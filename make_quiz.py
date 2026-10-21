"""Reels de UDA · Unión de Arquitectos (diseño editorial de tarjetas + voz en off masculina), en 6 estilos (themes.py).

Estructura con pregunta: gancho -> pregunta (la voz la lee, las palabras se iluminan al decirlas) -> cuenta atrás ->
respuesta correcta marcada en bronce -> explicación breve con su fuente (BOE o documentos de UDA) -> cierre con la web.
Estructura sin pregunta (checklist, delegar, uda_servicio): gancho -> 3 claves que aparecen al decirlas -> cierre.
Formatos: test_normativa, error_tipico, mito_realidad, norma_30s, simulacro_3, caso_despacho (escena + pregunta),
checklist, delegar, uda_servicio y repaso_express (4 fichas que se giran).

    QUIZ_MOCK=1 VOICE_ENGINE=mock python make_quiz.py <formato> out.mp4 [estilo]      (prueba sin red)
"""
import json, math, os, random, subprocess, sys
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw

import fx
import themes
from fx import W, H, FPS, SR, F800, F900, CARBON, PIEDRA, BRONCE, ARENA, GRIS, INK, PAPER, WHITE, TERRACOTA, eob, eo, clamp
import questions as QB
import marca as M

HERE = os.path.dirname(os.path.abspath(__file__))
CARD_W, PAD = 950, 46
CARD_TOP = 410            # tope superior mínimo de las tarjetas
CARD_CENTER = 900         # las tarjetas se centran aquí si caben (zona segura 250-1500)
CARD_MAX_BOTTOM = 1385   # deja sitio debajo para 'Comenta…' / retos dentro de la zona segura
HDR = 74                  # alto de la cabecera de la hoja (estilo examen)
THINK = {"corto": 5, "normal": 7, "largo": 9}
BADGE = {"caso_coste": "CUÁNTO CUESTA DELEGAR", "grafico": "LAS CIFRAS", "claves": "3 CLAVES PARA TU DESPACHO", "comparativa": "CONTRATAR O DELEGAR", "dato": "DATO DE PROYECTO",
         "test_normativa": "TEST DE NORMATIVA", "error_tipico": "ERROR TÍPICO EN PROYECTO", "mito_realidad": "MITO O REALIDAD",
         "norma_30s": "NORMATIVA EN 30 SEGUNDOS", "simulacro_3": "TEST RÁPIDO", "caso_despacho": "CASO DE DESPACHO",
         "checklist": "CHECKLIST DE PROYECTO", "delegar": "CONTRATAR O DELEGAR", "uda_servicio": "ASÍ TRABAJA UDA",
         "repaso_express": "REPASO EXPRÉS"}
DEFAULT_STYLE = {"caption_scale": 1.0, "screen_hook": "", "follow_line": "Síguenos: normativa y oficio cada día",
                 "share_line": "Envíaselo a tu socio del despacho", "save_line": "", "reto_line": "", "series": ""}
TAGS_FIXED = ["#arquitectura", "#arquitectos"]
TAGS_ROT = ["#CTE", "#normativa", "#proyectodeejecucion", "#despachodearquitectura", "#arquitecturaespaña", "#BIM", "#Revit",
            "#arquitectostecnicos", "#edificacion"]
T = themes.get("negro")
NEGRO_ = fx.NEGRO


def ctop(h):
    """Posición superior de una tarjeta de alto h: centrada en la zona útil, sin pasar de los límites."""
    return int(max(CARD_TOP - 20, min(CARD_CENTER - h / 2, CARD_MAX_BOTTOM - h)))


def _mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a[:3], b[:3]))


