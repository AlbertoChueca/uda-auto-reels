"""Infografías animadas para los reels de UDA (negro y oro): nada de tablas, cada idea es un gráfico a pantalla completa.

Cada escena es una función scene_xxx(T, data, lt, ...) -> imagen RGBA de W×H (transparente) que se pinta sobre el fondo
(la foto de arquitectura del gancho, oscurecida y desenfocada). lt = segundos desde que empieza la escena.

  stack     tu estudio hoy: 3 encargos en marcha (barras de avance) + el nuevo que entra, latiendo en oro
  towers    cuánto cuesta delegar: tres edificios dorados (parcial, P. Ejecución, Básico + Ejecución) que crecen
  versus    contratar (gris) frente a delegar (oro), con las cifras contando
  donut     anillo que se llena: «hasta un 67 % más de tiempo» (web de UDA)
  timeline  del primer contacto a tu firma: reunión, presupuesto cerrado en 24 h, entrega, tu firma
  quote     testimonio literal de un estudio (web de UDA) sobre la foto

Todas las cifras llegan ya calculadas o citadas (casos.py / web): aquí solo se dibujan.
"""
import math
from PIL import Image, ImageDraw, ImageFilter

import fx
from fx import W, H, F_BOLD, F_REG, clamp, eo, eob

TOP = 400              # debajo de la web y la etiqueta
BOTTOM = 1480          # zona segura inferior (la interfaz de la red tapa los 420 px de abajo)


def _txt(text, size, maxw, col, bold=True, align="center"):
    return fx.text_block(text, F_BOLD if bold else F_REG, size, maxw, col, align=align)


def _paste(c, im, cx, y, alpha=1.0):
    """Pega centrado en x con la parte superior en y."""
    if im is None or alpha <= 0.01:
        return
    if alpha < 1:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda a: int(a * alpha)))
    c.alpha_composite(im, (int(cx - im.width / 2), int(y)))


def _label(T, text, y, c, alpha=1.0):
    lab = fx.spaced(text.upper(), F_BOLD, 34, T.label, 0.10)
    _paste(c, lab, W / 2, y, alpha)
    ImageDraw.Draw(c).line([(W / 2 - 60, y + lab.height + 14), (W / 2 + 60, y + lab.height + 14)],
                           fill=tuple(T.label[:3]) + (int(255 * alpha),), width=3)
    return y + lab.height + 40


def _glow(size, col, a=90):
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([size * .2, size * .2, size * .8, size * .8], fill=tuple(col[:3]) + (a,))
    return g.filter(ImageFilter.GaussianBlur(size * .12))


def _num(v, p):
    """Cifra que cuenta hasta v (formato español con punto de miles)."""
    x = v * eo(p)
    return f"{x:,.0f}".replace(",", ".")


def _panel(c, box, T, alpha=235, rule=True):
    d = ImageDraw.Draw(c)
    d.rounded_rectangle(box, 10, fill=tuple(T.card_fill[:3]) + (alpha,), outline=tuple(T.card_outline[:3]) + (255,) if T.card_outline else None, width=2)
    if rule:
        d.rectangle([box[0] + 6, box[1], box[2] - 6, box[1] + 6], fill=T.top_rule or T.label)


