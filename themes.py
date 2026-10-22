"""Estilos visuales de los reels de UDA. Todos son editoriales y sobrios, con los colores y la tipografía de los
documentos de UDA (carbón, piedra, bronce, arena; TeX Gyre Adventor). El piloto automático prueba cuál funciona mejor.

  piedra    como los documentos: fondo piedra con rejilla fina de papel técnico, tarjetas blancas, acentos bronce (por defecto)
  carbon    fondo carbón como las cabeceras de los documentos, tarjetas piedra y etiquetas arena
  plano     fondo piedra oscura con ejes y líneas de cota de un plano, tarjetas de esquinas vivas
  ficha     hoja técnica con cajetín (como un plano de proyecto): casillas que se marcan a mano en bronce
  minimal   editorial: fondo claro, tipografía grande en carbón y un único acento bronce
  negro     premium: fondo negro, tarjetas grafito con filete dorado, cifras y acentos en oro (por defecto)
  ilustrado imagen original de arquitectura generada por la ilustradora (IA) de fondo, con tarjetas encima
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from fx import W, H, CARBON, CARBON_D, PIEDRA, PIEDRA_D, BRONCE, ARENA, GRIS, WHITE, TERRACOTA, BORDER, NEGRO, NEGRO_C, ORO, ORO_D, CREMA

STYLES = ["negro", "piedra", "carbon", "plano", "ficha", "minimal", "ilustrado"]


def _mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a[:3], b[:3]))


# ------------------------------------------------------------------ fondos
class GradientBG:
    """Degradado vertical + luces muy suaves que se mueven + trazado técnico (rejilla, ejes y cotas)."""
    S = 4

    def __init__(self, top, bottom, pattern="grid", line=(43, 43, 43, 16), blobs=(), blob_alpha=26, seed=0):
        rng = np.random.RandomState(seed)
        w, h = W // self.S, H // self.S
        y = np.linspace(0, 1, h)[:, None, None]
        base = np.broadcast_to(np.array(top, np.float32) * (1 - y) + np.array(bottom, np.float32) * y, (h, w, 3)).copy()
        self.base = Image.fromarray(base.astype(np.uint8)).convert("RGBA")
        self.pat = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(self.pat)
        strong = line[:3] + (min(255, line[3] * 2),)
        if pattern in ("grid", "ficha"):                       # papel técnico: rejilla fina y una más marcada cada 5
            for k, yy in enumerate(range(0, H, 36)):
                d.line([(0, yy), (W, yy)], fill=strong if k % 5 == 0 else line, width=1)
            for k, xx in enumerate(range(0, W, 36)):
                d.line([(xx, 0), (xx, H)], fill=strong if k % 5 == 0 else line, width=1)
        elif pattern == "plan":                                 # ejes de replanteo y líneas de cota (sin números)
            xs = [90, 380, 700, 990]; ys = [180, 620, 1180, 1760]
            for x in xs:
                for y0 in range(0, H, 46):                     # eje en trazo y punto
                    d.line([(x, y0), (x, y0 + 26)], fill=strong, width=2); d.ellipse([x - 2, y0 + 33, x + 2, y0 + 37], fill=strong)
                d.ellipse([x - 22, 70, x + 22, 114], outline=strong, width=3)
            for y in ys:
                for x0 in range(0, W, 46):
                    d.line([(x0, y), (x0 + 26, y)], fill=line, width=2)
            for (a, b) in zip(xs, xs[1:]):                     # cota superior con marcas a 45º
                d.line([(a, 140), (b, 140)], fill=strong, width=2)
                for x in (a, b):
                    d.line([(x - 10, 150), (x + 10, 130)], fill=strong, width=3)
            for (a, b) in zip(ys, ys[1:]):                     # cota lateral
                d.line([(40, a), (40, b)], fill=strong, width=2)
                for y in (a, b):
                    d.line([(30, y + 10), (50, y - 10)], fill=strong, width=3)
        elif pattern == "rules":                                # editorial: filetes horizontales muy finos
            for yy in range(120, H, 120):
                d.line([(60, yy), (W - 60, yy)], fill=line, width=1)
        self.blobs = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(80, 130), rng.uniform(0, 6.28),
                       blobs[k % len(blobs)], blob_alpha) for k in range(4)] if blobs else []
        self._cache = {}

    def _blob(self, r, col, a):
        k = (int(r), col, a)
        if k not in self._cache:
            im = Image.new("RGBA", (int(r * 2.6), int(r * 2.6)), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([r * .3, r * .3, r * 2.3, r * 2.3], fill=tuple(col[:3]) + (a,))
            self._cache[k] = im.filter(ImageFilter.GaussianBlur(r * 0.4))
        return self._cache[k]

    def frame(self, t):
        q = round(t * 8) / 8                         # el fondo se mueve muy despacio: basta con recalcularlo 8 veces/s
        if getattr(self, "_last", (None,))[0] == q:
            return self._last[1].copy()
        im = self._frame(q)
        self._last = (q, im)
        return im.copy()

    def _frame(self, t):
        im = self.base.copy()
        for x, y, r, ph, col, a in self.blobs:
            b = self._blob(r, col, a)
            cx = x + 14 * math.sin(t * 0.17 + ph); cy = y + 18 * math.cos(t * 0.13 + ph)
            im.alpha_composite(b, (int(cx - b.width / 2), int(cy - b.height / 2)))
        im = im.resize((W, H), Image.BILINEAR)
        im.alpha_composite(self.pat)
        return im


class ImageBG:
    """Imagen original de fondo: movimiento lento tipo Ken Burns, oscurecida (carbón) para que las tarjetas se lean."""

    def __init__(self, img, dark=0.55, blur=6, punch=0.0):
        self.punch = punch                          # acercamiento rápido al principio (gancho con movimiento)
        im = img.convert("RGB")
        r = max(W * 1.12 / im.width, H * 1.12 / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        self.sharp = im
        soft = im.filter(ImageFilter.GaussianBlur(blur)) if blur else im
        self.soft = Image.blend(soft, Image.new("RGB", soft.size, CARBON_D), dark)

    def frame(self, t, sharp=False):
        q = (round(t * (25 if self.punch else 8)) / (25 if self.punch else 8), sharp)   # lento: 8 cálculos/s; gancho: 25
        if getattr(self, "_last", (None,))[0] == q:
            return self._last[1].copy()
        im = self._frame(q[0], sharp)
        self._last = (q, im)
        return im.copy()

    def _frame(self, t, sharp=False):
        src = self.sharp if sharp else self.soft
        z = 1.0 + 0.05 * (0.5 - 0.5 * math.cos(min(t, 60) / 60 * math.pi)) + self.punch * (1 - (1 - min(t, 4) / 4) ** 2)
        vw, vh = src.width / 1.12 / z, src.height / 1.12 / z
        x0 = (src.width - vw) / 2 + 20 * math.sin(t * 0.05); y0 = (src.height - vh) / 2
        return src.crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh))).resize((W, H), Image.BILINEAR).convert("RGBA")


# ------------------------------------------------------------------ temas
class Theme:
    def __init__(self, name, **kw):
        self.name = name
        # valores por defecto = piedra (como los documentos)
        self.card_fill, self.card_outline, self.card_radius, self.shadow = WHITE, BORDER, 10, True
        self.ink, self.dim, self.label = CARBON, (178, 172, 165), BRONCE
        self.accent, self.accent_fg = CARBON, WHITE
        self.row_fill, self.row_active, self.row_outline, self.row_radius = PIEDRA, PIEDRA_D, BRONCE, 6
        self.ok_mode, self.ok_col, self.ok_text = "fill", BRONCE, WHITE
        self.bad_col, self.bad_fill = TERRACOTA, (247, 234, 230)
        self.faded = (205, 200, 194)
        self.letter = "square"
        self.title_bg, self.title_fg = CARBON, WHITE
        self.badge_bg, self.badge_fg, self.chip_bg, self.chip_fg = CARBON, ARENA, WHITE, BRONCE
        self.head_col, self.head_hot, self.head_stroke, self.head_stroke_col, self.head_shadow = CARBON, BRONCE, 0, WHITE, False
        self.sub_band, self.sub_ink, self.sub_dim = (255, 255, 255, 236), CARBON, (175, 170, 164)
        self.ring_bg, self.ring_col, self.ring_fg = (255, 255, 255, 245), BRONCE, CARBON
        self.pill_bg, self.pill_fg, self.pill_outline = CARBON, WHITE, None
        self.big_col = CARBON
        self.ref_bg, self.ref_fg = PIEDRA, BRONCE
        self.burst = []                       # sin confeti: estética sobria (la respuesta se marca con un barrido bronce)
        self.web_bg, self.web_fg = (255, 255, 255, 225), CARBON      # la web arriba, en pequeño
        self.header, self.header_right = None, "HOJA DE PROYECTO"   # cajetín de la tarjeta (estilo ficha)
        self.pill_radius = 4
        self.top_rule = BRONCE                # filete bronce sobre las tarjetas (como en los documentos)
        self.music_bpm = 84
        # tarjeta final de marca y detalles que antes iban fijos
        self.brand_bg, self.brand_rule, self.brand_ink, self.brand_sub = CARBON, BRONCE, WHITE, ARENA
        self.brand_pill, self.brand_pill_fg, self.brand_web, self.brand_web_fg = BRONCE, WHITE, PIEDRA, CARBON
        self.mito_col, self.real_col, self.img_hot, self.warn_col = TERRACOTA, BRONCE, ARENA, TERRACOTA
        self.__dict__.update(kw)

    def background(self, seed, image=None):
        n = self.name
        if n == "carbon":
            return GradientBG(CARBON, CARBON_D, "grid", line=(255, 255, 255, 9), blobs=(BRONCE, ARENA), blob_alpha=22, seed=seed)
        if n == "plano":
            return GradientBG(PIEDRA_D, (204, 197, 188), "plan", line=(43, 43, 43, 30), blobs=(WHITE,), blob_alpha=40, seed=seed)
        if n == "ficha":
            return GradientBG(PIEDRA, (236, 232, 226), "ficha", line=(122, 106, 88, 18), seed=seed)
        if n == "minimal":
            return GradientBG((250, 249, 247), PIEDRA, "rules", line=(43, 43, 43, 14), seed=seed)
        if n == "negro":
            return GradientBG((22, 21, 19), (6, 6, 6), "rules", line=ORO + (16,), blobs=(ORO,), blob_alpha=12, seed=seed)
        if n == "ilustrado" and image is not None:
            return ImageBG(image)
        return GradientBG(PIEDRA, (236, 232, 226), "grid", line=(43, 43, 43, 11), blobs=(WHITE, ARENA), blob_alpha=34, seed=seed)


def get(name):
    if name == "negro":
        G = (34, 33, 30)
        return Theme("negro", card_fill=NEGRO_C, card_outline=(70, 60, 40), card_radius=6, shadow=False,
                     ink=CREMA, dim=(105, 100, 92), label=ORO, accent=ORO, accent_fg=NEGRO,
                     row_fill=G, row_active=(52, 46, 34), row_outline=ORO, ok_col=ORO, ok_text=NEGRO,
                     bad_col=(120, 116, 110), bad_fill=G, faded=(72, 69, 64), title_bg=ORO, title_fg=NEGRO,
                     badge_bg=ORO, badge_fg=NEGRO, chip_bg=(255, 255, 255, 18), chip_fg=ORO,
                     head_col=CREMA, head_hot=ORO, sub_band=(8, 8, 8, 200), sub_ink=CREMA, sub_dim=(120, 114, 104),
                     ring_bg=(14, 14, 14, 240), ring_col=ORO, ring_fg=CREMA, pill_bg=ORO, pill_fg=NEGRO, big_col=ORO,
                     ref_bg=G, ref_fg=ORO, web_bg=(255, 255, 255, 14), web_fg=ORO, top_rule=ORO, pill_radius=3,
                     brand_bg=NEGRO, brand_rule=ORO, brand_ink=CREMA, brand_sub=ORO, brand_pill=ORO, brand_pill_fg=NEGRO,
                     brand_web=CREMA, brand_web_fg=NEGRO, mito_col=(110, 106, 100), real_col=ORO, img_hot=ORO,
                     warn_col=ORO_D, music_bpm=82)
    if name == "carbon":
        return Theme("carbon", card_fill=PIEDRA, card_outline=None, label=BRONCE, row_fill=WHITE, row_active=PIEDRA_D,
                     badge_bg=BRONCE, badge_fg=WHITE, chip_bg=(255, 255, 255, 30), chip_fg=ARENA,
                     head_col=WHITE, head_hot=ARENA, sub_band=(20, 20, 20, 170), sub_ink=WHITE, sub_dim=(140, 136, 130),
                     ring_bg=(20, 20, 20, 235), ring_col=ARENA, ring_fg=WHITE, pill_bg=BRONCE, ref_bg=WHITE,
                     web_bg=(255, 255, 255, 30), web_fg=ARENA, top_rule=ARENA, music_bpm=80)
    if name == "plano":
        return Theme("plano", card_radius=0, card_outline=CARBON, row_radius=0, letter="circle_outline",
                     shadow=False, badge_bg=CARBON, badge_fg=WHITE, top_rule=None, music_bpm=86)
    if name == "ficha":
        return Theme("ficha", card_radius=0, card_outline=CARBON, row_fill=WHITE, row_radius=0, row_active=PIEDRA,
                     row_outline=CARBON, ok_mode="pen", ok_col=BRONCE, ok_text=CARBON, letter="box", label=GRIS,
                     header="UDA · UNIÓN DE ARQUITECTOS", header_right="HOJA DE PROYECTO", top_rule=None,
                     shadow=False, music_bpm=78)
    if name == "minimal":
        return Theme("minimal", card_outline=None, card_radius=0, shadow=False, row_fill=(247, 245, 242),
                     letter="square", badge_bg=BRONCE, badge_fg=WHITE, top_rule=BRONCE, music_bpm=88)
    if name == "ilustrado":
        return Theme("ilustrado", card_fill=PIEDRA + (246,), card_outline=None, sub_band=(20, 20, 20, 160), sub_ink=WHITE,
                     sub_dim=(150, 146, 140), web_bg=(0, 0, 0, 110), web_fg=WHITE, head_col=WHITE, head_hot=ARENA)
    return Theme("piedra")
