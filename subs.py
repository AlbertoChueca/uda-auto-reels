"""Subtítulos palabra a palabra para los reels con voz (portafolio.py y visual.py): la mayoría de la gente ve los
vídeos sin sonido, y un texto que avanza con la voz retiene mucho más que un rótulo fijo.

    S = subs.Subs(clips, textos, instantes)      # clips de voz (24 kHz), su texto y cuándo empieza cada uno
    S.pinta(fotograma_RGBA, t, y=350)            # en cada fotograma

Cada trozo son 2-4 palabras; la palabra que se está diciendo va en crema, las ya dichas más tenues y las palabras
clave (cifras) en dorado. Los instantes salen de la propia voz (voice.align); si el reconocedor no está, se reparten
en proporción a la longitud de cada palabra.
"""
import re

import fx
from fx import W, SR, CREMA, ORO, clamp, eo

NEGRO = (8, 8, 9)
_CACHE = {}


def _img(word, size, color):
    k = (word, size, color)
    if k not in _CACHE:
        _CACHE[k] = fx.word_img(word, size, color, stroke=max(4, size // 9), path=fx.F_BOLD, stroke_col=NEGRO)
    return _CACHE[k]


def palabras(clips, textos, at):
    """[(t_absoluto, palabra, fin_del_clip)]"""
    out = []
    for c, tx, t0 in zip(clips, textos, at):
        if c is None or not tx:
            continue
        ws = tx.split(); al = None
        try:
            import voice
            al = voice.align(c, tx)
        except Exception:
            al = None
        if not al or len(al) != len(ws):
            L = sum(len(w) + 1 for w in ws); acc = 0; al = []
            for w in ws:
                al.append(((len(c) / SR) * acc / L * 0.94, w)); acc += len(w) + 1
        fin = t0 + len(c) / SR
        out += [(t0 + float(a), w, fin) for (a, _), w in zip(al, ws)]
    return out


class Subs:
    def __init__(self, clips, textos, at, size=54, maxw=960, claves=()):
        self.size, self.maxw = size, maxw
        self.claves = {self._n(c) for c in claves}
        self.trozos = []                                   # [( [(t, palabra)], t_inicio, t_fin )]
        cur = []
        P = palabras(clips, textos, at)
        for i, (t, w, fin) in enumerate(P):
            cur.append((t, w))
            ult = i + 1 == len(P) or P[i + 1][2] != fin   # última palabra de su clip
            if ult or w[-1:] in ".,:;?!…" or sum(len(x[1]) + 1 for x in cur) >= 22 or len(cur) >= 4:
                self.trozos.append((cur, cur[0][0], fin + 0.25 if ult else None)); cur = []
        for i, (tr, t0, fin) in enumerate(self.trozos):   # cada trozo dura hasta que empieza el siguiente
            if fin is None:
                self.trozos[i] = (tr, t0, self.trozos[i + 1][1])

    @staticmethod
    def _n(w):
        return re.sub(r"[^\wáéíóúñü%€]", "", w.lower())

    def pinta(self, fr, t, y=350):
        act = next((tr for tr, t0, fin in self.trozos if t0 - 0.04 <= t < fin), None)
        if not act:
            return
        size = self.size
        ims = None
        while True:
            ims = [_img(w, size, CREMA) for _, w in act]
            esp = size * 0.10
            ancho = sum(im.width for im in ims) + esp * (len(ims) - 1)
            if ancho <= self.maxw or size <= 36:
                break
            size -= 4
        x = W / 2 - ancho / 2
        cur = max((i for i, (tw, _) in enumerate(act) if tw <= t), default=0)
        for i, ((tw, w), im) in enumerate(zip(act, ims)):
            if tw <= t + 0.03:
                k = eo((t - tw) / 0.12)
                clave = self._n(w) in self.claves or any(ch.isdigit() for ch in w)
                if clave:
                    im = _img(w, size, ORO)
                a = (1.0 if i == cur else 0.66) * clamp(k)
                fx.paste_center(fr, im, x + im.width / 2, y - (1 - k) * 8, alpha=a)
            x += im.width + esp