# ------------------------------------------------------------------ escenas
def scene_stack(T, d, lt):
    """d: {"titulo", "nuevo": "Unifamiliar · 180 m²"}"""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Tu estudio hoy"), TOP + 20, c, clamp(lt / 0.3))
    tw, th, gap = 440, 330, 30
    x0 = (W - 2 * tw - gap) / 2; y0 = y + 30
    fills = (0.82, 0.55, 0.68)
    for k in range(4):
        p = eob(clamp((lt - 0.15 - 0.22 * k) / 0.45))
        if p <= 0:
            continue
        col, row = k % 2, k // 2
        bx, by = x0 + col * (tw + gap), y0 + row * (th + gap) + (1 - p) * 60
        box = [bx, by, bx + tw, by + th]
        if k < 3:
            _panel(c, box, T, rule=False)
            ic = fx.icon("plan", 92, T.dim)
            c.alpha_composite(ic, (int(bx + 36), int(by + 40)))
            c.alpha_composite(_txt(f"Encargo {k + 1}", 46, 300, T.ink, align="left"), (int(bx + 150), int(by + 60)))
            c.alpha_composite(_txt("en marcha", 36, 300, (150, 144, 132), bold=False, align="left"), (int(bx + 150), int(by + 118)))
            bw = tw - 72; f = fills[k] * eo(clamp((lt - 0.6 - 0.2 * k) / 1.2))
            dr.rounded_rectangle([bx + 36, by + 230, bx + 36 + bw, by + 262], 8, fill=(46, 44, 40))
            dr.rounded_rectangle([bx + 36, by + 230, bx + 36 + max(14, bw * f), by + 262], 8, fill=_mix(T.ink, T.faded, .35))
            c.alpha_composite(_txt(f"{int(fills[k] * 100 * eo(clamp((lt - 0.6 - 0.2 * k) / 1.2)))} %", 30, 120, T.dim, align="left"),
                              (int(bx + 36), int(by + 180)))
        else:                                                   # el encargo nuevo: oro, latiendo
            pulse = 0.5 + 0.5 * math.sin(lt * 4.0)
            g = _glow(int(tw * 1.5), T.label, int(60 + 50 * pulse))
            c.alpha_composite(g, (int(bx + tw / 2 - g.width / 2), int(by + th / 2 - g.height / 2)))
            dr.rounded_rectangle(box, 10, fill=(30, 27, 20, 245), outline=T.label, width=4)
            c.alpha_composite(_txt("NUEVO", 40, 300, T.label, align="left"), (int(bx + 36), int(by + 36)))
            sz = 46
            while sz > 30 and max(fx.font(F_BOLD, sz).getlength(w_) for w_ in d["nuevo"].split()) > tw - 150:
                sz -= 2                                         # ninguna palabra se sale de la tarjeta («Equipamiento»)
            c.alpha_composite(_txt(d["nuevo"], sz, tw - 150, T.ink, align="left"), (int(bx + 36), int(by + 96)))
            q = fx.font(F_BOLD, 150); dr.text((bx + tw - 130, by + th - 190), "?", font=q, fill=T.label)
    return c


def _mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a[:3], b[:3]))


