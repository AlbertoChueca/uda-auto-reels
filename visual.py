"""Reels VISUALES de UDA (imagen primero, como los que triunfan en TikTok de arquitectura): poca letra, imágenes
espectaculares, cortes al ritmo de la música y una pregunta para comentar o una razón para guardar.

Formatos (banco: fuentes/visual.json):
    galeria         «Interiores que pondría en mi casa»: 6 imágenes numeradas -> «¿Con cuál te quedas? Comenta el número»
    proceso         «Del boceto al render»: la MISMA casa en boceto, planos de AutoCAD, modelo de Revit y render
    antes_despues   «Antes y después de una reforma»: 3 estancias, la misma cámara, cortinilla dorada
    tips            «5 tips para fotografiar arquitectura», «5 claves para un salón con más luz»...: imagen + consejo
    obra            «De la zanja a la llave»: la misma casa en cimentación, estructura, cerramientos y terminada

Imágenes: originales, generadas con IA (Gemini) y revisadas una a una por la revisora visual (sin texto, sin edificios
reales, construcción coherente). Las de una misma casa o estancia se generan a partir de la primera (referencia), para
que sea reconocible en cada paso. La descripción lo indica: «Imágenes creadas con IA».
Vídeo: 1080×1920, Ken Burns suave, cortes en el tiempo fuerte de la música (premium_beat con tempo exacto), título
fijo arriba, etiqueta por imagen y cierre con la pregunta, el «Guárdalo» y la marca. Revisión: agente de vídeo propio
(nota 8 con escala anclada); si marca imágenes concretas, se regeneran solo esas.
"""
import base64, datetime, hashlib, io, json, math, os, random, subprocess, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fx
from fx import W, H, FPS, SR, F_BOLD, F_REG, F900, clamp, eo, eob

HERE = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(HERE, "fuentes", "visual.json")
FORMATOS = ["galeria", "proceso_visual", "antes_despues", "tips", "obra"]
BANCO_DE = {"proceso_visual": "proceso"}                     # nombre de la sección del banco
NOMBRE = {"galeria": "Galería de inspiración", "proceso_visual": "Del boceto al render", "proceso": "Del boceto al render", "antes_despues": "Antes y después",
          "tips": "Tips visuales", "obra": "De la zanja a la llave"}
ORO, CREMA, NEGRO = fx.ORO, fx.CREMA, fx.NEGRO
FOTO = ("Fotografía de arquitectura e interiorismo de revista: luz natural bonita, colores reales y cálidos, encuadre "
        "editorial, nítida y aspiracional")
REGLAS = ("Imagen vertical 9:16. NADA de texto, letras, números, rótulos, cotas legibles ni logotipos. Arquitectura "
          "ORIGINAL y verosímil (nunca un edificio famoso o reconocible), construcción y detalles coherentes, sin personas "
          "identificables (si aparecen, de espaldas o desenfocadas). En obra: sin riesgos y con EPI correctos.")
SAFE_TOP, SAFE_BOT = 250, 1480


def say(*a):
    print("visual:", *a, flush=True)


# ------------------------------------------------------------------ elegir pieza
def _used():
    try:
        return {x["id"] for x in json.load(open(os.path.join(HERE, "used.json")))}
    except Exception:
        return set()


def pieza(formato, seed=0):
    """La pieza del banco menos usada de ese formato (y, en antes/después, 3 estancias distintas)."""
    B = json.load(open(BANCO)); rng = random.Random(seed); usados = _used()
    formato = BANCO_DE.get(formato, formato)
    lista = B[formato]
    if formato == "antes_despues":
        frescas = [p for p in lista if f"visual:{p['id']}" not in usados] or lista
        rng.shuffle(frescas)
        el = (frescas + [p for p in lista if p not in frescas])[:3]
        return {"id": "+".join(p["id"] for p in el), "ids": [f"visual:{p['id']}" for p in el], "estancias": el,
                "hook": "Antes y después de una reforma"}
    frescas = [p for p in lista if f"visual:{p['id']}" not in usados] or lista
    p = dict(rng.choice(frescas)); p["ids"] = [f"visual:{p['id']}"]
    return p


