"""Reels con TRABAJOS REALES de UDA (assets/portfolio, manifiesto fuentes/portfolio.json): lo que recibe un estudio.

Las láminas son de proyectos reales hechos en marca blanca, recortadas al dibujo (sin cajetín, logotipos, calles,
coordenadas ni nombres). Nunca se nombra al cliente ni la localidad.

Tipos (rotan):
    recorrido   «Esto es lo que recibe un estudio cuando nos delega el proyecto»: planta, instalaciones, estructura, detalles
    capas       «Las instalaciones de una vivienda, capa a capa»: la misma planta con fontanería, electricidad, iluminación…
    detalles    «Un detalle constructivo bien resuelto, de cerca»: recorrido de cámara por secciones y detalles

Estilo: planos en «modo oscuro» (la línea en crema y el color de cada instalación conservado, sobre negro), cámara
que recorre y se acerca a donde está el trabajo (las zonas con más instalación), trazado que se «dibuja» al entrar,
etiqueta dorada por lámina, voz de arquitecto que cuenta lo que se ve y cierre con la propuesta de UDA.
"""
import re, io, base64, json, math, os, random, subprocess, time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fx
from fx import W, H, FPS, SR, F_REG, F_BOLD, clamp, eo, eob

HERE = os.path.dirname(os.path.abspath(__file__))
MAN = os.path.join(HERE, "fuentes", "portfolio.json")
DIR = os.path.join(HERE, "assets", "portfolio")
ORO, CREMA, NEGRO = fx.ORO, fx.CREMA, fx.NEGRO
BOX = (30, 430, 1050, 1390)                 # zona del plano (entre el título y la etiqueta, dentro de la zona segura)
FONDO = (12, 12, 13)

HOOKS = {
    "proyecto": ["POV: delegas el Proyecto de Ejecución y te llega esto",
                 "Esto es lo que entregamos a un estudio de arquitectura",
                 "Un proyecto real, lámina a lámina"],
    "instalaciones": ["¿Cuántas horas te llevan las instalaciones?",
                      "Instalaciones de tres viviendas reales",
                      "Fontanería, electricidad, saneamiento: así las dejamos"],
    "estructura": ["Del forjado al detalle 1:20",
                   "Los detalles que el cliente nunca ve",
                   "Estructura y detalles de proyectos reales"],
}
CIERRE_VOZ = "Desarrollado por UDA para un estudio de arquitectura."
MIN_LAMINA = 5.0                         # segundos mínimos por lámina: que dé tiempo a verla entera y su detalle
ZOOM = 2.1


def say(*a):
    print("portfolio:", *a, flush=True)


# ------------------------------------------------------------------ material
def manifiesto():
    return json.load(open(MAN))