def scene_towers(T, d, lt, starts, cstart):
    """Barras como edificios: d = {"titulo", "barras": [...], "conclusion"}. Solo las de UDA (sin la del empleado)."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d["titulo"], TOP + 20, c, clamp(lt / 0.3))
    bars = d["barras"]; n = len(bars)
    base = 1230; hmax = base - y - 250
    vmax = max(b["valor"] for b in bars)
    bw = 200; gap = (W - 220 - n * bw) / max(1, n - 1)
    dr.line([(100, base), (W - 100, base)], fill=tuple(T.label[:3]) + (180,), width=3)
    for k, b in enumerate(bars):
        p = clamp((lt - starts[k]) / 1.0)
        x = 110 + k * (bw + gap)
        hh = max(6, hmax * b["valor"] / vmax * eo(p))
        top = base - hh
        hot = k == n - 1 or d.get("hot") == k
        col = T.label if hot else _mix(T.label, (60, 56, 50), 0.45)
        if p > 0:
            dr.rectangle([x, top, x + bw, base], fill=col)
            for wy in range(int(top + 22), int(base - 18), 34):           # ventanas: parece un edificio
                for wx in range(int(x + 22), int(x + bw - 30), 40):
                    dr.rectangle([wx, wy, wx + 20, wy + 16], fill=(20, 18, 14, 150))
            dr.rectangle([x - 6, top - 10, x + bw + 6, top], fill=_mix(col, (255, 255, 255), 0.25))
            vs = 64 if n <= 3 else 50                                 # 4 barras: cifra más pequeña, sin pisarse
            v = _txt(b["texto"], vs, bw + gap - 12, T.ink)            # cifra fija (sin contar: no parpadea)
            _paste(c, v, x + bw / 2, top - v.height - 18, clamp(p * 2))
            lab = _txt(b["etiqueta"], 38 if n <= 3 else 34, (bw + 60) if n <= 3 else (bw + gap - 14),
                       T.ink if hot else (160, 154, 142), bold=hot)
            _paste(c, lab, x + bw / 2, base + 18, clamp(p * 2))
    if lt > cstart and d.get("conclusion"):
        p = eob(clamp((lt - cstart) / 0.4))
        pill = fx.pill(d["conclusion"], 36, T.label, fx.NEGRO, padx=30, pady=16, radius=6)
        if pill.width > W - 80:
            pill = pill.resize((W - 80, int(pill.height * (W - 80) / pill.width)), Image.LANCZOS)
        _paste(c, pill, W / 2, y - 6 + (1 - p) * 20, clamp(p))
    return c


def scene_versus(T, d, lt, b_start):
    """d = {"a_tit","a_num","a_txt","b_tit","b_num","b_txt"} (a = contratar, gris; b = delegar, oro)."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Contratar o delegar"), TOP + 20, c, clamp(lt / 0.3))
    cw = 420; top = y + 30; bot = 1400                 # márgenes laterales: fuera de los botones de la app
    for side in (0, 1):
        st = 0.1 if side == 0 else b_start
        p = eo(clamp((lt - st) / 0.5))
        if p <= 0:
            continue
        x = 100 if side == 0 else W - 100 - cw
        x += (-1 if side == 0 else 1) * (1 - p) * 120
        gold = side == 1
        box = [x, top, x + cw, bot]
        if gold:
            g = _glow(900, T.label, 50); c.alpha_composite(g, (int(x + cw / 2 - 450), int((top + bot) / 2 - 450)))
        dr.rounded_rectangle(box, 12, fill=(28, 25, 19, 240) if gold else (26, 26, 26, 235),
                             outline=T.label if gold else (70, 68, 64), width=4 if gold else 2)
        col = T.label if gold else (150, 146, 138)
        ic = fx.icon("plan" if gold else "team", 150, col)
        c.alpha_composite(ic, (int(x + cw / 2 - 75), int(top + 50)))
        tit = _txt(d["b_tit" if gold else "a_tit"], 46, cw - 60, col)
        _paste(c, tit, x + cw / 2, top + 230)
        num = d["b_num" if gold else "a_num"]
        pn = clamp((lt - st - 0.3) / 1.0)
        shown = num
        nm = _txt(shown, 84 if len(num) < 10 else 42, cw - 30, T.ink)
        _paste(c, nm, x + cw / 2, top + 380 + (1 - eo(pn)) * 20, clamp(pn * 1.5))
        sub = _txt(d["b_txt" if gold else "a_txt"], 40, cw - 70, T.ink if gold else (150, 146, 138), bold=False)
        _paste(c, sub, x + cw / 2, top + 560, clamp((lt - st - 0.6) / 0.4))
        mark = fx.icon("check" if gold else "cross", 90, T.label if gold else (130, 126, 120))
        c.alpha_composite(mark, (int(x + cw / 2 - 45), int(bot - 120)))
    p = eob(clamp((lt - b_start + 0.2) / 0.4))
    if p > 0:
        r = 70 * p
        dr.ellipse([W / 2 - r, (top + bot) / 2 - r, W / 2 + r, (top + bot) / 2 + r], fill=fx.NEGRO, outline=T.label, width=4)
        vs = _txt("VS", 48, 200, T.label)
        if p > 0.6:
            _paste(c, vs, W / 2, (top + bot) / 2 - 30)
    return c


def _count_text(num, p):
    """Anima una cifra tipo «3.333–3.917 €» o «2.144 €» contando desde 0."""
    import re
    def rep(m):
        v = int(m.group(0).replace(".", ""))
        return f"{v * eo(p):,.0f}".replace(",", ".")
    return re.sub(r"\d[\d.]*", rep, num)


def scene_donut(T, d, lt):
    """d = {"pct": 67, "grande": "67 %", "texto", "prefijo": "hasta un", "fuente"}"""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Tiempo para lo que vale"), TOP + 20, c, clamp(lt / 0.3))
    cx, cy, R = W / 2, y + 400, 300
    p = eo(clamp((lt - 0.3) / 1.6))
    g = _glow(900, T.label, int(40 + 30 * p)); c.alpha_composite(g, (int(cx - 450), int(cy - 450)))
    dr.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(50, 47, 42), width=48)
    dr.arc([cx - R, cy - R, cx + R, cy + R], -90, -90 + 360 * d["pct"] / 100 * p, fill=T.label, width=48)
    pre = _txt(d.get("prefijo", ""), 46, 400, (160, 154, 142), bold=False)
    _paste(c, pre, cx, cy - 150)
    big = _txt(f"{d['pct']} %", 150, 600, T.ink)
    _paste(c, big, cx, cy - 95, clamp(p * 1.4))
    t = _txt(d["texto"], 56, 900, T.ink)
    _paste(c, t, cx, cy + R + 70, clamp((lt - 1.2) / 0.5))
    if d.get("fuente"):
        f = _txt(d["fuente"], 30, 900, (140, 134, 124), bold=False)
        _paste(c, f, cx, cy + R + 90 + t.height, clamp((lt - 1.4) / 0.5))
    return c