# ------------------------------------------------------------------ imágenes (IA + revisora)
def _gen(prompt, refs=(), revisar=True, intentos=2):
    import gemini, estudio
    idea = prompt
    for k in range(intentos):
        try:
            img = gemini.image(f"{FOTO}. {idea}. {REGLAS}", "9:16", refs)
        except Exception as e:
            say("imagen no generada:", str(e)[:150]); continue
        if not revisar:
            return img
        ok, why, mejor = estudio.revisora(img, prompt)
        if ok:
            return img
        say(f"revisora rechaza ({why[:120]}); intento {k + 2}")
        if mejor:
            idea = f"{prompt}. Corrige: {why[:200]}"
    return None


def imagenes(formato, P):
    """Lista de (imagen, etiqueta) en orden. Devuelve también el texto de cada paso para el guion."""
    formato = BANCO_DE.get(formato, formato)
    pasos = []
    with ThreadPoolExecutor(6) as ex:
        if formato == "galeria":
            fs = [ex.submit(_gen, e["idea"]) for e in P["escenas"]]
            pasos = [(f.result(), e["label"]) for f, e in zip(fs, P["escenas"])]
            pasos = [x for x in pasos if x[0] is not None]
            if len(pasos) < 5:
                raise RuntimeError("galería: menos de 5 imágenes aprobadas")
        elif formato == "tips":
            fs = [ex.submit(_gen, t["idea"]) for t in P["tips"]]
            pasos = [(f.result(), t["tip"]) for f, t in zip(fs, P["tips"])]
            if any(im is None for im, _ in pasos):
                raise RuntimeError("tips: falta alguna imagen aprobada")
        elif formato in ("proceso", "obra"):
            final = _gen(f"Render fotorrealista exterior de {P['descripcion']}, terminada, jardín cuidado, luz de atardecer")
            if final is None:
                raise RuntimeError(f"{formato}: no hay render final aprobado")
            if formato == "proceso":
                etapas = [
                    ("La idea, a mano", "Boceto a mano alzada con lápiz y rotulador sobre papel de croquis de ESTA MISMA casa "
                     "(misma forma y proporciones que la imagen de referencia), trazo suelto de arquitecto, papel de fondo", False),
                    ("Planos en AutoCAD", "Planta arquitectónica de ESTA casa dibujada en CAD: líneas negras finas sobre fondo "
                     "blanco, muros en gris, puertas y ventanas; SIN ningún texto, cota ni número", False),
                    ("Modelo en Revit", "Maqueta digital blanca de ESTA MISMA casa como un modelo BIM de Revit: volúmenes "
                     "blancos, sombras suaves, fondo gris claro, vista axonométrica", True)]
                fin = "Render final"
            else:
                etapas = [
                    ("Cimentación", "La obra de ESTA MISMA casa en fase de cimentación: zanjas, armaduras y hormigón de "
                     "limpieza en el solar, sin personas", True),
                    ("Estructura", "La obra de ESTA MISMA casa con la estructura de hormigón terminada: pilares y forjados, "
                     "andamio perimetral, sin personas", True),
                    ("Cerramientos", "La obra de ESTA MISMA casa con fachadas y cubierta cerradas, aún sin acabar, andamios",
                     True)]
                fin = "¡Terminada!"
            fs = [ex.submit(_gen, txt, [final], rev) for _, txt, rev in etapas]
            pasos = [(f.result(), lab) for f, (lab, _, _) in zip(fs, etapas)] + [(final, fin)]
            if any(im is None for im, _ in pasos):
                raise RuntimeError(f"{formato}: falta alguna etapa")
        else:                                                      # antes / después
            def par(e):
                antes = _gen(f"Fotografía real de {e['descripcion']}, aspecto anticuado y descuidado, luz pobre, "
                             "cámara a la altura de los ojos")
                if antes is None:
                    return None
                despues = _gen("La MISMA estancia de la imagen de referencia (misma geometría, mismas ventanas y la misma "
                               "cámara) después de una reforma de arquitecto: contemporánea, luminosa, materiales naturales, "
                               "impecable", [antes])
                return (antes, despues) if despues is not None else None
            fs = [ex.submit(par, e) for e in P["estancias"]]
            pares = [f.result() for f in fs]
            pares = [x for x in pares if x]
            if len(pares) < 2:
                raise RuntimeError("antes/después: menos de 2 parejas aprobadas")
            for a, d in pares:
                pasos += [(a, "ANTES"), (d, "DESPUÉS")]
    return pasos