def oscuro(img):
    """Plano en modo oscuro: la línea en crema cálido sobre negro y cada instalación en su color, más gruesa y luminosa
    (en el móvil, las líneas finas de color se perderían)."""
    rgb = img.convert("RGB")
    a = np.asarray(rgb).astype(np.float32) / 255
    mx, mn = a.max(2), a.min(2); L = (mx + mn) / 2
    out = np.clip(a + ((1 - L) - L)[..., None], 0, 1)                # invierte la luminosidad, conserva el matiz
    gray = (mx - mn) < 0.12
    out[gray] = out[gray] * np.array([1.0, 0.95, 0.86])               # línea en crema cálido, no blanco frío
    out = out * 0.92 + np.array(FONDO) / 255 * 0.08
    # instalaciones: el color original, saturado y engrosado
    col = (mx - mn) > 0.22
    if col.any():
        k = max(3, int(round(min(rgb.size) / 450)) * 2 + 1)
        pura = (a - mn[..., None]) / np.maximum((mx - mn)[..., None], 1e-3)   # el matiz puro, a toda saturación
        vivo = np.clip(pura * 0.82 + 0.18, 0, 1)
        cimg = Image.fromarray((vivo * col[..., None] * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))
        m = Image.fromarray((col * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))
        c2 = np.asarray(cimg).astype(np.float32) / 255; m2 = np.asarray(m).astype(np.float32)[..., None] / 255
        out = out * (1 - m2) + c2 * m2
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def foco(img, z=2.1):
    """Centro (0-1) de la ventana que verá la cámara al acercarse (z) con más trabajo dibujado: instalación (color) si
    la hay; si no, la zona con más líneas. Así el zoom cae siempre sobre el detalle, nunca sobre un hueco vacío."""
    a = np.asarray(img.convert("RGB").resize((240, max(1, int(240 * img.height / img.width))))).astype(np.int16)
    sat = (a.max(2) - a.min(2)) > 60
    m = sat if sat.sum() > 40 else (a.mean(2) < 150)
    if not m.any():
        return (0.5, 0.5)
    hh, ww = m.shape
    bw, bh = BOX[2] - BOX[0], BOX[3] - BOX[1]
    s_ = min(bw / ww, bh / hh) * z                                   # tamaño de la ventana en la imagen reducida
    vw, vh = max(4, int(bw / s_)), max(4, int(bh / s_))
    ii = np.pad(m.astype(np.float32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    best, bc = -1, (0.5, 0.5)
    for y in range(0, max(1, hh - vh + 1), 3):
        for x in range(0, max(1, ww - vw + 1), 3):
            y1, x1 = min(hh, y + vh), min(ww, x + vw)
            v = ii[y1, x1] - ii[y, x1] - ii[y1, x] + ii[y, x]
            if v > best:
                best, bc = v, ((x + x1) / 2 / ww, (y + y1) / 2 / hh)
    return bc


# ------------------------------------------------------------------ cámara
def vista(img, z, c):
    """Lo que ve la cámara dentro de BOX: imagen contenida (z=1) o acercada (z>1) al centro c (0-1)."""
    bw, bh = BOX[2] - BOX[0], BOX[3] - BOX[1]
    iw, ih = img.size
    s = min(bw / iw, bh / ih) * z
    vw, vh = bw / s, bh / s                                            # ventana en píxeles de la imagen
    cx = min(max(c[0] * iw, vw / 2), iw - vw / 2) if vw < iw else iw / 2
    cy = min(max(c[1] * ih, vh / 2), ih - vh / 2) if vh < ih else ih / 2
    x0, y0 = cx - vw / 2, cy - vh / 2
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(iw, x0 + vw), min(ih, y0 + vh)
    out = Image.new("RGB", (bw, bh), FONDO)
    if sx1 > sx0 and sy1 > sy0:
        dx0, dy0 = (sx0 - x0) * s, (sy0 - y0) * s
        dw, dh = (sx1 - sx0) * s, (sy1 - sy0) * s
        part = img.resize((max(1, int(dw)), max(1, int(dh))), Image.BICUBIC, box=(sx0, sy0, sx1, sy1))
        out.paste(part, (int(dx0), int(dy0)))
    return out


# ------------------------------------------------------------------ guion
def elegir(seed=0):
    """Tipo de reel menos usado (used.json): un proyecto entero, o un tema (instalaciones / estructura) con láminas de
    los tres proyectos. ids «portfolio:<tipo>:<proyecto o tema>»."""
    M = manifiesto(); rng = random.Random(seed)
    try:
        usados = [x["id"] for x in json.load(open(os.path.join(HERE, "used.json")))]
    except Exception:
        usados = []
    ops = [("proyecto", p["id"]) for p in M["proyectos"]] + [("instalaciones", "todos"), ("estructura", "todos")]
    ops.sort(key=lambda o: (sum(1 for u in usados if u.startswith(f"portfolio:{o[0]}:{o[1]}")), rng.random()))
    return ops[0]


def guion(tipo, cual, seed=0):
    rng = random.Random(seed)
    M = manifiesto()
    proy = {p["id"]: p for p in M["proyectos"]}
    sel = []
    if tipo == "proyecto":
        orden = {"planta": 0, "instalacion": 1, "estructura": 2, "detalle": 3}
        sel = [(proy[cual], l) for l in sorted(proy[cual]["laminas"], key=lambda l: orden[l["tipo"]])]
    else:
        quiero = ("instalacion",) if tipo == "instalaciones" else ("estructura", "detalle")
        for p in M["proyectos"]:
            sel += [(p, l) for l in p["laminas"] if l["tipo"] in quiero]
        sel = sel[:7]
    golpes = []
    for k, (p, l) in enumerate(sel):
        prev = golpes[-1] if golpes else None
        capa = bool(l.get("capa") and prev and prev.get("capa") == l.get("capa"))
        modo = "capa" if capa else "recorrer" if l["tipo"] == "detalle" else "zoom"
        golpes.append(dict(l, modo=modo, proyecto=p["titulo"], fase=p["fase"], primero=(k == 0)))
    hook = rng.choice(HOOKS[tipo])
    sub = f"{sel[0][0]['titulo']} · {sel[0][0]['fase']}" if tipo == "proyecto" else "Proyectos reales desarrollados por UDA"
    return {"tipo": tipo, "cual": cual, "hook": hook, "golpes": golpes, "sub": sub, "cierre_voz": CIERRE_VOZ,
            "proyecto": proy.get(cual)}


def comentar(G):
    """Voz de arquitecto lámina a lámina, a partir de lo que se VE en cada plano (Gemini mira la imagen). Si falla, las
    frases del manifiesto."""
    try:
        import gemini
        partes = [{"text": f"""Eres arquitecto en España y comentas a otros arquitectos, en un reel, láminas REALES de un
proyecto que tu equipo (UDA) desarrolló para un estudio. Titular: «{G['hook']}». Para CADA lámina escribe "voz": 1 o 2
frases habladas, 12 a 20 palabras en total, que digan algo CONCRETO que se ve en ese plano (qué resuelve, cómo está
organizado, qué cuidado tiene) con naturalidad, como quien lo enseña a un colega con orgullo. Español de España.
Prohibido: nombres de clientes, estudios, calles o municipios, fechas, precios, normativa, cifras que no se lean en el
plano, palabras de venta («contrata», «presupuesto», «servicio»), y empezar todas igual. La primera menciona la etiqueta.
Devuelve JSON: {{"frases": [str]}}"""}]
        for k, g in enumerate(G["golpes"]):
            im = Image.open(os.path.join(DIR, g["f"] + ".jpg")).convert("RGB"); im.thumbnail((1100, 1100))
            b = io.BytesIO(); im.save(b, "JPEG", quality=82)
            partes += [{"text": f"Lámina {k + 1}: {g['label']} ({g['proyecto']})"},
                       {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
        fr = [str(f).strip() for f in (gemini.ask(partes, 0.7).get("frases") or [])]
        malas = re.compile(r"presupuesto|contrat|servicio|precio|\bcalle\b|municipio", re.I)
        if len(fr) != len(G["golpes"]) or any(not f or len(f.split()) > 30 or malas.search(f) for f in fr):
            raise ValueError(f"frases no válidas: {fr[:2]}")
        for g, f in zip(G["golpes"], fr):
            g["voz"] = f
        say("voz escrita a partir de las láminas")
    except Exception as e:
        say("voz del manifiesto (comentario por imagen no disponible):", str(e)[:150])


# ------------------------------------------------------------------ montaje
def _escala(t):
    """«1:20» se lee «uno a veinte» (el sintetizador lo leía como una hora)."""
    return re.sub(r"\b1:(\d+)\b", r"uno a \1", t)


ESTILOS = ["intrigued and punchy, a real question to a colleague, pitch rising at the end",
           "proud and lively, like showing your own drawing to a friend, stress the key technical word",
           "lower and confident, slower on the important detail, a small pause before it",
           "enthusiastic, a smile in the voice, quicker pace",
           "thoughtful, conversational, natural ups and downs",
           "warm, relaxed, lower pitch and unhurried, friendly sign-off, never a sales pitch"]


def _voz(textos):
    import voice
    textos = [_escala(t) for t in textos]
    n = len(textos)
    estilos = [ESTILOS[0]] + [ESTILOS[1 + (k % 4)] for k in range(n - 2)] + [ESTILOS[5]]
    return voice.expresiva(textos, estilos)


def render(G, out, seed=0):
    import visual as V
    golpes = G["golpes"]
    imgs = [oscuro(Image.open(os.path.join(DIR, g["f"] + ".jpg"))) for g in golpes]
    focos = [foco(Image.open(os.path.join(DIR, g["f"] + ".jpg"))) for g in golpes]
    textos = [G["hook"]] + [g["voz"] for g in golpes] + [G["cierre_voz"]]
    clips = _voz(textos)
    dur = [len(c) / SR for c in clips]
    # tiempos: el gancho se dice sobre la primera lámina mientras se dibuja; luego una lámina por frase, sin prisas
    seg = []
    t = 0.0
    d0 = max(dur[0] + 0.35 + dur[1] + 1.0, MIN_LAMINA + 2.0)
    seg.append((0, t, t + d0)); t += d0
    for k in range(1, len(golpes)):
        d = max(dur[k + 1] + 1.0, MIN_LAMINA)
        seg.append((k, t, t + d)); t += d
    t_fin = t; d_fin = max(dur[-1] + 0.9, 2.8); total = t_fin + d_fin
    vo_at = [0.25, 0.25 + dur[0] + 0.35] + [seg[k][1] + 0.35 for k in range(1, len(golpes))] + [t_fin + 0.3]

    hook_big = V._panel(fx.headline(G["hook"], 98, 960, 3, color=CREMA, hot=ORO, shadow=True), 44, 150)
    tit = V._panel(fx.headline(G["hook"], 46, 940, 2, color=CREMA, hot=ORO, shadow=True), 22, 120)
    real = fx.pill("PROYECTO REAL · HECHO POR UDA", 30, ORO, NEGRO, padx=22, pady=10, radius=4)
    subs = [fx.text_block(G["sub"] if G["tipo"] == "proyecto" else f"{g['proyecto']} · {g['fase']}", F_BOLD, 32, 960,
                          (236, 228, 212), align="center") for g in golpes]
    labs = []
    for k, g in enumerate(golpes):
        num = fx.pill(f"{k + 1:02d}", 50, ORO, NEGRO, padx=22, pady=12, radius=6)
        txt = fx.pill(g["label"], 50, (18, 17, 15), CREMA, padx=26, pady=12, radius=6)
        im = Image.new("RGBA", (num.width + txt.width + 12, max(num.height, txt.height)), (0, 0, 0, 0))
        im.alpha_composite(num, (0, 0)); im.alpha_composite(txt, (num.width + 12, 0)); labs.append(im)
    fondo = Image.new("RGBA", (W, H), FONDO + (255,))
    gd = ImageDraw.Draw(fondo)
    for y in range(H):                                              # degradado sutil, como un estudio de noche
        v = int(10 + 10 * math.sin(math.pi * y / H))
        gd.line([(0, y), (W, y)], fill=(v + 2, v + 1, v, 255))
    marco = Image.new("RGBA", (W, H), (0, 0, 0, 0)); md = ImageDraw.Draw(marco)
    md.rectangle([BOX[0] - 2, BOX[1] - 2, BOX[2] + 1, BOX[3] + 1], outline=(70, 62, 46, 255), width=2)
    # cierre corto, sin vender: la marca y la web
    q = fx.headline("Desarrollado por UDA para un estudio de arquitectura", 64, 920, 3, color=CREMA, hot=ORO, shadow=True)
    lg = fx.logo(70, CREMA, ORO)
    web = fx.text_block("uniondearquitectos.com", F_REG, 34, 900, (200, 194, 182), align="center")

    # cámara por lámina: puntos clave (fracción, zoom, cx, cy); entre ellos, suavizado. Plano entero -> detalle.
    rutas = []
    for k, g in enumerate(golpes):
        d = seg[k][2] - seg[k][1]; f = focos[k]
        ver = max(0.35, 2.6 / d) if k == 0 else 0.33                 # tiempo para ver la lámina entera
        if g["modo"] == "capa":                                     # misma cámara que la anterior y vuelta al conjunto
            pz = rutas[-1][-1][1:]
            fin = (1.0, 0.5, 0.5) if pz[0] > 1.2 else (ZOOM, *focos[k - 1])
            r = [(0, *pz), (0.3, *pz), (1, *fin)]
        elif g["modo"] == "recorrer":                               # detalles: se recorre la lámina de lado a lado
            r = [(0, 1, .5, .5), (ver, 1, .5, .5), (ver + .15, 1.85, .3, f[1]), (1, 1.85, .7, f[1])]
        else:
            r = [(0, 1, .5, .5), (ver, 1, .5, .5), (1, ZOOM, f[0], f[1])]
        rutas.append(r)

    def cam(k, lt, d):
        r = rutas[k]; p = clamp(lt / d)
        for (p0, *a), (p1, *b) in zip(r, r[1:]):
            if p <= p1:
                u = eo(clamp((p - p0) / max(1e-6, p1 - p0)))
                return a[0] + (b[0] - a[0]) * u, (a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)
        return r[-1][1], (r[-1][2], r[-1][3])

    # ---- audio
    n = int(SR * (total + 0.3))
    vo = np.zeros(n, np.float32)
    for c, at in zip(clips, vo_at):
        i = int(at * SR); j = min(n, i + len(c)); vo[i:j] += c[: j - i]
    music = fx.premium_beat(total + 0.3, 84, seed=seed, energy=0.9)
    music = np.pad(music, (0, max(0, n - len(music))))[:n]
    venv = np.convolve((np.abs(vo) > 0.01).astype(np.float32), np.ones(3000) / 3000, "same")
    sfx = np.zeros(n, np.float32)

    def put(a, at, gain=1.0):
        i = int(at * SR)
        if i < 0: a = a[-i:]; i = 0
        j = min(n, i + len(a)); sfx[i:j] += a[: j - i] * gain
    put(fx.impact(), 0.0, 0.6)
    for _, a_, _b in seg[1:]:
        put(fx.whoosh2(0.4), a_ - 0.3, 0.6)
    put(fx.whoosh2(0.4), t_fin - 0.3, 0.6); put(fx.shimmer(), t_fin + 0.2, 0.5)
    mix = vo * 1.15 + sfx + music * (0.40 - 0.28 * np.clip(venv * 3, 0, 1))
    mix = fx.dehiss(np.tanh(mix * 1.05) * 0.92)
    wav = out.replace(".mp4", ".wav")
    import soundfile as sf
    sf.write(wav, mix, SR)
    sf.write(out.replace(".mp4", "_voz.wav"), np.tanh((vo * 1.15 + sfx) * 1.05) * 0.92, SR)   # para TikTok con su música

    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", wav, "-shortest", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "20", "-maxrate", "8M", "-bufsize", "12M", "-g", str(FPS * 2), "-pix_fmt", "yuv420p",
                             "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                             "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    bw, bh = BOX[2] - BOX[0], BOX[3] - BOX[1]
    for fi in range(int(total * FPS)):
        tt = fi / FPS
        fr = fondo.copy()
        if tt < t_fin:
            k = max(i for i, s_ in enumerate(seg) if s_[1] <= tt)
            _, a_, b_ = seg[k]; lt = tt - a_; d = b_ - a_
            z, c = cam(k, lt, d)
            v = vista(imgs[k], z, c).convert("RGBA")
            g = golpes[k]
            if g["modo"] == "capa" and k > 0:                            # la nueva capa aparece sobre la anterior
                prev = vista(imgs[k - 1], z, c).convert("RGBA")
                v = Image.blend(prev, v, eo(clamp(lt / 0.9)))
            elif k > 0 and lt < 0.25:
                prev = vista(imgs[k - 1], *cam(k - 1, seg[k - 1][2] - seg[k - 1][1], seg[k - 1][2] - seg[k - 1][1])).convert("RGBA")
                v = Image.blend(prev, v, lt / 0.25)
            if k == 0 and lt < 0.6:                                    # la primera lámina aparece con un fundido
                v = Image.blend(Image.new("RGBA", v.size, FONDO + (255,)), v, eo(lt / 0.6))
            fr.paste(v, (BOX[0], BOX[1]))
            fr.alpha_composite(marco)
            hook_t = dur[0] + 0.6
            if tt < hook_t:
                a = eob(clamp(tt / 0.35)) * (1 - clamp((tt - hook_t + 0.25) / 0.25))
                fx.paste_center(fr, hook_big, W / 2, 330 + hook_big.height / 2 - 60, alpha=clamp(a))
            else:
                fx.paste_center(fr, tit, W / 2, 300 + tit.height / 2)
                fx.paste_center(fr, real, W / 2, 300 + tit.height + 26)
            if not (k == 0 and tt < hook_t):
                la = labs[k]; a = eo(clamp((lt - (hook_t if k == 0 else 0.3)) / 0.3))
                fx.paste_center(fr, la, W / 2, BOX[3] - 70 - (1 - a) * 20, alpha=a)
            if not (k == 0 and tt < hook_t):
                fx.paste_center(fr, subs[k], W / 2, BOX[3] + 40, alpha=clamp((lt - (hook_t if k == 0 else 0.3)) / 0.4))
        else:
            lt = tt - t_fin
            bgv = vista(imgs[-1], 1.0, (0.5, 0.5)).filter(ImageFilter.GaussianBlur(10)).convert("RGBA")
            fr.paste(bgv, (BOX[0], BOX[1])); fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 170)))
            a = eob(clamp(lt / 0.4))
            fx.paste_center(fr, q, W / 2, 760 - (1 - a) * 30, alpha=clamp(a))
            c_ = clamp((lt - 0.5) / 0.4)
            fx.paste_center(fr, lg, W / 2, 760 + q.height / 2 + 140, alpha=c_)
            fx.paste_center(fr, web, W / 2, 760 + q.height / 2 + 230, alpha=c_)
        proc.stdin.write(fr.convert("RGB").tobytes())
    proc.stdin.close(); proc.wait(); os.remove(wav)
    if proc.returncode:
        raise RuntimeError("ffmpeg falló al codificar el reel de portfolio")
    return {"duration": round(total, 1), "seg": seg, "t_fin": t_fin, "lineas": textos}


def portada(G, path):
    import infoviz as IV, themes
    T = themes.get("negro")
    g0 = G["golpes"][min(1, len(G["golpes"]) - 1)]
    img = oscuro(Image.open(os.path.join(DIR, g0["f"] + ".jpg")))
    base = Image.new("RGBA", (W, H), FONDO + (255,))
    v = vista(img, 1.25, foco(Image.open(os.path.join(DIR, g0["f"] + ".jpg")))).convert("RGBA")
    base.paste(v, (BOX[0], BOX[1] + 120))
    base.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
    hl = fx.headline(G["hook"], 104, 960, 4, color=CREMA, hot=ORO, shadow=True)
    import visual as V
    fx.paste_center(base, V._panel(hl, 40, 160), W / 2, IV.GRID[0] + 160 + hl.height / 2)
    fx.paste_center(base, fx.pill("PROYECTO REAL · HECHO POR UDA", 36, ORO, NEGRO, padx=26, pady=12, radius=4), W / 2, IV.GRID[1] - 250)
    IV.frame(base, T)
    fx.paste_center(base, fx.logo(52, CREMA, ORO), W / 2, IV.GRID[1] - 90)
    base.convert("RGB").save(path, "JPEG", quality=92)
    return path


def revisar(path, G):
    import reviewer
    small = path.replace(".mp4", "_review.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "scale=360:640", "-r", "12", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "48k", small], check=True)
        data = base64.b64encode(open(small, "rb").read()).decode()
        res = reviewer._ask([{"text": f"""Eres director creativo de una cuenta de arquitectura para FUNDADORES DE
DESPACHOS. Revisa este reel con PLANOS REALES de un proyecto que UDA desarrolló para un estudio (en «modo oscuro», a
propósito). Gancho: «{G['hook']}». Voz (sintética de España, a propósito): {' / '.join(G.get('lineas', []))}.
Comprueba: que la voz diga lo mismo que las etiquetas y textos en pantalla, que los textos superpuestos se lean en el
móvil y no los tape la interfaz, que el gancho se entienda en 1,5 s, ritmo, que se vea premium e impresione a un
arquitecto, y que NO aparezca ningún dato sensible (nombre de cliente o estudio, calle, dirección, coordenadas,
teléfono). El texto pequeño DENTRO del plano no tiene que leerse: es parte del dibujo.
ESCALA ANCLADA: 8 = profesional y publicable SIN defectos objetivos (lo de estilo va en "suggestions"); 6-7 = algún
defecto objetivo (voz distinta del texto, texto superpuesto ilegible o que se sale, corte de audio); 5 o menos = grave
(dato sensible visible, vídeo roto, voz ininteligible).
Devuelve JSON: {{"overall": number, "issues": [str], "suggestions": [str], "critical": bool}}"""},
                             {"inline_data": {"mime_type": "video/mp4", "data": data}}], 0.3)
    except Exception as e:
        say("revisión no disponible:", str(e)[:200])
        return {"overall": 0, "issues": [f"revisor no disponible: {str(e)[:100]}"]}
    finally:
        if os.path.exists(small): os.remove(small)
    ov = float(res.get("overall") or 0)
    if ov < 8 and not (res.get("issues") or []) and not res.get("critical"):
        res["overall_raw"] = ov; ov = 8.0
    res["overall"] = ov
    import voice
    reviewer._log("video_portfolio", {"hook": G["hook"], "overall": ov, "issues": res.get("issues"), "voz": voice.ENGINE_USED,
                                      "suggestions": res.get("suggestions")})
    say(f"revisión: {ov}/10", res.get("issues") or "")
    return res


def descripcion(G):
    lista = "\n".join(f"▪️ {g['label']}" + ("" if G["tipo"] == "proyecto" else f" · {g['proyecto'].lower()}")
                      for g in G["golpes"])
    contexto = (f"Proyecto real ({G['proyecto']['titulo'].lower()}, {G['proyecto']['fase']}) que desarrollamos para un "
                "estudio de arquitectura." if G["tipo"] == "proyecto" else
                "Láminas reales de proyectos que desarrollamos para estudios de arquitectura.")
    return (f"{G['hook']} 📐\nproyecto de ejecución · planos de arquitectura · instalaciones y estructura\n\n"
            f"{contexto} El estudio diseña y firma; nosotros lo desarrollamos. Datos del cliente ocultos.\n\n{lista}\n\n"
            "👇 ¿Qué parte del proyecto te lleva más horas?\n\n"
            "#arquitectura #proyectodeejecucion #arquitecto #autocad #planos")


def hacer(out, seed=0, max_rondas=2):
    t0 = time.time()
    tipo, cual = elegir(seed)
    rev = {}
    for ronda in range(max_rondas):
        G = guion(tipo, cual, f"{seed}-{ronda}")
        comentar(G)
        say(f"{tipo} · {cual} · «{G['hook']}» · {len(G['golpes'])} láminas")
        info = render(G, out, seed=f"{seed}-{ronda}")
        G["lineas"] = info["lineas"]
        rev = revisar(out, G)
        if rev["overall"] >= 8 and not rev.get("critical"):
            break
    else:
        raise RuntimeError(f"portfolio sin el 8: {rev.get('overall')} · {(rev.get('issues') or [''])[:2]}")
    cover = portada(G, out.replace(".mp4", "_portada.jpg"))
    tt = out.replace(".mp4", "_tiktok.mp4")                            # para TikTok: solo voz y efectos (su música encima)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-i", out.replace(".mp4", "_voz.wav"), "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-shortest", tt])
    open(out.replace(".mp4", ".txt"), "w").write(descripcion(G))
    pid = f"portfolio:{tipo}:{cual}"
    meta = {"formato": "visual", "estilo": "portfolio", "hook": G["hook"], "duration": info["duration"], "cover": cover,
            "thumb_ms": 2500, "review_score": rev["overall"], "design_score": rev["overall"], "ids": [pid], "temas": [],
            "story_base": cover, "variante": "portfolio", "tematica": "portfolio", "guion": "portfolio",
            "ai": False, "tt_video": tt if os.path.exists(tt) else None, "con_voz": True,
            "pregunta": "👇 Arquitectos: ¿qué parte del proyecto de ejecución delegaríais primero? Instalaciones, estructura, detalles..."}
    say(f"listo en {time.time() - t0:.0f} s · {info['duration']} s")
    return meta, [{"id": pid, "tema": "portfolio", "grupo": tipo}]