def scene_timeline(T, d, lt, starts):
    """d = {"pasos": [(icono, titulo, detalle), ...]} vertical, la línea se dibuja paso a paso."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Así de fácil"), TOP + 20, c, clamp(lt / 0.3))
    pasos = d["pasos"]; n = len(pasos)
    x = 190; y0 = y + 60; step = min(230, (1420 - y0) / max(1, n - 1) if n > 1 else 0)
    for k, (ic, tit, det) in enumerate(pasos):
        p = clamp((lt - starts[k]) / 0.5)
        yy = y0 + k * step
        if k < n - 1:
            q = clamp((lt - starts[k] - 0.3) / max(0.4, (starts[k + 1] - starts[k]) - 0.3))
            dr.line([(x, yy + 60), (x, yy + 60 + (step - 120) * eo(q))], fill=T.label, width=5)
        if p <= 0:
            continue
        r = 60 * eob(p)
        dr.ellipse([x - r, yy - r, x + r, yy + r], fill=(30, 27, 20), outline=T.label, width=4)
        if p > 0.5:
            i = fx.icon(ic, 64, T.label); c.alpha_composite(i, (int(x - 32), int(yy - 32)))
        a = clamp(p * 1.5)
        tt = _txt(tit, 54, 720, T.ink, align="left")
        dd = _txt(det if not d.get("compact") else " ", 40, 720, (160, 154, 142), bold=False, align="left")
        for im_, oy in ((tt, yy - 48), (dd, yy + 10)):
            im2 = im_.copy(); im2.putalpha(im2.getchannel("A").point(lambda v: int(v * a)))
            c.alpha_composite(im2, (int(x + 100 + (1 - a) * 40), int(oy)))
    return c


def scene_quote(T, d, lt):
    """d = {"texto": testimonio literal, "autor"}"""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Lo que dicen los estudios"), TOP + 20, c, clamp(lt / 0.3))
    p = eo(clamp(lt / 0.6))
    q = fx.font(F_BOLD, 260); dr.text((90, y - 10), "“", font=q, fill=tuple(T.label[:3]) + (int(255 * p),))
    words = d["texto"].split(); n = int(len(words) * clamp((lt - 0.3) / max(1.0, d.get("dur", 6) * 0.75)))
    body = fx.text_block(d["texto"], F_BOLD, 60, 880, T.ink, lit=n, dim=(90, 86, 80), align="left")
    c.alpha_composite(body, (100, int(y + 200)))
    a = _txt("— " + d.get("autor", "Estudio que colabora con UDA"), 40, 880, T.label, bold=False, align="left")
    _paste(c, a, 100 + 440, y + 230 + body.height, clamp((lt - 1.0) / 0.5))
    return c


def scene_delegable(T, d, lt, b_start):
    """Qué delegas (oro, ✓) y qué sigue siendo tuyo (crema, pluma): d = {"si": [...], "no": [...]}."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Qué delegas y qué sigue siendo tuyo"), TOP + 20, c, clamp(lt / 0.3))
    x0, x1 = 100, W - 100
    # bloque 1: lo que delegas
    p = eo(clamp((lt - 0.2) / 0.4))
    _panel(c, [x0, y + 10, x1, y + 10 + 110 + 82 * len(d["si"])], T)
    _paste(c, _txt("LO DELEGAS EN UDA", 40, 800, T.label, align="left"), x0 + 40 + 400, y + 40, p)
    for k, it in enumerate(d["si"]):
        q = eob(clamp((lt - 0.4 - 0.25 * k) / 0.35))
        if q <= 0:
            continue
        yy = y + 120 + 82 * k
        c.alpha_composite(fx.icon("check", 56, T.label), (x0 + 40, int(yy)))
        im = _txt(it, 44, 760, T.ink, align="left")
        _paste(c, im, x0 + 120 + 380 + (1 - q) * 30, yy + 4, q)
    # bloque 2: lo que sigue siendo tuyo
    y2 = y + 10 + 110 + 82 * len(d["si"]) + 40
    p = eo(clamp((lt - b_start) / 0.4))
    if p > 0:
        dr.rounded_rectangle([x0, y2, x1, y2 + 110 + 82 * len(d["no"])], 10, fill=(24, 23, 21, 235), outline=(70, 68, 64), width=2)
        _paste(c, _txt("SIGUE SIENDO TUYO", 40, 800, (200, 194, 182), align="left"), x0 + 40 + 400, y2 + 30, p)
        for k, it in enumerate(d["no"]):
            q = eob(clamp((lt - b_start - 0.2 - 0.25 * k) / 0.35))
            if q <= 0:
                continue
            yy = y2 + 110 + 82 * k
            c.alpha_composite(fx.icon("shield", 56, (200, 194, 182)), (x0 + 40, int(yy)))
            _paste(c, _txt(it, 44, 760, (200, 194, 182), align="left"), x0 + 120 + 380 + (1 - q) * 30, yy + 4, q)
    return c