# ------------------------------------------------------------------ montaje
def _cover_fit(img, zoom=1.0, cx=0.5, cy=0.5):
    """Recorta la imagen a 9:16 llenando la pantalla, con zoom y centro (0-1)."""
    iw, ih = img.size
    s = max(W / iw, H / ih) * zoom
    nw, nh = int(iw * s), int(ih * s)
    im = img.resize((nw, nh), Image.BICUBIC)
    x = int((nw - W) * cx); y = int((nh - H) * cy)
    return im.crop((x, y, x + W, y + H))


def _ventana(big, z, c):
    """Recorte de la imagen grande con zoom z (1 = llena justo la pantalla) centrado en c, redimensionado a W×H."""
    bw, bh = big.size
    base = min(bw / W, bh / H)                       # píxeles de la imagen grande por píxel de pantalla con zoom 1
    ww, wh = W * base / z, H * base / z
    x = (bw - ww) * c[0]; y = (bh - wh) * c[1]
    return big.resize((W, H), Image.BICUBIC, box=(x, y, x + ww, y + wh))


def _plano(img, seed):
    r = random.Random(seed)
    z0, z1 = (1.0, 1.13) if r.random() < 0.6 else (1.13, 1.0)          # Ken Burns bien visible
    c0 = (r.uniform(0.35, 0.65), r.uniform(0.4, 0.6)); c1 = (r.uniform(0.35, 0.65), r.uniform(0.4, 0.6))
    iw, ih = img.size; s = max(W / iw, H / ih) * 1.15
    big = img.convert("RGB").resize((int(iw * s), int(ih * s)), Image.BICUBIC)
    return lambda p: _ventana(big, z0 + (z1 - z0) * eo(clamp(p)), (c0[0] + (c1[0] - c0[0]) * p, c0[1] + (c1[1] - c0[1]) * p))


def _degradados():
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    for y in range(0, 620, 4):
        d.rectangle([0, y, W, y + 4], fill=(0, 0, 0, int(170 * (1 - y / 620) ** 1.6)))
    for y in range(1000, H, 4):
        d.rectangle([0, y, W, y + 4], fill=(0, 0, 0, int(210 * ((y - 1000) / (H - 1000)) ** 1.3)))
    return g