# ------------------------------------------------------------------ tarjetas
def _card_base(h, header=None):
    im = Image.new("RGBA", (CARD_W, int(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CARD_W - 1, int(h) - 1], T.card_radius, fill=T.card_fill,
                        outline=T.card_outline, width=3 if T.card_outline else 0)
    if T.top_rule and not header:                      # filete bronce arriba, como las tarjetas de los documentos
        d.rectangle([T.card_radius // 2, 0, CARD_W - 1 - T.card_radius // 2, 7], fill=T.top_rule)
    if header:                                         # cajetín de plano: marca a la izquierda, tipo de hoja a la derecha
        f = fx.font(F900, 24); f2 = fx.font(F800, 22)
        d.text((PAD, 26), header, font=f, fill=T.ink)
        d.text((CARD_W - PAD - f2.getlength(T.header_right), 28), T.header_right, font=f2, fill=T.label)
        d.line([(PAD, HDR - 8), (CARD_W - PAD, HDR - 8)], fill=T.ink, width=3)
    return im


def _letter(row, k, cy, color=None):
    """Distintivo de la letra (A-D) según el estilo."""
    rd = ImageDraw.Draw(row); L = QB.LETTERS[k]; f = fx.font(F900, 36)
    if T.letter == "box":                                  # casilla de hoja de respuestas
        rd.rectangle([20, cy - 26, 72, cy + 26], outline=T.ink, width=4)
        rd.text((46 - f.getlength(L.lower()) / 2, cy - 25), L.lower(), font=f, fill=color or T.ink)
    elif T.letter == "circle_outline":
        rd.ellipse([16, cy - 31, 78, cy + 31], outline=color or T.accent, width=4)
        rd.text((47 - f.getlength(L) / 2, cy - 25), L, font=f, fill=color or T.accent)
    elif T.letter == "square":
        rd.rounded_rectangle([16, cy - 31, 78, cy + 31], 12, fill=color or T.accent)
        rd.text((47 - f.getlength(L) / 2, cy - 25), L, font=f, fill=T.accent_fg)
    else:
        rd.ellipse([16, cy - 31, 78, cy + 31], fill=color or T.accent)
        rd.text((47 - f.getlength(L) / 2, cy - 25), L, font=f, fill=T.accent_fg)


class QuestionCard:
    """Tarjeta con enunciado + 4 opciones. Mide su propio tamaño para caber siempre en la zona segura."""

    def __init__(self, P, label, counter=None):
        self.P, self.label, self.counter = P, label, counter
        self.hdr = HDR if T.header else 0
        inner = CARD_W - 2 * PAD
        for qs, os_ in ((62, 48), (58, 46), (54, 43), (50, 40), (47, 38), (44, 35), (41, 33), (38, 30)):
            self.qs, self.os = qs, os_
            self.q_img = fx.text_block(P["pregunta"], F900, qs, inner)
            self.rows = [self._row_layout(k) for k in range(4)]
            self.h = self.hdr + PAD + 52 + self.q_img.height + 26 + sum(self.rows) + 16 * 3 + PAD
            if CARD_TOP + self.h <= CARD_MAX_BOTTOM:
                break
        self.ok_center = (CARD_W / 2, self.h / 2)
        self._cache = {}

    def _row_layout(self, k):
        im = fx.text_block(self.P["op"][k], F800, self.os, CARD_W - 2 * PAD - 70 - 44)
        return max(86, im.height + 30)

    def render(self, lit=None, active=None, reveal=0.0, trampa=None, show_trampa=0.0):
        key = (lit, active, round(reveal, 1), trampa, round(show_trampa, 1))
        if key in self._cache:
            return self._cache[key]
        P = self.P
        im = _card_base(self.h, T.header); d = ImageDraw.Draw(im)
        y = self.hdr + PAD - 6
        room = CARD_W - 2 * PAD - (110 if self.counter else 0)
        lab = self.label
        while fx.font(F800, 30).getlength(lab) > room and " " in lab:
            lab = lab.rsplit(" ", 1)[0].rstrip(" ,·-") + "…"
        d.text((PAD, y), lab, font=fx.font(F800, 30), fill=T.label)
        if self.counter:
            c = fx.pill(self.counter, 30, T.accent if T.letter != "box" else T.ink, WHITE, padx=22, pady=8)
            im.alpha_composite(c, (CARD_W - PAD - c.width, y - 6))
        y += 52
        q = fx.text_block(P["pregunta"], F900, self.qs, CARD_W - 2 * PAD, T.ink, lit=lit, dim=T.dim)
        im.alpha_composite(q, (PAD, y)); y += q.height + 26
        a = eo(reveal)
        for k in range(4):
            rh = self.rows[k]
            ok, is_tr = k == P["ok"], (k == trampa and show_trampa > 0)
            fill, txt, outline, lcol = T.row_fill, T.ink, None, None
            if active == k and reveal == 0:
                fill, outline = T.row_active, T.row_outline
            if reveal > 0:
                if ok and T.ok_mode == "fill":
                    fill = _mix(T.row_fill, T.ok_col, a); txt = T.ok_text if a > .5 else T.ink
                elif ok and T.ok_mode == "pen":
                    fill = _mix(T.row_fill, (232, 238, 255), a); txt = T.ok_text if a > .5 else T.ink
                elif ok:
                    txt = T.ok_text
                elif is_tr:
                    fill, outline = T.bad_fill, T.bad_col
                else:
                    txt = _mix(T.ink, T.faded, a * .75); lcol = _mix(T.accent, T.faded, a * .8)
            row = Image.new("RGBA", (CARD_W - 2 * PAD, rh), (0, 0, 0, 0)); rd = ImageDraw.Draw(row)
            rd.rounded_rectangle([0, 0, row.width - 1, rh - 1], T.row_radius, fill=fill, outline=outline, width=5 if outline else 0)
            cy = rh // 2
            t = fx.text_block(P["op"][k], F800, self.os, row.width - 70 - 44, txt)
            if ok and reveal > 0 and T.ok_mode == "marker":        # subrayador amarillo que se desliza
                hl = Image.new("RGBA", (int((t.width + 20) * a) + 2, t.height - 6), T.ok_col + (190,))
                row.alpha_composite(hl, (90, (rh - t.height) // 2 + 8))
            if reveal > 0.5 and ok and T.ok_mode == "pen":           # aspa de bolígrafo azul en la casilla
                _letter(row, k, cy, T.ok_col)
                p = clamp((reveal - .5) * 2)
                rd.line([(24, cy - 22), (24 + 44 * p, cy - 22 + 44 * p)], fill=T.ok_col, width=7)
                if p > .5:
                    rd.line([(68, cy - 22), (68 - 44 * (p - .5) * 2, cy - 22 + 44 * (p - .5) * 2)], fill=T.ok_col, width=7)
            elif reveal > 0.5 and ok:
                icon = fx.check_icon(62, T.ok_col, T.ok_text) if T.ok_mode == "fill" else fx.check_icon(62, WHITE, T.accent)
                row.alpha_composite(icon, (16, cy - 31))
            elif reveal > 0.5 and is_tr:
                row.alpha_composite(fx.cross_icon(62, WHITE, T.bad_col), (16, cy - 31))
            else:
                _letter(row, k, cy, lcol)
            row.alpha_composite(t, (100, (rh - t.height) // 2 + 4))
            if is_tr:
                tag = fx.pill("TRAMPA", 26, T.bad_col, WHITE, padx=16, pady=6)
                row.alpha_composite(tag, (row.width - tag.width - 14, 8))
            im.alpha_composite(row, (PAD, y))
            if ok:
                self.ok_center = (PAD + 60, y + rh / 2)
            y += rh + 16
        self._cache[key] = im
        return im


class TextCard:
    """Tarjeta de explicación / truco / afirmación / puntos clave / ficha, con karaoke del texto hablado."""

    def __init__(self, title, body, ref=None, top_line=None, big=None, bullets=None, title_color=None, body_size=54,
                 title_fg=None, icons=False):
        self.title, self.body, self.ref, self.top, self.big, self.bullets = title, body, ref, top_line, big, bullets
        self.icons = [fx.icon_for(b) for b in (bullets or [])] if icons else None
        self.title_color, self.title_fg = title_color or T.title_bg, title_fg or (T.title_fg if not title_color else WHITE)
        inner = CARD_W - 2 * PAD
        for bs in (body_size, body_size - 4, body_size - 8, body_size - 12, body_size - 16):
            self.bs = bs
            self.h = self._measure(inner)
            if CARD_TOP + self.h <= CARD_MAX_BOTTOM:
                break
        self._cache = {}

    def _measure(self, inner):
        h = PAD
        if self.top:
            h += fx.text_block(self.top, F800, 36, inner - 90).height + 40
        if self.title:
            h += 64
        if self.big:
            h += fx.text_block(self.big, F900, 64, inner).height + 24
        if self.body:
            h += fx.text_block(self.body, F800, self.bs, inner).height + 10
        for b in self.bullets or []:
            h += fx.text_block(b, F800, self.bs, inner - 84).height + 26
        if self.ref:
            h += 80
        return h + PAD

    def render(self, lit=None, n_bullets=None, bullet_lit=None):
        key = (lit, n_bullets, bullet_lit)
        if key in self._cache:
            return self._cache[key]
        inner = CARD_W - 2 * PAD
        im = _card_base(self.h); d = ImageDraw.Draw(im)
        y = PAD
        if self.top:                                      # respuesta correcta recordada arriba
            t = fx.text_block(self.top, F800, 36, inner - 90, T.ok_text if T.ok_mode == "fill" else T.ink)
            band = Image.new("RGBA", (inner, t.height + 24), (0, 0, 0, 0))
            bcol = T.ok_col if T.ok_mode == "fill" else (_mix(T.ok_col, (255, 255, 255), .55))
            ImageDraw.Draw(band).rounded_rectangle([0, 0, inner - 1, band.height - 1], min(24, T.row_radius), fill=bcol)
            band.alpha_composite(fx.check_icon(50, bcol, T.ok_text if T.ok_mode == "fill" else T.ink), (14, (band.height - 50) // 2))
            band.alpha_composite(t, (80, 14)); im.alpha_composite(band, (PAD, y)); y += band.height + 22
        if self.title:
            p = fx.pill(self.title, 30, self.title_color, self.title_fg, padx=22, pady=9, radius=T.pill_radius)
            im.alpha_composite(p, (PAD, y)); y += 64
        if self.big:
            b = fx.text_block(self.big, F900, 64, inner, T.big_col)
            im.alpha_composite(b, (PAD, y)); y += b.height + 24
        if self.body:
            b = fx.text_block(self.body, F800, self.bs, inner, T.ink, lit=lit, dim=T.dim)
            im.alpha_composite(b, (PAD, y)); y += b.height + 10
        for k, bl in enumerate(self.bullets or []):
            if n_bullets is not None and k >= n_bullets:
                break
            if self.icons:
                im.alpha_composite(fx.icon(self.icons[k], 92, T.ok_col), (PAD - 18, y - 16))
            else:
                d.ellipse([PAD, y + 2, PAD + 58, y + 60], fill=T.accent if T.letter != "box" else T.ink)
                f = fx.font(F900, 34); d.text((PAD + 29 - f.getlength(str(k + 1)) / 2, y + 6), str(k + 1), font=f,
                                              fill=T.accent_fg if T.letter != "box" else WHITE)
            b = fx.text_block(bl, F800, self.bs, inner - 84, T.ink,
                              lit=(bullet_lit if k == (n_bullets or 0) - 1 else None), dim=T.dim)
            im.alpha_composite(b, (PAD + 84, y + 4)); y += b.height + 26
        if self.ref:
            r = fx.pill(self.ref, 26, T.ref_bg, T.ref_fg, padx=20, pady=10, path=F800, radius=T.pill_radius)
            if r.width > CARD_W - 2 * PAD:
                r = r.resize((CARD_W - 2 * PAD, int(r.height * (CARD_W - 2 * PAD) / r.width)), Image.LANCZOS)
            im.alpha_composite(r, (PAD, int(self.h - PAD - r.height)))
        self._cache[key] = im
        return im


class ChartCard:
    """Gráfico de barras animado: cada barra crece al decirla; la conclusión aparece al final. Cifras tal cual de la fuente."""

    def __init__(self, title, bars, conclusion, ref=None, hi_set=None):
        self.title, self.bars, self.conclusion, self.ref = title, bars, conclusion, ref
        self.note = "Precios de referencia" if any("€" in b["texto"] for b in bars) else None
        self.vmax = max(b["valor"] for b in bars)
        hi = [i for i, b in enumerate(bars) if "uda" in b["etiqueta"].lower() or "delega" in b["etiqueta"].lower()]
        self.hi = hi[0] if hi else None
        if hi_set is not None:
            self.hi = None; self.hiset = set(hi_set)
        else:
            self.hiset = None
        self.th = fx.text_block(title, F900, 56, CARD_W - 2 * PAD).height
        self.ch = fx.text_block(conclusion, F900, 42, CARD_W - 2 * PAD - 84).height
        self.rows = []
        for b in bars:
            v = fx.text_block(b["texto"], F900, 38, fx.font(F900, 38).getlength(b["texto"]) + 4)
            self.rows.append(max(fx.text_block(b["etiqueta"], F800, 34, CARD_W - 2 * PAD - v.width - 24).height, v.height))
        self.h = (PAD + self.th + 36 + sum(r + 8 + 58 + 34 for r in self.rows) + 20 + self.ch + 40 + (60 if self.note else 0)
                  + (80 if ref else 0) + PAD)
        self._cache = {}

    def render(self, grow=None, show_conc=0.0, lit=None):
        """grow: lista con el avance (0-1) de cada barra."""
        grow = grow or [1.0] * len(self.bars)
        key = (tuple(round(g, 2) for g in grow), round(show_conc, 1), lit)
        if key in self._cache:
            return self._cache[key]
        im = _card_base(self.h); d = ImageDraw.Draw(im)
        y = PAD
        im.alpha_composite(fx.text_block(self.title, F900, 56, CARD_W - 2 * PAD, T.ink), (PAD, y)); y += self.th + 36
        maxw = CARD_W - 2 * PAD
        for k, b in enumerate(self.bars):
            g = eo(grow[k])
            v = fx.text_block(b["texto"], F900, 38, fx.font(F900, 38).getlength(b["texto"]) + 4, T.ink)
            lab = fx.text_block(b["etiqueta"], F800, 34, CARD_W - 2 * PAD - v.width - 24, T.ink if g > 0 else T.faded)
            im.alpha_composite(lab, (PAD, y))
            if g > 0.5:                                    # la cifra aparece a la derecha, encima de la barra
                vv = v.copy(); vv.putalpha(vv.getchannel("A").point(lambda a_: int(a_ * min(1, (g - 0.5) * 2))))
                im.alpha_composite(vv, (CARD_W - PAD - v.width, y - 2))
            by = y + self.rows[k] + 8; bw = max(10, maxw * b["valor"] / self.vmax * g)
            on = (k in self.hiset) if self.hiset is not None else (self.hi == k or (self.hi is None and k == len(self.bars) - 1))
            col = T.ok_col if on else _mix(T.ink, T.faded, 0.25)
            d.rounded_rectangle([PAD, by, PAD + maxw, by + 58], 6, fill=_mix(T.faded, T.card_fill[:3] if isinstance(T.card_fill, tuple) else T.card_fill, 0.5))
            d.rounded_rectangle([PAD, by, PAD + bw, by + 58], 6, fill=col)
            y = by + 58 + 34
        y += 20
        if show_conc > 0:
            ic = fx.icon("up" if (self.hi is None and self.hiset is None) else "check", 72, T.ok_col)
            im.alpha_composite(ic, (PAD, y + 2))
            c = fx.text_block(self.conclusion, F900, 42, CARD_W - 2 * PAD - 84, T.ink, lit=lit, dim=T.dim)
            im.alpha_composite(c, (PAD + 84, y + 4)); y += self.ch + 40
        else:
            y += self.ch + 40
        if self.note:
            im.alpha_composite(fx.text_block(self.note, F800, 26, 600, _mix(T.ink, T.faded, 0.4)), (PAD, y))
        if self.ref:
            r_ = fx.pill(self.ref, 26, T.ref_bg, T.ref_fg, padx=20, pady=10, path=F800, radius=T.pill_radius)
            if r_.width > CARD_W - 2 * PAD:
                r_ = r_.resize((CARD_W - 2 * PAD, int(r_.height * (CARD_W - 2 * PAD) / r_.width)), Image.LANCZOS)
            im.alpha_composite(r_, (PAD, int(self.h - PAD - r_.height)))
        self._cache[key] = im
        return im


class CompareCard:
    """Comparativa a dos columnas (p. ej. «Contratar en plantilla» / «Contratar por servicios»): las filas aparecen al decirlas."""

    def __init__(self, title, col_a, col_b, rows, ref=None):
        self.title, self.col_a, self.col_b, self.rows, self.ref = title, col_a, col_b, rows, ref
        for s in (54, 50, 46, 42, 38, 34):
            self.s = s
            self.h = self._measure()
            if CARD_TOP + self.h <= CARD_MAX_BOTTOM:
                break
        self._cache = {}

    def _colw(self):
        return (CARD_W - 2 * PAD - 30) // 2

    def _measure(self):
        h = PAD + fx.text_block(self.title, F900, 54, CARD_W - 2 * PAD).height + 24 + 44
        for r in self.rows:
            ha = fx.text_block(r["a"], F800, self.s, self._colw() - 52).height
            hb = fx.text_block(r["b"], F900, self.s, self._colw() - 52).height
            h += 46 + max(ha, hb) + 30
        return h + (80 if self.ref else 0) + PAD

    def render(self, n_rows=3, hot=None):
        key = (n_rows, hot)
        if key in self._cache:
            return self._cache[key]
        im = _card_base(self.h); d = ImageDraw.Draw(im)
        y = PAD
        t = fx.text_block(self.title, F900, 54, CARD_W - 2 * PAD, T.ink)
        im.alpha_composite(t, (PAD, y)); y += t.height + 24
        cw = self._colw(); xb = PAD + cw + 30
        im.alpha_composite(fx.spaced(self.col_a.upper(), F900, 26, _mix(T.ink, T.faded, 0.45), 0.06), (PAD, y))
        im.alpha_composite(fx.spaced(self.col_b.upper(), F900, 26, T.label, 0.06), (xb, y))
        y += 44
        for k, r in enumerate(self.rows):
            ha = fx.text_block(r["a"], F800, self.s, cw - 52).height; hb = fx.text_block(r["b"], F900, self.s, cw - 52).height
            rh = 46 + max(ha, hb) + 30
            if k < n_rows:
                d.line([(PAD, y), (CARD_W - PAD, y)], fill=T.faded, width=2)
                if hot == k:
                    d.rectangle([xb - 14, y + 8, CARD_W - PAD + 6, y + rh - 8], fill=_mix(T.card_fill if len(T.card_fill) == 3 else T.card_fill[:3], T.ok_col, 0.12))
                im.alpha_composite(fx.spaced(r["aspecto"].upper(), F900, 24, T.label, 0.05), (PAD, y + 12))
                im.alpha_composite(fx.icon("cross", 52, T.bad_col), (PAD - 6, y + 46))
                im.alpha_composite(fx.icon("check", 52, T.ok_col), (xb - 6, y + 46))
                im.alpha_composite(fx.text_block(r["a"], F800, self.s, cw - 52, _mix(T.ink, T.faded, 0.35)), (PAD + 52, y + 46))
                im.alpha_composite(fx.text_block(r["b"], F900, self.s, cw - 52, T.ink), (xb + 52, y + 46))
            y += rh
        if self.ref:
            r_ = fx.pill(self.ref, 26, T.ref_bg, T.ref_fg, padx=20, pady=10, path=F800, radius=T.pill_radius)
            if r_.width > CARD_W - 2 * PAD:
                r_ = r_.resize((CARD_W - 2 * PAD, int(r_.height * (CARD_W - 2 * PAD) / r_.width)), Image.LANCZOS)
            im.alpha_composite(r_, (PAD, int(self.h - PAD - r_.height)))
        self._cache[key] = im
        return im


def brand_card(style):
    """Tarjeta final, como la cabecera de los documentos de UDA: bloque carbón, logotipo, claim y la web (solo hechos)."""
    h = 860
    im = Image.new("RGBA", (CARD_W, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CARD_W - 1, h - 1], 12, fill=T.brand_bg, outline=T.card_outline if T.name == "negro" else None, width=2)
    d.rectangle([6, 0, CARD_W - 7, 8], fill=T.brand_rule)
    lg = fx.logo(104, T.brand_ink, T.brand_sub)
    im.alpha_composite(lg, ((CARD_W - lg.width) // 2, 64))
    y = 64 + lg.height + 44
    cl = fx.text_block(M.CLAIM, F900, 50, 800, T.brand_ink, align="center")
    im.alpha_composite(cl, ((CARD_W - cl.width) // 2, y)); y += cl.height + 18
    sub = fx.text_block("Proyectos Básicos y de Ejecución · Precio cerrado · Tu firma al final", F800, 30, 780, T.brand_sub,
                        align="center")
    im.alpha_composite(sub, ((CARD_W - sub.width) // 2, y)); y += sub.height + 34
    p1 = fx.pill("PRESUPUESTO CERRADO EN 24–72 H", 32, T.brand_pill, T.brand_pill_fg, padx=30, pady=13, radius=4)
    im.alpha_composite(p1, ((CARD_W - p1.width) // 2, y)); y += p1.height + 26
    p2 = fx.pill(M.WEB, 54, T.brand_web, T.brand_web_fg, padx=40, pady=16, radius=4)
    im.alpha_composite(p2, ((CARD_W - p2.width) // 2, y)); y += p2.height + 24
    p3 = fx.text_block("Link en la bio", F900, 34, 600, T.brand_ink, align="center")
    im.alpha_composite(p3, ((CARD_W - p3.width) // 2, y)); y += p3.height + 8
    if style.get("follow_line") and y < h - 60:
        p4 = fx.text_block(style["follow_line"], F800, 30, 820, T.brand_sub, align="center")
        im.alpha_composite(p4, ((CARD_W - p4.width) // 2, min(y, h - p4.height - 30)))
    return im


def badge(fmt, extra=None, series=None):
    b = fx.pill(series.upper() if series else BADGE[fmt], 32, T.badge_bg, T.badge_fg, padx=26, pady=12, radius=T.pill_radius)
    if not extra:
        return b
    e = fx.pill(extra, 30, T.chip_bg, T.chip_fg, padx=22, pady=11, path=F800, radius=T.pill_radius)
    if b.width + 16 + e.width > W - 120:
        return b
    im = Image.new("RGBA", (b.width + 16 + e.width, max(b.height, e.height)), (0, 0, 0, 0))
    im.alpha_composite(b, (0, (im.height - b.height) // 2)); im.alpha_composite(e, (b.width + 16, (im.height - e.height) // 2))
    return im


def ring(remain, frac, size=170):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([6, 6, size - 6, size - 6], fill=T.ring_bg)
    col = T.warn_col if remain <= 3 else T.ring_col
    d.arc([14, 14, size - 14, size - 14], -90, -90 + 360 * frac, fill=col, width=16)
    f = fx.font(F900, 78); t = str(remain)
    d.text((size / 2 - f.getlength(t) / 2, size / 2 - 52), t, font=f, fill=T.ring_fg if T.name != "minimal" else WHITE)
    return im


def burst(fr, cx, cy, lt, seed=3):
    """Destello de partículas al revelar la respuesta correcta (0,8 s)."""
    if lt > 0.8 or not T.burst:                        # estilos sobrios: sin confeti
        return
    rng = random.Random(seed); d = ImageDraw.Draw(fr)
    for k in range(30):
        ang = rng.uniform(0, 2 * math.pi); sp = rng.uniform(260, 820); col = T.burst[k % len(T.burst)]
        r0 = sp * eo(lt / 0.8); x = cx + math.cos(ang) * r0; y = cy + math.sin(ang) * r0 * 0.7 + 260 * lt * lt
        s = max(2, 10 * (1 - lt / 0.8))
        d.ellipse([x - s, y - s, x + s, y + s], fill=tuple(col[:3]) + (int(255 * (1 - lt / 0.8)),))


# ------------------------------------------------------------------ guion -> líneas de voz
# El tercer elemento es una pista de interpretación MUY corta y en inglés: nunca se dice, solo orienta la entonación
# (en inglés para que la voz no la confunda con el texto en español; voice.py además rechaza cualquier toma que la lea).
def lines_for(fmt, items, S):
    P = items[0]
    L = [("hook", S["hook_line"], "punchy, confident challenge")]
    if fmt == "repaso_express":
        for i, F in enumerate(items):
            L.append((f"fq{i}", F["q"], "clear, quick question"))
            L.append((f"fa{i}", F["a"], "assured, explaining"))
        L.append(("fin", S["cierre_line"], "warm, inviting"))
    elif fmt == "simulacro_3":
        for i, Q in enumerate(items):
            L.append((f"q{i}", Q["pregunta"], "clear, brisk"))
            L.append((f"r{i}", f"La {Q['letra']}.", "confident, short"))
        L.append(("fin", S["cierre_line"], "warm, inviting"))
    elif fmt == "mito_realidad":
        L.append(("st", S["afirmacion"], "intriguing"))
        L.append(("rev", "¡Mito!" if S["veredicto"] == "MITO" else "¡Realidad!", "emphatic, lively"))
        L.append(("ex", S["explicacion"], "assured, explaining"))
    elif fmt == "grafico":
        if S.get("intro_line"):
            L.append(("intro", S["intro_line"], "intriguing, confident"))
        for k, b in enumerate(S["barras"]):
            L.append((f"b{k}", f"{b['etiqueta']}: {b['texto']}.", "clear, assured, building up"))
        L.append(("conc", S["conclusion"], "emphatic, confident conclusion"))
    elif fmt == "caso_coste":
        for k, b in enumerate(S["barras"]):
            L.append((f"b{k}", f"{b['etiqueta']}: {b['texto']}.", "clear, assured, building up"))
        L.append(("conc", S["conclusion"], "emphatic, confident conclusion"))
        L.append(("pt", S["puntos_titulo"] + ".", "assured"))
        for k, p in enumerate(S["puntos"]):
            L.append((f"p{k}", p, "clear, assured, explaining"))
    elif fmt == "dato":
        L.append(("st", S["afirmacion"], "revealing, confident, slight emphasis"))
        L.append(("ex", S["explicacion"], "assured, explaining"))
    elif fmt == "comparativa":
        for k, r in enumerate(S["filas"]):
            L.append((f"c{k}", f"{r['aspecto']}. {S['col_a']}: {r['a']}. {S['col_b']}: {r['b']}.", "clear, assured, contrasting"))
    elif fmt in QB.POINTS_ONLY:
        if fmt == "caso_despacho":
            L.append(("esc", S["escena"], "storytelling, slight suspense"))
        for k, p in enumerate(S["puntos"]):
            L.append((f"p{k}", p, "clear, assured, explaining"))
    else:
        if fmt == "norma_30s":
            for k, p in enumerate(S["puntos"]):
                L.append((f"p{k}", p, "clear, explaining"))
        if fmt == "caso_despacho":
            L.append(("esc", S["escena"], "storytelling, slight suspense"))
        L.append(("q", P["pregunta"], "natural, clear"))
        if fmt != "norma_30s":
            for k, o in enumerate(P["op"]):
                L.append((f"o{k}", f"{QB.LETTERS[k]}. {o}", "natural, listing"))
        L.append(("rev", S["reveal_line"], "confident, a hint of a smile"))
        if fmt == "error_tipico":
            L.append(("ex", S["trampa_porque"], "explaining, warning"))
        elif fmt != "norma_30s":
            L.append(("ex", S["explicacion"], "assured, explaining"))
    L.append(("cta", S["cta_line"], "warm, persuasive"))
    return L


# Una sola dirección de voz para TODO el reel: si cada frase lleva su propia indicación (enérgica, cálida...), el modelo
# cambia de timbre entre tomas y el revisor lo detecta como dos voces distintas.
ONE_VOICE = "confident, warm and assured, same timbre, pitch and energy as every other line of this reel"


def _groups(L):
    """Bloques que se dicen seguidos (pregunta + opciones, solución + explicación, ficha + respuesta, 3 claves...)."""
    out = []
    for item in L:
        k = item[0]
        joins = k[:1] == "o" or k in ("ex", "p1", "p2", "c1", "c2", "b1", "b2", "b3", "conc") or k.startswith("fa") or (k.startswith("r") and k[1:].isdigit())
        if joins and out:
            out[-1].append(item)
        else:
            out.append([item])
    return out


def ref_label(P):
    """Fuente que se muestra en pantalla: la referencia verificada (norma y artículo, o documento de UDA y apartado)."""
    if P.get("tipo") == "caso":
        return "Fuente: " + P["referencia"]
    r = QB.verif().get(P["id"], {})
    ref = r.get("referencia") if r.get("fuente_ok") else ""
    if ref:
        return "Fuente: " + ref
    return "Tema: " + QB.tema_corto(P.get("tema"))


CTA_CAPTION = M.CTA_CAPTION


def caption_text(fmt, items, S, rng, st=None):
    P = items[0]; st = st or {}
    if fmt == "repaso_express":
        body = f"Repaso exprés · {QB.tema_titulo(P['tema'])}:\n\n" + "\n\n".join(
            f"{i + 1}. {F['q']}\n→ {F['a']}" for i, F in enumerate(items))
    elif fmt == "simulacro_3":
        body = "\n\n".join(f"{i + 1}. {Q['pregunta']}\n" + "\n".join(f"{QB.LETTERS[k]}) {o}" for k, o in enumerate(Q["op"]))
                           for i, Q in enumerate(items))
    elif fmt == "mito_realidad":
        body = f"¿Mito o realidad? «{S['afirmacion']}»"
    elif fmt in QB.POINTS_ONLY:
        body = (S["escena"] + "\n\n" if fmt == "caso_despacho" else "") + f"{S['titulo_norma']}\n\n" + \
            "\n".join(f"{k + 1}. {p}" for k, p in enumerate(S["puntos"]))
    elif fmt == "comparativa":
        body = f"{S['titulo_norma']}: {S['col_a']} o {S['col_b']}\n\n" + "\n".join(
            f"▪️ {r['aspecto']} → {S['col_a']}: {r['a']} · {S['col_b']}: {r['b']}" for r in S["filas"])
    elif fmt == "dato":
        body = f"{S['afirmacion']}\n\n{S['explicacion']}"
    elif fmt == "caso_coste":
        body = (f"{S['titulo_norma']} (precios de referencia):\n\n" + "\n".join(f"▪️ {b['etiqueta']}: {b['texto']}" for b in S["barras"])
                + f"\n\n→ {S['conclusion']}\n\n{S['puntos_titulo']}:\n" + "\n".join(f"✔️ {p}" for p in S["puntos"]))
    elif fmt == "grafico":
        nota = " (precios de referencia)" if any("€" in b["texto"] for b in S["barras"]) else ""
        body = f"{S['titulo_norma']}{nota}\n\n" + "\n".join(f"▪️ {b['etiqueta']}: {b['texto']}" for b in S["barras"]) + \
            f"\n\n→ {S['conclusion']}"
    else:
        body = (S["escena"] + "\n\n" if fmt == "caso_despacho" else "") + P["pregunta"] + "\n" + \
               "\n".join(f"{QB.LETTERS[k]}) {o}" for k, o in enumerate(P["op"]))
    refs = list(dict.fromkeys(ref_label(Q) for Q in items if ref_label(Q).startswith("Fuente")))
    fuente = ("\n\n" + " · ".join(refs)) if refs else ""
    tags = TAGS_FIXED + rng.sample(TAGS_ROT, 3)
    sol = " La respuesta, al final del vídeo." if fmt == "mito_realidad" else ""
    extra = "".join(f"{x}\n" for x in (S.get("save_caption"), S.get("tag_caption"), S.get("web_caption"),
                                        S.get("follow_caption"), S.get("seo_line")) if x)
    return (f"{S['caption_hook']}\n\n{body}{fuente}\n\n{S['comment_prompt'].rstrip('.!')}.{sol}\n\n"
            + (extra + "\n" if extra else "") + CTA_CAPTION + "\n\n" + " ".join(tags))


# ------------------------------------------------------------------ build
def build(fmt, items, S, seed, out, arms=None, style=None, max_len=58.0, keep_voice=False, image=None, estilo=None):
    """image: ilustración original (PIL) para el estilo 'ilustrado', el gancho y la escena del caso de despacho."""
    global T
    import voice
    arms = arms or {}
    estilo = estilo or arms.get("estilo") or "negro"
    if estilo == "ilustrado" and image is None:
        estilo = "negro"                                 # sin imagen: el estilo más parecido
    T = themes.get(estilo)
    st = {**DEFAULT_STYLE, **(style or {})}
    if st.get("screen_hook"):
        S = {**S, "screen_hook": st["screen_hook"]}
    rng = random.Random(f"{seed}-{fmt}")
    P = items[0]
    count = 5 if fmt == "simulacro_3" else THINK.get(arms.get("think_time"), 7)
    L = lines_for(fmt, items, S)
    speed = float(st.get("voice_speed") or 1.0)

    if not keep_voice:
        voice.reset()                    # reel nuevo: elige la mejor voz y úsala en todas las frases
    for attempt in range(3):
        try:
            clips = []
            for grp in _groups(L):                  # cada bloque se graba de una sola toma: entonación más natural
                clips += voice.say_many([t for _, t, _ in grp], speed=speed, styles=[ONE_VOICE] * len(grp),
                                        one_take=len(grp) > 1)
            break
        except voice.VoiceError as e:
            print(f"voz cambiada a mitad de reel ({e}); repito con {voice.next_engine()}", flush=True)
            voice.reset(voice.next_engine())
    else:
        raise RuntimeError("no se pudo grabar una voz coherente")
    A = {k: c for (k, _, _), c in zip(L, clips)}; TXT = {k: t for k, t, _ in L}
    # control final de la voz: cada frase debe decir su texto UNA vez, en español (letras incluidas) y sin indicaciones.
    # Si una falla, se graba otra vez sola (hasta 4 tomas nuevas, cada una con sus propios reintentos); si no sale
    # limpia, el reel no se publica con ese fallo y se pasa al siguiente formato.
    if voice.LOCK != "mock":
        for k, t, s_ in L:
            why = voice.problem(A[k], t)
            tries = 0
            while why and tries < 4:
                tries += 1
                print(f"voz: '{k}' {why}; la grabo otra vez sola (intento {tries})", flush=True)
                try:
                    A[k] = voice.say_many([t], speed=speed, styles=[ONE_VOICE], one_take=False, force=True)[0]
                except voice.VoiceError:
                    raise
                except Exception as e:
                    print("voz: nueva toma fallida:", str(e)[:150], flush=True); continue
                why = voice.problem(A[k], t)
            if why:
                raise RuntimeError(f"la voz no graba bien '{t[:40]}' ({why})")
    D = {k: len(a) / SR for k, a in A.items()}

    # ---- línea de tiempo (si sale demasiado larga, se acorta el tiempo para pensar)
    def plan(count):
        SEG, VO = [], {}
        t = 0.0

        def seg(kind, dur, **kw):
            nonlocal t
            SEG.append({"kind": kind, "a": t, "b": t + dur, **kw}); t += dur

        def say(k, at):
            VO[k] = at

        seg("hook", max(2.6, D["hook"] + 0.6)); say("hook", 0.25)
        if fmt == "repaso_express":
            pause = max(1.2, min(2.5, count / 3))
            for i in range(len(items)):
                a = t; seg("fq", D[f"fq{i}"] + 0.6 + pause, q=i); say(f"fq{i}", a + 0.35)
                a = t; seg("fa", D[f"fa{i}"] + 0.9, q=i); say(f"fa{i}", a + 0.4)
            a = t; seg("score", D["fin"] + 1.2); say("fin", a + 0.3)
        elif fmt == "simulacro_3":
            for i, Q in enumerate(items):
                a = t; seg("question", D[f"q{i}"] + 0.9, q=i); say(f"q{i}", a + 0.45)
                seg("count", count, q=i, n=count)
                a = t; seg("reveal", max(1.6, D[f"r{i}"] + 0.6), q=i); say(f"r{i}", a + 0.15)
            a = t; seg("score", D["fin"] + 1.2); say("fin", a + 0.3)
        elif fmt == "mito_realidad":
            a = t; seg("statement", D["st"] + 1.0); say("st", a + 0.45)
            seg("count", count, q=0, n=count)
            a = t; seg("stamp", max(1.6, D["rev"] + 0.7)); say("rev", a + 0.1)
            a = t; seg("explain", D["ex"] + 1.2); say("ex", a + 0.5)
        elif fmt == "grafico":
            a = t; tt = a + 0.5
            if "intro" in D:
                say("intro", tt); tt += D["intro"] + 0.4
            starts = []
            for k in range(len(S["barras"])):
                starts.append(tt); say(f"b{k}", tt); tt += D[f"b{k}"] + 0.45
            cstart = tt; say("conc", tt); tt += D["conc"]
            seg("chart", tt - a + 1.8, starts=starts, cstart=cstart)
        elif fmt == "caso_coste":
            a = t; tt = a + 0.5; starts = []
            for k in range(len(S["barras"])):
                starts.append(tt); say(f"b{k}", tt); tt += D[f"b{k}"] + 0.4
            cstart = tt; say("conc", tt); tt += D["conc"]
            seg("chart", tt - a + 1.3, starts=starts, cstart=cstart)
            a = t; tt = a + 0.4; say("pt", tt); tt += D["pt"] + 0.25; starts = []
            for k in range(len(S["puntos"])):
                starts.append(tt); say(f"p{k}", tt); tt += D[f"p{k}"] + 0.4
            seg("points", tt - a + 1.2, starts=starts)
        elif fmt == "dato":
            a = t; seg("statement", D["st"] + 1.4); say("st", a + 0.45)
            a = t; seg("explain", D["ex"] + 1.4); say("ex", a + 0.5)
        elif fmt == "comparativa":
            a = t; tt = a + 0.6; starts = []
            for k in range(3):
                starts.append(tt); say(f"c{k}", tt); tt += D[f"c{k}"] + 0.5
            seg("compare", tt - a + 1.4, starts=starts)
        elif fmt in QB.POINTS_ONLY:                       # sin pregunta: las 3 claves aparecen al decirlas
            if fmt == "caso_despacho":
                a = t; seg("scene", D["esc"] + 1.0); say("esc", a + 0.4)
            a = t; tt = a + 0.5; starts = []
            for k in range(3):
                starts.append(tt); say(f"p{k}", tt); tt += D[f"p{k}"] + 0.45
            seg("points", tt - a + 1.4, starts=starts)
        else:
            if fmt == "norma_30s":
                a = t; tt = a + 0.5; starts = []
                for k in range(3):
                    starts.append(tt); say(f"p{k}", tt); tt += D[f"p{k}"] + 0.35
                seg("points", tt - a + 0.5, starts=starts)
            if fmt == "caso_despacho":
                a = t; seg("scene", D["esc"] + 1.0); say("esc", a + 0.4)
            a = t; tt = a + 0.45; say("q", tt); tt += D["q"] + 0.3; ostarts = []
            if "o0" in A:
                for k in range(4):
                    ostarts.append(tt); say(f"o{k}", tt); tt += D[f"o{k}"] + 0.2
            seg("question", tt - a + 0.3, q=0, ostarts=ostarts)
            seg("count", count, q=0, n=count)
            a = t; seg("reveal", max(2.0, D["rev"] + 0.9), q=0,
                       trampa=S.get("trampa") if fmt == "error_tipico" else None); say("rev", a + 0.15)
            if "ex" in A:
                a = t; seg("explain", D["ex"] + 1.2); say("ex", a + 0.5)
        a = t; seg("cta", max(4.8, D["cta"] + 1.8)); say("cta", a + 0.4)
        return SEG, VO, t

    SEG, VO, total = plan(count)
    n_counts = max(1, sum(1 for s_ in SEG if s_["kind"] == "count"))
    if total > max_len and count > 4:
        count = max(4, count - math.ceil((total - max_len) / n_counts))
        SEG, VO, total = plan(count)
    print(f"reel: {fmt} · estilo {T.name} · {total:.1f} s · {count} s para pensar", flush=True)

    # ---- audio
    n = int(SR * (total + 0.5)); vo = np.zeros(n, np.float32); sfx = np.zeros(n, np.float32)

    def put(buf, a, at, g=1.0):
        i = int(at * SR)
        if i >= n: return
        if i < 0: a = a[-i:]; i = 0
        j = min(n, i + len(a)); buf[i:j] += a[: j - i] * g
    for k, at in VO.items():
        put(vo, A[k], at)
    for sg in SEG:
        if sg["kind"] in ("question", "statement", "points", "explain", "cta", "score", "scene", "fq", "compare", "chart"):
            put(sfx, fx.whoosh(), sg["a"] - 0.15, 1.1)
        if sg["kind"] == "count":
            for s_ in range(sg["n"]):
                put(sfx, fx.tick(s_ >= sg["n"] - 3), sg["a"] + s_, 1.0)
            put(sfx, fx.riser(min(3.0, sg["n"])), sg["b"] - min(3.0, sg["n"]), 0.8)
        if sg["kind"] in ("reveal", "fa"):
            put(sfx, fx.chime_ok(), sg["a"] + 0.05, 1.0 if sg["kind"] == "reveal" else 0.6)
        if sg["kind"] == "stamp":
            put(sfx, fx.stamp(), sg["a"] + 0.05, 0.9)
    bpm = {"calma": T.music_bpm - 8, "energica": T.music_bpm + 14}.get(st.get("music"), T.music_bpm)
    music = fx.study_beat(total, bpm)[:n]
    venv = np.convolve((np.abs(vo) > 0.01).astype(np.float32), np.ones(3000) / 3000, "same")
    for sg in SEG:
        if sg["kind"] == "count":                         # más tensión y menos música mientras piensas
            music[int(sg["a"] * SR):int(sg["b"] * SR)] *= 0.55
    mix = vo * 1.15 + sfx + music * (0.55 - 0.35 * np.clip(venv * 3, 0, 1))
    mix = fx.dehiss(np.tanh(mix * 1.05) * 0.92)
    wav = out.replace(".mp4", ".wav"); sf.write(wav, mix, SR)

    # ---- karaoke: momento en que se dice cada palabra
    WT = {k: [VO[k] + ts for ts, _ in voice.align(A[k], TXT[k])] for k in VO}

    def lit(k, tt):
        return sum(1 for x in WT[k] if x <= tt) if k in WT else None

    # ---- elementos visuales
    bg = T.background(rng.randint(0, 999), image)
    hook_bg = themes.ImageBG(image, dark=0.25, blur=0) if image is not None else None
    corto = QB.tema_corto(P.get("tema"))
    extra = corto if len(corto) <= 26 and fmt not in ("simulacro_3", "delegar", "uda_servicio", "caso_coste") else None
    bdg = badge(fmt, extra, st.get("series"))
    # la web siempre visible arriba, en pequeño (si el reel se descarga y se reenvía, se sabe de dónde viene)
    web_img = fx.pill(M.WEB, 28, T.web_bg, T.web_fg, padx=22, pady=8, path=F800, radius=T.pill_radius)
    web_dark = fx.pill(M.WEB, 28, (0, 0, 0, 110), WHITE, padx=22, pady=8, path=F800, radius=T.pill_radius)
    on_img = hook_bg is not None
    hook_img = fx.headline(S["screen_hook"], 116, 920, 3,
                           color=WHITE if on_img else T.head_col, hot=T.img_hot if on_img else T.head_hot,
                           hot_words=("trampa", "mito", "realidad", "3", "30", "error", "caso", "delegar", "contratar",
                                      "entregar", "normativa", "cte", "loe", "despacho", "proyecto"),
                           stroke=0, shadow=on_img)
    hook_logo = fx.logo(70, T.head_col, T.label if T.name != "carbon" else ARENA)
    hook_logo_img = fx.logo(70, WHITE, T.img_hot)
    cards = []
    if fmt not in ("repaso_express", "dato", "comparativa", "mito_realidad", "grafico", "caso_coste") and fmt not in QB.POINTS_ONLY:
        cards = [QuestionCard(Q, QB.tema_titulo(Q["tema"]).upper(), f"{i + 1}/3" if fmt == "simulacro_3" else None)
                 for i, Q in enumerate(items)]
    expl = stmt = pts = scene_card = cmp_card = chart = None
    fronts, backs = [], []
    if fmt == "repaso_express":
        for i, F in enumerate(items):
            fronts.append(TextCard(f"FICHA {i + 1}/{len(items)}", F["q"], ref_label(F), body_size=62))
            backs.append(TextCard("RESPUESTA", F["a"], ref_label(F), body_size=54, title_color=T.ok_col,
                                  title_fg=T.ok_text if T.ok_mode == "fill" else T.ink))
    elif fmt == "grafico":
        chart = ChartCard(S["titulo_norma"], S["barras"], S["conclusion"], ref_label(P))
    elif fmt == "caso_coste":                          # barras de UDA en oro, la del empleado en gris
        chart = ChartCard(S["titulo_norma"], S["barras"], S["conclusion"], ref_label(P),
                          hi_set=[k for k, b in enumerate(S["barras"]) if b["etiqueta"].startswith("Delegar")])
        pts = TextCard(None, None, None, big=S["puntos_titulo"], bullets=S["puntos"], icons=True, body_size=58)
    elif fmt in QB.POINTS_ONLY or fmt in ("dato", "comparativa", "mito_realidad"):
        if fmt == "mito_realidad":
            stmt = TextCard("¿MITO O REALIDAD?", S["afirmacion"], None, body_size=70)
            expl = TextCard("¿POR QUÉ?", S["explicacion"], ref_label(P), body_size=50)
        if fmt in QB.POINTS_ONLY:
            pts = TextCard(None, None, ref_label(P), big=S["titulo_norma"], bullets=S["puntos"], icons=True, body_size=58)
        if fmt == "caso_despacho" and hook_bg is None:
            scene_card = TextCard("CASO DE DESPACHO", S["escena"], None, body_size=58)
        if fmt == "dato":
            stmt = TextCard("DATO DE PROYECTO", S["afirmacion"], None, body_size=66)
            expl = TextCard("¿POR QUÉ IMPORTA?", S["explicacion"], ref_label(P), body_size=50)
        if fmt == "comparativa":
            cmp_card = CompareCard(S["titulo_norma"], S["col_a"], S["col_b"], S["filas"], ref_label(P))
    else:
        corr = f"{P['letra']}) {P['op'][P['ok']]}"
        if fmt == "error_tipico":
            expl = TextCard("OJO CON LA TRAMPA", S["trampa_porque"], ref_label(P), top_line=corr, title_color=T.bad_col)
        elif fmt == "mito_realidad":
            expl = TextCard("¿POR QUÉ?", S["explicacion"], ref_label(P))
        elif "ex" in A:
            expl = TextCard("¿POR QUÉ?", S["explicacion"], ref_label(P), top_line=corr, body_size=52)
        if fmt == "mito_realidad":
            stmt = TextCard("¿MITO O REALIDAD?", S["afirmacion"], None, body_size=70)
        if fmt == "norma_30s":
            pts = TextCard(None, None, ref_label(P), big=S.get("titulo_norma"), bullets=S["puntos"])
        if fmt == "caso_despacho" and hook_bg is None:
            scene_card = TextCard("CASO DE DESPACHO", S["escena"], None, body_size=58)
    brand = fx.shadowed(brand_card(st), alpha=70)
    stamp_img = fx.pill(S.get("veredicto", "MITO"), 116, T.mito_col if S.get("veredicto") == "MITO" else T.real_col, WHITE if T.name != "negro" or S.get("veredicto") == "MITO" else NEGRO_,
                        padx=60, pady=26, outline=WHITE, radius=6) if fmt == "mito_realidad" else None
    n_items = len(items)
    score_img = fx.headline("¿Cuántas sabías?" if fmt == "repaso_express" else "¿Cuántas has acertado?", 104, 900, 3,
                            color=T.head_col, hot=T.head_hot, hot_words=("acertado?", "sabías?"), stroke=0, shadow=False)
    score_row = None
    if fmt in ("simulacro_3", "repaso_express"):
        labs = [f"{k}/{n_items}" for k in range(n_items + 1)]
        ps = [fx.pill(x, 46, T.badge_bg if x == labs[-1] else (255, 255, 255), T.badge_fg if x == labs[-1] else INK,
                      padx=24, pady=12, radius=T.pill_radius) for x in labs]
        score_row = Image.new("RGBA", (sum(p.width for p in ps) + 18 * (len(ps) - 1), ps[0].height), (0, 0, 0, 0)); x = 0
        for p in ps:
            score_row.alpha_composite(p, (x, 0)); x += p.width + 18
    comment_lab = fx.pill("COMENTA: A, B, C O D", 38, T.pill_bg, T.pill_fg, padx=30, pady=12, outline=T.pill_outline,
                          radius=T.pill_radius)
    reto_lab = fx.pill(st["reto_line"].upper(), 36, T.pill_bg, T.pill_fg, padx=30, pady=12, outline=T.pill_outline,
                       radius=T.pill_radius) if st.get("reto_line") else None
    save_lab = fx.pill(st["save_line"].upper(), 32, T.title_bg, T.title_fg, padx=26, pady=12, radius=T.pill_radius) \
        if st.get("save_line") else None

    def sub_img(k, tt, size=50, dark=False):
        """Subtítulo de la línea k (karaoke) en una banda."""
        n_ = lit(k, tt)
        if not n_:
            return None
        ink, dim, band_c = (WHITE, (170, 180, 190), (0, 0, 0, 150)) if dark else (T.sub_ink, T.sub_dim, T.sub_band)
        txt = fx.text_block(TXT[k], F900, int(size * st["caption_scale"]), 900, ink, lit=n_, dim=dim, align="center")
        b = Image.new("RGBA", (W - 20, txt.height + 64), (0, 0, 0, 0))
        if band_c[3]:
            ImageDraw.Draw(b).rounded_rectangle([30, 18, b.width - 30, b.height - 18], 38, fill=band_c)
        b.alpha_composite(txt, ((b.width - txt.width) // 2, 34))
        return b

    def card_at(img, tt, a, enter=0.35):
        p = eo((tt - a) / enter)
        return img, ctop(img.height) + img.height / 2 + (1 - p) * 140, p

    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + fx.enc_args(out), stdin=subprocess.PIPE)
    sh_cache = {}

    def shadow(img):
        if not T.shadow:
            return img
        k = id(img)
        if k not in sh_cache:
            if len(sh_cache) > 40: sh_cache.clear()
            sh_cache[k] = (fx.shadowed(img), img)
        return sh_cache[k][0]

    def flip(img_a, img_b, p):
        """Giro de ficha: anverso -> reverso (escala horizontal)."""
        src = img_a if p < 0.5 else img_b
        k = abs(math.cos(p * math.pi))
        return src.resize((max(2, int(src.width * k)), src.height), Image.BILINEAR)

    # ---- fotogramas fijos (carrusel de TikTok y base de las stories): uno por bloque, en su mejor momento
    caps, slides = {}, []
    for sg in SEG:
        k, a, b = sg["kind"], sg["a"], sg["b"]
        if k == "count":
            continue
        t_ = {"hook": a + 0.8 * (b - a), "reveal": a + min(1.2, b - a - 0.1), "stamp": a + min(1.0, b - a - 0.1),
              "cta": a + min(3.0, b - a - 0.2)}.get(k, b - 0.15)
        caps[int(t_ * FPS)] = (k, out.replace(".mp4", f"_slide{len(caps) + 1:02d}_{k}.png"))
    story_base = None
    for fi in range(int(total * FPS)):
        tt = fi / FPS
        sg = next((s for s in SEG if s["a"] <= tt < s["b"]), SEG[-1])
        lt = tt - sg["a"]; kind = sg["kind"]
        if kind in ("hook", "scene") and hook_bg is not None:
            fr = hook_bg.frame(tt)
            grad = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(grad)
            for yy in range(0, H, 8):
                a_ = int(200 * max(0, (yy - H * 0.35) / (H * 0.65)) ** 1.3 + 90 * max(0, 1 - yy / 420))
                gd.rectangle([0, yy, W, yy + 8], fill=(0, 0, 0, min(220, a_)))
            fr.alpha_composite(grad)
        else:
            fr = bg.frame(tt)
        if kind != "cta":
            fx.paste_center(fr, bdg, 60 + bdg.width / 2, 312, alpha=eo(tt / 0.4))
            fx.paste_center(fr, web_dark if (kind in ("hook", "scene") and hook_bg is not None) else web_img, W / 2, 222)
        if kind == "hook":
            y_h = 860 if hook_bg is not None else 820
            fx.paste_center(fr, hook_logo_img if hook_bg is not None else hook_logo, W / 2, y_h - hook_img.height / 2 - 120,
                            alpha=min(1, lt / 0.3))
            fx.paste_center(fr, hook_img, W / 2, y_h, eob(lt / 0.35), min(1, lt / 0.15))
            s_ = sub_img("hook", tt, dark=hook_bg is not None)
            if s_ is not None: fx.paste_center(fr, s_, W / 2, 1300)
        elif kind == "scene":
            if scene_card is not None:
                img = scene_card.render(lit=lit("esc", tt)); im_, y, p = card_at(img, tt, sg["a"])
                fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
            else:
                fx.paste_center(fr, fx.pill("CASO DE DESPACHO", 38, T.img_hot, CARBON, padx=30, pady=12, radius=4), W / 2, 1060, eob(lt / 0.3))
                s_ = sub_img("esc", tt, 52, dark=True)
                if s_ is not None: fx.paste_center(fr, s_, W / 2, 1260)
        elif kind in ("fq", "fa"):
            i = sg["q"]
            if kind == "fq":
                img = fronts[i].render(lit=lit(f"fq{i}", tt)); im_, y, p = card_at(img, tt, sg["a"])
                fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
            else:
                p = clamp(lt / 0.45)
                img = flip(fronts[i].render(), backs[i].render(lit=lit(f"fa{i}", tt)), p) if p < 1 else backs[i].render(lit=lit(f"fa{i}", tt))
                h_ = max(fronts[i].h, backs[i].h) if p < 1 else img.height
                fx.paste_center(fr, shadow(img) if p >= 1 else img, W / 2, ctop(h_) + h_ / 2 if p < 1 else ctop(img.height) + img.height / 2)
        elif kind in ("question", "count", "reveal") and stmt is None:
            qi = sg.get("q", 0); C = cards[qi]
            if kind == "question":
                act = None
                for k, s0 in enumerate(sg.get("ostarts") or []):
                    if s0 <= tt < s0 + D[f"o{k}"] + 0.15: act = k          # solo mientras se lee esa opción
                img = C.render(lit=lit(f"q{qi}" if fmt == "simulacro_3" else "q", tt), active=act)
                im_, y, p = card_at(img, tt, sg["a"])
                fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
            elif kind == "count":
                img = C.render()
                fx.paste_center(fr, shadow(img), W / 2, ctop(img.height) + img.height / 2)
                remain = sg["n"] - int(lt); ph = lt % 1
                fx.paste_center(fr, ring(remain, 1 - lt / sg["n"]), W - 150, 300, 1 + 0.12 * max(0, 1 - ph * 5))
                cy = ctop(img.height) + img.height + 58
                lab = reto_lab if (reto_lab is not None and int(lt / 2.5) % 2 == 1) else comment_lab
                if cy + 30 < fx.SAFE_BOTTOM + 20:
                    fx.paste_center(fr, lab, W / 2, cy, eob((lt % 2.5) / 0.3))
            else:
                prog = clamp(lt / 0.45)
                tr = QB.LETTERS.index(sg["trampa"]) if sg.get("trampa") else None
                img = C.render(reveal=prog, trampa=tr, show_trampa=clamp((lt - 0.6) / 0.3) if tr is not None else 0)
                top_ = ctop(img.height)
                fx.paste_center(fr, shadow(img), W / 2, top_ + img.height / 2, 1 + 0.02 * math.sin(min(1, lt / 0.3) * math.pi))
                burst(fr, W / 2 - CARD_W / 2 + C.ok_center[0], top_ + C.ok_center[1], lt, seed=qi)
        elif kind == "statement" or (kind in ("count", "stamp") and stmt is not None):
            if kind == "statement":
                img = stmt.render(lit=lit("st", tt)); im_, y, p = card_at(img, tt, sg["a"])
                fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
            else:
                img = stmt.render(); fx.paste_center(fr, shadow(img), W / 2, ctop(img.height) + img.height / 2)
                if kind == "count":
                    remain = sg["n"] - int(lt); ph = lt % 1
                    fx.paste_center(fr, ring(remain, 1 - lt / sg["n"]), W - 150, 300, 1 + 0.12 * max(0, 1 - ph * 5))
                    lab = fx.pill("COMENTA: ¿MITO O REALIDAD?", 38, T.pill_bg, T.pill_fg, padx=30, pady=12, outline=T.pill_outline)
                    if ctop(img.height) + img.height + 110 < fx.SAFE_BOTTOM:
                        fx.paste_center(fr, lab, W / 2, ctop(img.height) + img.height + 70)
                else:
                    fx.paste_center(fr, stamp_img, W / 2, ctop(img.height) + img.height / 2, 1.6 - 0.6 * eob(lt / 0.3), min(1, lt / 0.1), -8)
                    burst(fr, W / 2, ctop(img.height) + img.height / 2, lt)
        elif kind == "explain":
            img = expl.render(lit=lit("ex", tt)); im_, y, p = card_at(img, tt, sg["a"])
            fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
            if save_lab is not None and lt > 1.0 and y + img.height / 2 + 80 < fx.SAFE_BOTTOM:
                fx.paste_center(fr, save_lab, W / 2, y + img.height / 2 + 70, eob((lt - 1.0) / 0.35))
        elif kind == "chart":
            grow = [clamp((tt - s0) / 0.9) for s0 in sg["starts"]]
            img = chart.render(grow=grow, show_conc=clamp((tt - sg["cstart"]) / 0.3), lit=lit("conc", tt))
            im_, y, p = card_at(img, tt, sg["a"])
            fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
        elif kind == "compare":
            nr = sum(1 for s0 in sg["starts"] if tt >= s0 - 0.1)
            img = cmp_card.render(n_rows=nr, hot=nr - 1 if nr and tt < sg["starts"][nr - 1] + D[f"c{nr - 1}"] + 0.2 else None)
            im_, y, p = card_at(img, tt, sg["a"])
            fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
        elif kind == "points":
            nb = sum(1 for s0 in sg["starts"] if tt >= s0 - 0.1)
            bl = lit(f"p{max(0, nb - 1)}", tt) if nb else None
            img = pts.render(n_bullets=max(0, nb), bullet_lit=bl); im_, y, p = card_at(img, tt, sg["a"])
            fx.paste_center(fr, shadow(im_), W / 2, y, alpha=p)
        elif kind == "score":
            fx.paste_center(fr, score_img, W / 2, 720, eob(lt / 0.35))
            fx.paste_center(fr, score_row, W / 2, 1000, eob((lt - 0.3) / 0.35))
            s_ = sub_img("fin", tt)
            if s_ is not None: fx.paste_center(fr, s_, W / 2, 1260)
        elif kind == "cta":
            fx.paste_center(fr, brand, W / 2, 330 + brand.height / 2 - 66, eob(lt / 0.4), min(1, lt / 0.2))
            if st.get("share_line") and lt > 1.2:
                fx.paste_center(fr, fx.pill(st["share_line"].upper(), 32, T.badge_bg, T.badge_fg, padx=26, pady=12, radius=4), W / 2, 1225,
                                eob((lt - 1.2) / 0.35))
            top_, sz = 1262, 44                    # el subtítulo nunca entra en los 420 px inferiores (interfaz de la red)
            s_ = sub_img("cta", tt, sz)
            while s_ is not None and s_.height > fx.SAFE_BOTTOM - 10 - top_ and sz > 30:
                sz -= 3; s_ = sub_img("cta", tt, sz)
            if s_ is not None: fx.paste_center(fr, s_, W / 2, top_ + s_.height / 2)
        if fi in caps and len(slides) < 12:
            name, path = caps[fi]
            fr.convert("RGB").save(path); slides.append(path)
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait(); os.remove(wav)
    for want in ("question", "statement", "fq", "scene", "hook"):        # base de la story: sin desvelar la respuesta
        story_base = next((p for p in slides if f"_{want}.png" in p), None)
        if story_base:
            break
    if proc.returncode:
        raise RuntimeError("ffmpeg falló al codificar el reel")

    cap = caption_text(fmt, items, S, rng, st)
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    return {"formato": fmt, "estilo": T.name, "ids": [Q["id"] for Q in items], "temas": [Q["tema"] for Q in items],
            "respuestas": [Q.get("letra") for Q in items if Q.get("letra")],
            "veredicto": S.get("veredicto"), "hook": S["screen_hook"], "hook_line": S["hook_line"],
            "duration": round(total, 1), "timeline": [(s_["kind"], round(s_["a"], 2)) for s_ in SEG],
            "thumb_ms": int(1200), "slides": slides, "story_base": story_base or (slides[0] if slides else None)}


def mock_script(fmt, items):
    import writer
    S = writer.template(fmt, items)
    P = items[0]
    keep = writer.verified(fmt, P)
    S.update({"trampa": next(L for L in "ABCD" if L != P.get("letra", "A")),
              "trampa_porque": "Parece correcta porque suena a regla general, pero la norma dice otra cosa en este caso.",
              "afirmacion": "Esta es una afirmación de prueba para el formato mito o realidad.", "veredicto": "MITO",
              "titulo_norma": P.get("titulo") or QB.tema_corto(P.get("tema")), "explicacion": S.get("explicacion") or "Explicación de prueba.",
              "escena": "Te entra un encargo de doce adosados y tu equipo ya va a tope con dos entregas esta semana.",
              "puntos": list(P["puntos"]) if P.get("puntos") else ["Primer punto clave de prueba del vídeo",
                                                                  "Segundo punto clave algo más largo de prueba",
                                                                  "Tercer punto clave de prueba"]})
    S.update(keep)
    return S


if __name__ == "__main__":
    fmt = sys.argv[1] if len(sys.argv) > 1 else "test_normativa"
    out = sys.argv[2] if len(sys.argv) > 2 else f"out/test_{fmt}.mp4"
    estilo = sys.argv[3] if len(sys.argv) > 3 else "piedra"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if fmt == "repaso_express":
        items = QB.pick_fichas(seed=7)
    else:
        n = 3 if fmt == "simulacro_3" else 1
        items = [QB.prepare(q, 7) for q in QB.candidates(fmt, None, seed=7)[:n]]
    img = None
    if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
        img = Image.open(sys.argv[4])
    S = mock_script(fmt, items)
    print(json.dumps(build(fmt, items, S, 7, out, {"estilo": estilo}, image=img), ensure_ascii=False, indent=1))