def scene_cargas(T, d, lt, starts):
    """Lo que no sale en la nómina: 4 losas grises que aparecen una a una y, al final, el sello dorado «Con UDA, nada de eso».
    starts: [titular, formar, baja, nómina, despido, uda]"""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Y no es solo dinero"), TOP + 20, c, clamp(lt / 0.3))
    tw, th, gap = 430, 380, 24
    x0 = (W - 2 * tw - gap) / 2; y0 = y + 20
    grey = (190, 184, 172)
    done = lt >= starts[-1] if len(starts) > 5 else False
    for k, (ic, tit, det) in enumerate(d["items"]):
        st = starts[k + 1] if len(starts) > k + 1 else 0.3 + 0.4 * k
        p = eob(clamp((lt - st) / 0.4))
        if p <= 0:
            continue
        col, row = k % 2, k // 2
        bx, by = x0 + col * (tw + gap), y0 + row * (th + gap) + (1 - p) * 50
        dr.rounded_rectangle([bx, by, bx + tw, by + th], 10, fill=(26, 25, 23, 238), outline=(78, 74, 68), width=2)
        c.alpha_composite(fx.icon(ic, 110, grey if d.get("tachar", True) else T.label), (int(bx + 40), int(by + 40)))
        ti = _txt(tit, 46, tw - 80, (236, 230, 218), align="left")
        c.alpha_composite(ti, (int(bx + 40), int(by + 166)))
        if not d.get("compact"):                              # modo compacto: solo el titular de cada losa
            c.alpha_composite(_txt(det, 34, tw - 80, (150, 144, 132), bold=False, align="left"),
                              (int(bx + 40), int(by + 166 + ti.height + 4)))
        if done and d.get("tachar", True):                    # tachado dorado: con UDA desaparece (solo en costes)
            q = eo(clamp((lt - starts[-1] - 0.1 * k) / 0.35))
            dr.line([(bx + 30, by + th / 2), (bx + 30 + (tw - 60) * q, by + th / 2)], fill=T.label, width=7)
    if done:
        p = eob(clamp((lt - starts[-1]) / 0.4))
        pill = fx.pill(d.get("uda", "Con UDA, nada de eso"), 54, T.label, fx.NEGRO, padx=40, pady=22, radius=6)
        _paste(c, pill, W / 2, y0 + 2 * th + gap + 50 + (1 - p) * 30, clamp(p))
    return c


# ------------------------------------------------------------------ tests, encuestas y verdadero/falso (interacción)
def _center_v(c, im, x, cy):
    """Pega im con su TINTA (no su caja) centrada en vertical en cy."""
    bb = im.getbbox() or (0, 0, im.width, im.height)
    c.alpha_composite(im, (int(x), int(cy - (bb[1] + bb[3]) / 2)))