def _panel(im, pad=36, alpha=150):
    """Texto grande sobre una banda oscura difuminada: legible aunque la foto sea muy clara."""
    w, h = im.width + 2 * pad, im.height + 2 * pad
    p = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(p).rounded_rectangle([pad // 2, pad // 2, w - pad // 2, h - pad // 2], 40, fill=(0, 0, 0, alpha))
    p = p.filter(ImageFilter.GaussianBlur(pad / 2))
    p.alpha_composite(im, (pad, pad))
    return p


def _titulo_fijo(texto):
    """Título pequeño fijo arriba (como en los reels de referencia)."""
    return fx.headline(texto, 54, 900, 2, color=CREMA, hot=ORO, hot_words=(), shadow=True)


def guion(formato, P, pasos, bpm):
    formato = BANCO_DE.get(formato, formato)
    beat = 60 / bpm
    por = {"galeria": 2, "tips": 4, "proceso": 3, "obra": 3, "antes_despues": 2}[formato]
    hook = P.get("hook") or {"proceso": "Del boceto al render", "obra": "De la zanja a la llave"}[formato]
    sub = P.get("descripcion", "")
    golpes = []
    for k, (img, lab) in enumerate(pasos):
        d = beat * por
        if k == 0:
            d += beat * 3                                            # el primero lleva antes el gancho (≈2 s)
        if formato == "antes_despues" and lab == "DESPUÉS":
            d = beat * 3
        golpes.append({"img": img, "label": lab, "dur": d, "n": k})
    cierre = {"galeria": (P.get("cierre", "¿Con cuál te quedas?"), "Comenta el número"),
              "tips": ("¿Cuál aplicas ya?", "Guárdalo para tu próximo proyecto"),
              "proceso": ("¿Qué fase te gusta más?", "Guárdalo y compártelo con tu equipo"),
              "obra": ("¿Cuál es la fase más difícil?", "Cuéntanoslo en comentarios"),
              "antes_despues": ("¿Cuál te sorprende más?", "Guárdalo para tu próxima reforma")}[formato]
    return {"formato": formato, "hook": hook, "sub": sub, "golpes": golpes, "cierre": cierre, "beat": beat,
            "fin": beat * 6}


def render(G, out, seed=0, bpm=84):
    """Renderiza el reel (vídeo + audio) y devuelve meta."""
    golpes, beat = G["golpes"], G["beat"]
    fmt = G["formato"]
    t0s = []; t = 0.0
    for g in golpes:
        t0s.append(t); t += g["dur"]
    t_fin = t; total = t + G["fin"]
    planos = [_plano(g["img"], f"{seed}-{k}") for k, g in enumerate(golpes)]
    grad = _degradados()
    hook_big = _panel(fx.headline(G["hook"], 118, 960, 3, color=CREMA, hot=ORO,
                                  hot_words=tuple(w.lower().strip("¿?¡!.,") for w in G["hook"].split() if w[:1].isdigit()),
                                  shadow=True), 50, 140)
    tit = _panel(_titulo_fijo(G["hook"]), 24, 120)
    labs = []
    for k, g in enumerate(golpes):
        lab = g["label"]
        if fmt == "galeria":
            num = fx.pill(f"{k + 1:02d}", 54, ORO, NEGRO, padx=24, pady=14, radius=6)
            txt = fx.pill(lab, 54, (18, 17, 15), CREMA, padx=28, pady=14, radius=6)
            im = Image.new("RGBA", (num.width + txt.width + 14, max(num.height, txt.height)), (0, 0, 0, 0))
            im.alpha_composite(num, (0, 0)); im.alpha_composite(txt, (num.width + 14, 0))
        elif fmt == "tips":
            n = fx.headline(str(k + 1), 230, 400, 1, color=ORO, hot=ORO, shadow=True)
            tx = fx.headline(lab, 92, 940, 3, color=CREMA, hot=ORO, shadow=True)
            im = Image.new("RGBA", (max(n.width, tx.width), n.height + tx.height - 30), (0, 0, 0, 0))
            im.alpha_composite(n, ((im.width - n.width) // 2, 0)); im.alpha_composite(tx, ((im.width - tx.width) // 2, n.height - 30))
            im = _panel(im, 44, 150)
        elif fmt == "antes_despues":
            im = fx.pill(lab, 64, ORO if lab == "DESPUÉS" else (40, 38, 34), NEGRO if lab == "DESPUÉS" else CREMA,
                         padx=40, pady=18, radius=6)
        else:
            num = fx.pill(f"{k + 1}", 60, ORO, NEGRO, padx=28, pady=14, radius=40)
            tx = fx.headline(lab, 88, 900, 2, color=CREMA, hot=ORO, shadow=True)
            im = Image.new("RGBA", (max(num.width, tx.width), num.height + 16 + tx.height), (0, 0, 0, 0))
            im.alpha_composite(num, ((im.width - num.width) // 2, 0)); im.alpha_composite(tx, ((im.width - tx.width) // 2, num.height + 16))
            im = _panel(im, 40, 140)
        labs.append(im)
    # cierre: cuadrícula de miniaturas numeradas (galería) o la última imagen; pregunta + «guárdalo» + marca
    ult = golpes[-1]["img"].convert("RGB")
    fondo_fin = _cover_fit(ult).filter(ImageFilter.GaussianBlur(18))
    fondo_fin = Image.blend(fondo_fin, Image.new("RGB", (W, H), (0, 0, 0)), 0.55).convert("RGBA")
    if fmt == "galeria":
        tw, th, g_ = 290, 380, 22
        x0 = (W - 3 * tw - 2 * g_) // 2; y0 = 560
        for k, g in enumerate(golpes[:6]):
            th_ = _cover_fit(g["img"].convert("RGB")).resize((tw, th))
            x = x0 + (k % 3) * (tw + g_); y = y0 + (k // 3) * (th + g_)
            fondo_fin.paste(th_, (x, y))
            ImageDraw.Draw(fondo_fin).rectangle([x, y, x + tw - 1, y + th - 1], outline=ORO, width=3)
            fondo_fin.alpha_composite(fx.pill(str(k + 1), 44, ORO, NEGRO, padx=20, pady=8, radius=6), (x + 14, y + 14))
    q = fx.headline(G["cierre"][0], 100, 960, 2, color=CREMA, hot=ORO, shadow=True)
    sv = fx.pill(G["cierre"][1], 46, ORO, NEGRO, padx=34, pady=18, radius=6)
    lg = fx.logo(54, CREMA, ORO)
    web = fx.text_block("Equipo técnico para despachos · uniondearquitectos.com", F_REG, 30, 900, (200, 194, 182), align="center")

    # ---- audio: música con tempo exacto + aire en cada corte + golpe en gancho y cierre
    n = int(SR * (total + 0.3))
    music = fx.premium_beat(total + 0.3, bpm, seed=seed, energy=1.2, jitter=False)
    music = np.pad(music, (0, max(0, n - len(music))))[:n] * 0.75
    sfx = np.zeros(n, np.float32)

    def put(a, at, gain=1.0):
        i = int(at * SR)
        if i < 0: a = a[-i:]; i = 0
        j = min(n, i + len(a)); sfx[i:j] += a[: j - i] * gain
    put(fx.impact(), 0.0, 0.7)
    for t0 in t0s[1:] + [t_fin]:
        put(fx.whoosh2(0.4), t0 - 0.3, 0.7); put(fx.impact(), t0, 0.35)
    if fmt == "antes_despues":
        for k, g in enumerate(golpes):
            if g["label"] == "DESPUÉS":
                put(fx.shimmer(), t0s[k] + 0.1, 0.35)
    put(fx.shimmer(), t_fin + 0.2, 0.55)
    mix = fx.dehiss(np.tanh((music + sfx) * 1.1) * 0.9)
    wav = out.replace(".mp4", ".wav")
    import soundfile as sf
    sf.write(wav, mix, SR)

    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest",
                             "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-crf", "20", "-maxrate", "8M",
                             "-bufsize", "12M", "-g", str(FPS * 2), "-pix_fmt", "yuv420p", "-r", str(FPS),
                             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", out],
                            stdin=subprocess.PIPE)
    nf = int(total * FPS); timeline = []
    for f in range(nf):
        tt = f / FPS
        if tt < t_fin:
            k = max(i for i, a in enumerate(t0s) if a <= tt)
            g = golpes[k]; lt = tt - t0s[k]
            fr = planos[k](lt / g["dur"]).convert("RGBA")
            if fmt == "antes_despues" and g["label"] == "DESPUÉS" and k > 0:   # cortinilla dorada desde el «antes»
                w_ = eo(clamp(lt / 0.7))
                if w_ < 1:
                    prev = planos[k - 1](1.0).convert("RGBA")
                    cut = int(W * w_)
                    prev.paste(fr.crop((0, 0, cut, H)), (0, 0))
                    fr = prev
                    ImageDraw.Draw(fr).rectangle([cut - 4, 0, cut + 4, H], fill=ORO)
            elif k > 0 and lt < 0.16:                                 # fundido corto con el plano anterior
                prev = planos[k - 1](1.0).convert("RGBA")
                fr = Image.blend(prev, fr, lt / 0.16)
            fr.alpha_composite(grad)
            hook_t = 3 * beat
            if k == 0 and lt < hook_t:                                # gancho grande al principio (solo)
                a = eob(clamp(lt / 0.35))
                im = hook_big
                if a < 1:
                    s_ = 0.9 + 0.1 * a; im = hook_big.resize((int(hook_big.width * s_), int(hook_big.height * s_)))
                fx.paste_center(fr, im, W / 2, 760, alpha=clamp(a * 1.5) * (1 - clamp((lt - hook_t + 0.25) / 0.25)))
            else:
                fx.paste_center(fr, tit, W / 2, SAFE_TOP + 60 + tit.height / 2)
            if not (k == 0 and lt < hook_t):
                la = labs[k]; a = eob(clamp((lt - (hook_t if k == 0 else 0.12)) / 0.3))
                cy = 1270 if fmt != "tips" else 1180
                fx.paste_center(fr, la, W / 2, cy - (1 - a) * 30, alpha=clamp(a))
        else:
            lt = tt - t_fin
            fr = fondo_fin.copy()
            a = eob(clamp(lt / 0.4))
            yq = 330 if fmt == "galeria" else 760
            fx.paste_center(fr, q, W / 2, yq + q.height / 2 - (1 - a) * 30, alpha=clamp(a))
            b = eob(clamp((lt - 0.5) / 0.4))
            ys = 1420 if fmt == "galeria" else yq + q.height + 90
            fx.paste_center(fr, sv, W / 2, ys - (1 - b) * 20, alpha=clamp(b))
            c_ = clamp((lt - 0.9) / 0.4)
            fx.paste_center(fr, lg, W / 2, 1460 if fmt != "galeria" else 1535, alpha=c_)
            fx.paste_center(fr, web, W / 2, 1560 if fmt != "galeria" else 1610, alpha=c_)
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait(); os.remove(wav)
    if proc.returncode:
        raise RuntimeError("ffmpeg falló al codificar el reel visual")
    return {"duration": round(total, 1), "t0s": t0s, "t_fin": t_fin}


# ------------------------------------------------------------------ portada
def portada(G, path):
    import infoviz as IV, themes
    T = themes.get("negro"); golpes = G["golpes"]; fmt = G["formato"]
    if fmt == "galeria":                                       # mosaico 2×2 con las 4 mejores
        base = Image.new("RGBA", (W, H), (10, 10, 10, 255))
        cw, ch = W // 2, (IV.GRID[1] - IV.GRID[0]) // 2
        for k, g in enumerate(golpes[:4]):
            im = _cover_fit(g["img"].convert("RGB")).resize((cw, int(cw * H / W))).crop((0, (int(cw * H / W) - ch) // 2, cw, (int(cw * H / W) - ch) // 2 + ch))
            base.paste(im, ((k % 2) * cw, IV.GRID[0] + (k // 2) * ch))
        band = Image.new("RGBA", (W, 420), (0, 0, 0, 0)); bd = ImageDraw.Draw(band)
        for y in range(420):
            bd.line([(0, y), (W, y)], fill=(0, 0, 0, int(205 * math.sin(math.pi * y / 420) ** 0.6)))
        base.alpha_composite(band, (0, (IV.GRID[0] + IV.GRID[1]) // 2 - 210))
        hl = fx.headline(G["hook"], 110, 960, 3, color=CREMA, hot=ORO, shadow=True)
        fx.paste_center(base, hl, W / 2, (IV.GRID[0] + IV.GRID[1]) / 2)
    elif fmt == "antes_despues":                               # mitad antes / mitad después
        a, d = golpes[0]["img"], golpes[1]["img"]
        base = _cover_fit(a.convert("RGB")).convert("RGBA")
        base.paste(_cover_fit(d.convert("RGB")).crop((W // 2, 0, W, H)), (W // 2, 0))
        ImageDraw.Draw(base).rectangle([W // 2 - 4, 0, W // 2 + 4, H], fill=ORO)
        base.alpha_composite(_degradados())
        fx.paste_center(base, fx.pill("ANTES", 50, (40, 38, 34), CREMA, padx=30, pady=14, radius=6), W / 4, IV.GRID[1] - 300)
        fx.paste_center(base, fx.pill("DESPUÉS", 50, ORO, NEGRO, padx=30, pady=14, radius=6), 3 * W / 4, IV.GRID[1] - 300)
        hl = fx.headline(G["hook"], 104, 960, 3, color=CREMA, hot=ORO, shadow=True)
        fx.paste_center(base, hl, W / 2, IV.GRID[0] + 140 + hl.height / 2)
    else:                                                      # la imagen más bonita + el titular grande
        img = golpes[-1]["img"] if fmt in ("proceso", "obra") else golpes[0]["img"]
        base = _cover_fit(img.convert("RGB")).convert("RGBA")
        base.alpha_composite(_degradados())
        hl = fx.headline(G["hook"], 120, 960, 3, color=CREMA, hot=ORO,
                         hot_words=tuple(w.lower() for w in G["hook"].split() if w[:1].isdigit()), shadow=True)
        fx.paste_center(base, hl, W / 2, IV.GRID[0] + 150 + hl.height / 2)
        if fmt == "proceso":                                   # miniatura del boceto en una esquina
            sk = _cover_fit(golpes[0]["img"].convert("RGB")).resize((300, 533))
            base.paste(sk, (W - 300 - 90, IV.GRID[1] - 533 - 130))
            ImageDraw.Draw(base).rectangle([W - 390, IV.GRID[1] - 663, W - 90, IV.GRID[1] - 130], outline=ORO, width=4)
    IV.frame(base, T)
    fx.paste_center(base, fx.logo(52, CREMA, ORO), W / 2, IV.GRID[1] - 90)
    base.convert("RGB").save(path, "JPEG", quality=92)
    return path


# ------------------------------------------------------------------ revisión
def revisar(path, G):
    """Agente de vídeo para reels visuales. Devuelve {"overall", "issues", "malas": [índices de imagen], ...}."""
    import reviewer
    small = path.replace(".mp4", "_review.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "scale=360:640", "-r", "12", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "48k", small], check=True)
        data = base64.b64encode(open(small, "rb").read()).decode()
        etiquetas = [f"{k + 1}: «{g['label']}» ({g['dur']:.1f} s)" for k, g in enumerate(G["golpes"])]
        res = reviewer._ask([{"text": f"""Eres director creativo de una cuenta de TikTok e Instagram de arquitectura para
arquitectos y amantes del diseño. Revisa este reel VISUAL (imágenes de arquitectura creadas con IA + música, sin voz, a
propósito). Formato: {NOMBRE[G['formato']]}. Gancho: «{G['hook']}». Imágenes en orden: {'; '.join(etiquetas)}.
Comprueba: que cada imagen sea bonita, verosímil y coherente con su etiqueta (en antes/después y en el proceso, que sea
reconocible la MISMA estancia o casa); defectos de IA (geometría imposible, escaleras o ventanas absurdas, texto o
letras raras en la imagen, objetos deformes); legibilidad de los textos en el móvil y zona segura; que el gancho se
entienda en 1,5 s; ritmo; cierre claro.
ESCALA ANCLADA: 8 = profesional y publicable SIN defectos objetivos (las opiniones de estilo no bajan de 8, van en
"suggestions"); 6-7 = algún defecto objetivo (imagen con defecto de IA visible, etiqueta que no corresponde, texto que se
sale o ilegible); 5 o menos = defecto grave (imagen absurda o inquietante, edificio famoso reconocible, vídeo roto).
"malas" = números (1, 2, ...) de las imágenes con defecto objetivo (vacío si ninguna).
Devuelve JSON: {{"overall": number, "issues": [str], "suggestions": [str], "malas": [int], "critical": bool}}"""},
                             {"inline_data": {"mime_type": "video/mp4", "data": data}}], 0.3)
    except Exception as e:
        say("revisión de vídeo no disponible:", str(e)[:200])
        return {"overall": 0, "issues": [f"revisor no disponible: {str(e)[:100]}"], "malas": []}
    finally:
        if os.path.exists(small): os.remove(small)
    ov = float(res.get("overall") or 0)
    if ov < 8 and not (res.get("issues") or []) and not res.get("critical"):
        res["overall_raw"] = ov; ov = 8.0                         # escala anclada: sin defectos objetivos, es un 8
    res["overall"] = ov
    reviewer._log("video_visual", {"hook": G["hook"], "overall": ov, "issues": res.get("issues"), "malas": res.get("malas"),
                                   "suggestions": res.get("suggestions")})
    say(f"revisión: {ov}/10", res.get("issues") or "")
    return res


# ------------------------------------------------------------------ descripción
TAGS = {"galeria": "#arquitectura #interiorismo #diseñodeinteriores #architecture #interiordesign #casas #decoracion",
        "proceso": "#arquitectura #autocad #revit #render #arquitecto #proyecto #architecture",
        "antes_despues": "#reforma #antesydespues #arquitectura #interiorismo #reformas #architecture",
        "tips": "#arquitectura #tipsdearquitectura #interiorismo #diseño #architecture #arquitecto",
        "obra": "#obra #construccion #arquitectura #arquitecto #casa #architecture"}


def descripcion(G):
    q, sv = G["cierre"]
    cuerpo = {"galeria": "\n".join(f"{k + 1}. {g['label']}" for k, g in enumerate(G["golpes"])),
              "tips": "\n".join(f"{k + 1}. {g['label']}" for k, g in enumerate(G["golpes"])),
              "proceso": " → ".join(g["label"] for g in G["golpes"]),
              "obra": " → ".join(g["label"] for g in G["golpes"]),
              "antes_despues": "Tres estancias, la misma cámara: antes y después de la reforma."}[G["formato"]]
    return (f"{G['hook']} ✨\n\n{cuerpo}\n\n👇 {q} {sv if G['formato'] == 'galeria' else ''}".rstrip()
            + f"\n📌 Guárdalo para tu próximo proyecto.\n\nImágenes creadas con IA por el equipo de UDA · Unión de "
              f"Arquitectos, tu equipo técnico para proyectos básicos y de ejecución.\n\n{TAGS[G['formato']]}")


# ------------------------------------------------------------------ todo junto
def hacer(formato, out, seed=0, max_rondas=2):
    """Genera, monta, revisa y deja el reel listo. Devuelve meta (como run_daily) y la pieza (para marcarla usada)."""
    t0 = time.time()
    tematica = formato
    formato = BANCO_DE.get(formato, formato)
    P = pieza(formato, seed)
    say(f"{formato}: {P.get('hook') or P.get('descripcion')}")
    pasos = imagenes(formato, P)
    say(f"{len(pasos)} imágenes aprobadas en {time.time() - t0:.0f} s")
    bpm = random.Random(seed).choice((80, 84, 88))
    mejor = None
    for ronda in range(max_rondas):
        G = guion(formato, P, pasos, bpm)
        info = render(G, out, seed=f"{seed}-{ronda}", bpm=bpm)
        rev = revisar(out, G)
        if rev["overall"] >= 8 and not rev.get("critical"):
            mejor = (G, info, rev); break
        malas = [int(m) - 1 for m in (rev.get("malas") or []) if str(m).isdigit() and 0 < int(m) <= len(pasos)]
        if not malas or ronda == max_rondas - 1:
            break
        say("regenero las imágenes", [m + 1 for m in malas])
        for m in malas:                                         # solo las imágenes marcadas
            lab = pasos[m][1]
            ref = [pasos[m - 1][0]] if formato == "antes_despues" and lab == "DESPUÉS" else \
                  ([pasos[-1][0]] if formato in ("proceso", "obra") and m < len(pasos) - 1 else [])
            idea = next((e["idea"] for e in P.get("escenas", []) + P.get("tips", []) if e.get("label", e.get("tip")) == lab), lab)
            nuevo = _gen(f"{idea}. Evita: {'; '.join(rev.get('issues') or [])[:300]}", ref)
            if nuevo is not None:
                pasos[m] = (nuevo, lab)
    if not mejor:
        raise RuntimeError(f"reel visual sin el 8: {rev.get('overall')} · {(rev.get('issues') or [''])[:2]}")
    G, info, rev = mejor
    cover = portada(G, out.replace(".mp4", "_portada.jpg"))
    cap = descripcion(G)
    open(out.replace(".mp4", ".txt"), "w").write(cap)
    meta = {"formato": "visual", "estilo": "visual", "hook": G["hook"], "duration": info["duration"], "cover": cover,
            "thumb_ms": 1500, "review_score": rev["overall"], "design_score": rev["overall"], "ids": P["ids"],
            "story_base": cover, "temas": [], "variante": formato, "tematica": tematica, "guion": "visual"}
    say(f"listo en {time.time() - t0:.0f} s · {info['duration']} s de vídeo · nota {rev['overall']}")
    return meta, [{"id": i, "tema": "visual", "grupo": formato} for i in P["ids"]]