def _opt_rows(T, c, d, y, lt, starts, reveal=None):
    """Opciones en filas (letra en círculo + texto). reveal: índice correcto (oro) o -1 (encuesta: todas neutras)."""
    dr = ImageDraw.Draw(c)
    ops = d["opciones"]; n = len(ops)
    x0, x1 = 100, W - 100; gap = 22; fs = 46 if n > 2 else 54
    ims = []
    for k, o in enumerate(ops):
        ok = reveal is not None and reveal >= 0 and k == reveal
        dim = reveal is not None and reveal >= 0 and k != reveal
        col = fx.NEGRO if ok else ((120, 116, 108) if dim else T.ink)
        ims.append((_txt(o, fs, x1 - x0 - 230, col, align="left"), ok, dim))
    rh = max([128 if n > 2 else 150] + [im.height + 44 for im, _, _ in ims])   # filas de dos líneas: más altas
    for k, (im, ok, dim) in enumerate(ims):
        p = eob(clamp((lt - (starts[k] if k < len(starts) else 0)) / 0.35)) if reveal is None else 1.0
        if p <= 0:
            continue
        yy = y + k * (rh + gap) + (1 - p) * 30
        fill = tuple(T.label[:3]) + (245,) if ok else (26, 25, 23, 150 if dim else 238)
        dr.rounded_rectangle([x0, yy, x1, yy + rh], 14, fill=fill, outline=(78, 74, 68) if not ok else None, width=2)
        cx, cy = x0 + 70, yy + rh / 2
        dr.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=fx.NEGRO if ok else (40, 38, 34), outline=T.label, width=3)
        L = d.get("letras", "ABCD")[k]
        lf = fx.font(F_BOLD, 44); bb = lf.getbbox(L)
        dr.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), L, font=lf, fill=T.label)
        _center_v(c, im, x0 + 135, cy)
        if ok:
            c.alpha_composite(fx.icon("check", 64, fx.NEGRO), (int(x1 - 90), int(cy - 32)))
    return y + n * (rh + gap)


def scene_pregunta(T, d, lt, starts, end):
    """Pregunta + opciones que aparecen al decirlas + cuenta atrás con «Comenta tu respuesta»."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    y = _label(T, d.get("titulo", "Test de arquitecto"), TOP + 20 - 120, c, clamp(lt / 0.3))
    q = _txt(d["pregunta"], 66, 900, T.ink)
    _paste(c, q, W / 2, y + 10, clamp((lt - starts[0]) / 0.3))
    y2 = y + 10 + q.height + 50
    y3 = _opt_rows(T, c, d, y2, lt, starts[1:1 + len(d["opciones"])])
    cst = starts[-1]
    if lt >= cst:
        p = eob(clamp((lt - cst) / 0.4))
        pill = fx.pill(d.get("cta", "Comenta tu respuesta"), 50, T.label, fx.NEGRO, padx=40, pady=20, radius=6)
        _paste(c, pill, W / 2, y3 + 30 + (1 - p) * 30, clamp(p))
        if d.get("segundos"):
            span = max(1.0, end - cst - 0.3); frac = clamp((lt - cst) / span)
            rem = max(1, math.ceil(d["segundos"] * (1 - frac)))
            R = 52; cx, cy = W / 2 + pill.width / 2 + 30 + R, y3 + 30 + pill.height / 2   # a la derecha del botón
            if True:
                dr.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(24, 22, 19, 230))
                dr.arc([cx - R + 8, cy - R + 8, cx + R - 8, cy + R - 8], -90, -90 + 360 * (1 - frac), fill=T.label, width=12)
                f = fx.font(F_BOLD, 50); t = str(rem); bb = f.getbbox(t)
                dr.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), t, font=f, fill=T.ink)
    return c


def scene_respuesta(T, d, lt, starts):
    """La solución: la opción correcta en oro (o, en las encuestas, todas iguales) + explicación + invitación a guardar."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = _label(T, d.get("titulo", "La respuesta"), TOP + 20 - 120, c, clamp(lt / 0.3))
    q = _txt(d["pregunta"], 44, 900, (190, 184, 172), bold=False)
    _paste(c, q, W / 2, y)
    y2 = _opt_rows(T, c, d, y + q.height + 30, lt, [0] * 4, reveal=d.get("correcta", -1))
    if len(starts) > 1 and lt >= starts[1] and d.get("explicacion"):
        p = eo(clamp((lt - starts[1]) / 0.4))
        ex = _txt(d["explicacion"], 46, 880, T.ink, bold=False)
        _paste(c, ex, W / 2, y2 + 20 + (1 - p) * 20, p)
        y2 += ex.height + 40
    if lt >= starts[-1] and d.get("pill"):
        p = eob(clamp((lt - starts[-1]) / 0.4))
        pill = fx.pill(d["pill"], 46, T.label, fx.NEGRO, padx=36, pady=18, radius=6)
        _paste(c, pill, W / 2, y2 + 30 + (1 - p) * 20, clamp(p))
    return c


def render(T, sc, d, lt, sg):
    """Escena sc con sus datos d en el instante lt (sg: segmento del plan, con starts / bstart / cstart)."""
    starts = list(sg.get("starts") or [0.3 + 0.5 * k for k in range(8)])
    sc = sc.split("_")[0]                                 # «cargas_garantias», «timeline_pagos»: misma escena, otros datos
    if sc == "pregunta":
        return scene_pregunta(T, d, lt, starts, sg.get("b", 99) - sg.get("a", 0))
    if sc == "respuesta":
        return scene_respuesta(T, d, lt, starts)
    if sc == "stack":
        return scene_stack(T, d, lt)
    if sc == "towers":
        return scene_towers(T, d, lt, starts, sg.get("cstart", starts[-1]))
    if sc == "versus":
        return scene_versus(T, d, lt, sg.get("bstart", 1.5))
    if sc == "cargas":
        return scene_cargas(T, d, lt, starts)
    if sc == "delegable":
        return scene_delegable(T, d, lt, sg.get("bstart", 1.5))
    if sc == "donut":
        return scene_donut(T, d, lt)
    if sc == "timeline":
        return scene_timeline(T, d, lt, starts + [99] * 4)
    return scene_quote(T, dict(d, dur=sg.get("b", 7) - sg.get("a", 0)), lt)


def cover(T, ig, photo=None):
    """Portada del reel (la miniatura del perfil): foto + titular grande + la infografía principal ya completa.
    Todo lo importante cabe en el recorte 3:4 de la cuadrícula del perfil (y = 240-1680)."""
    from themes import ImageBG
    base = ImageBG(photo, dark=0.55, blur=6).frame(0) if photo is not None else T.background(1).frame(0)
    base = base.convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shade)
    for yy in range(0, H, 6):
        sd.rectangle([0, yy, W, yy + 6], fill=(0, 0, 0, int(90 + 110 * abs(yy / H - 0.45))))
    base.alpha_composite(shade)
    tag = fx.pill(ig["badge"], 34, T.label, fx.NEGRO, padx=26, pady=12, radius=4)
    _paste(base, tag, W / 2, 290)
    hl = fx.headline(ig["screen_hook"], 112, 960, 3, color=(242, 236, 224), hot=T.label,
                     hot_words=tuple(w.strip("¿?¡!.,") for w in ig["screen_hook"].split() if any(ch.isdigit() for ch in w))
                     + ("delegar", "Delegar", "contratar", "horas", "delega", "estudios"), stroke=0, shadow=True)
    _paste(base, hl, W / 2, 380)
    y0 = 380 + hl.height + 30
    prefer = {"caso": "towers", "contratar": "versus", "proceso": "timeline", "partidas": "towers", "actuaciones": "towers",
              "revit": "versus", "test": "pregunta", "vf": "pregunta", "encuesta": "pregunta",
              "atajos": "cargas_atajos"}.get(ig.get("variante"))           # cada temática, su propia portada
    main = prefer if prefer in ig["orden"] else next((x for b in ("towers", "versus", "donut", "cargas", "delegable",
                                                                  "timeline", "stack", "quote")
                                                      for x in ig["orden"] if x.split("_")[0] == b), None)
    if main:
        sg = {"starts": [0, 0.2, 0.4, 0.6, 0.8, 1.0], "cstart": 1.0, "bstart": 0.4, "a": 0, "b": 7}
        if main == "pregunta":                                     # portada del test: pregunta y opciones, sin la solución
            sg["starts"] = [0] * 7; sg["b"] = 30.0
        ov = render(T, main, ig["datos"][main], 30.0, sg)
        crop = ov.crop((0, (TOP - 60) if main == "pregunta" else (TOP + 70), W, 1490))   # sin la etiqueta pequeña
        k = min(0.9, (1560 - y0) / crop.height)
        crop = crop.resize((int(W * k), int(crop.height * k)), Image.LANCZOS)
        base.alpha_composite(crop, (int((W - crop.width) / 2), int(y0)))
    lg = fx.logo(56, (242, 236, 224), T.label)
    _paste(base, lg, W / 2, 1585)
    return base.convert("RGB")
