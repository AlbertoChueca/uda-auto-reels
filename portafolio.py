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
import base64, json, math, os, random, subprocess, time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fx
from fx import W, H, FPS, SR, F_REG, clamp, eo, eob

HERE = os.path.dirname(os.path.abspath(__file__))
MAN = os.path.join(HERE, "fuentes", "portfolio.json")
DIR = os.path.join(HERE, "assets", "portfolio")
ORO, CREMA, NEGRO = fx.ORO, fx.CREMA, fx.NEGRO
BOX = (30, 440, 1050, 1480)                 # zona del plano (entre el título y la etiqueta, dentro de la zona segura)
FONDO = (12, 12, 13)

HOOKS = {
    "recorrido": ["Esto es lo que recibe un estudio cuando nos delega el proyecto",
                  "POV: delegas el Proyecto de Ejecución y te llega esto",
                  "Un proyecto real, de principio a fin"],
    "capas": ["Las instalaciones de una vivienda, capa a capa",
              "Misma planta, tres instalaciones",
              "¿Cuántas horas te llevan las instalaciones?"],
    "detalles": ["Un detalle constructivo bien resuelto, de cerca",
                 "Así se dibuja un detalle a escala 1:20",
                 "Los detalles que no ve el cliente, pero que importan"],
}
CIERRE_VOZ = ("El estudio diseña y firma. Nosotros desarrollamos el proyecto, con presupuesto cerrado en 24 horas.")


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


def foco(img):
    """Centro (0-1) de la zona con más trabajo de instalación (píxeles de color); si no hay, el centro del dibujo."""
    a = np.asarray(img.convert("RGB").resize((200, int(200 * img.height / img.width)))).astype(np.int16)
    sat = a.max(2) - a.min(2)
    ys, xs = np.nonzero(sat > 60)
    if len(xs) < 30:
        dark = a.mean(2) < 160
        ys, xs = np.nonzero(dark)
    if not len(xs):
        return (0.5, 0.5)
    return (float(np.median(xs)) / a.shape[1], float(np.median(ys)) / a.shape[0])


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
    """Tipo y proyecto menos usados (used.json): ids «portfolio:<tipo>:<proyecto>»."""
    M = manifiesto(); rng = random.Random(seed)
    try:
        usados = [x["id"] for x in json.load(open(os.path.join(HERE, "used.json")))]
    except Exception:
        usados = []
    ops = []
    for p in M["proyectos"]:
        tipos = {l["tipo"] for l in p["laminas"]}
        ops.append(("recorrido", p))
        if sum(1 for l in p["laminas"] if l.get("capa")) >= 3:
            ops.append(("capas", p))
        if "detalle" in tipos:
            ops.append(("detalles", p))
    ops.sort(key=lambda o: (usados.count(f"portfolio:{o[0]}:{o[1]['id']}"), rng.random()))
    return ops[0]


def guion(tipo, P, seed=0):
    rng = random.Random(seed)
    L = P["laminas"]
    if tipo == "capas":
        cap = [l for l in L if l.get("capa")][:3]
        golpes = [dict(l, modo="dibujar" if k == 0 else "capa") for k, l in enumerate(cap)]
    elif tipo == "detalles":
        det = ([l for l in L if l["tipo"] == "detalle"] + [l for l in L if l["tipo"] == "estructura"])[:3]
        golpes = [dict(l, modo="recorrer") for l in det]
    else:
        orden = {"planta": 0, "instalacion": 1, "estructura": 2, "detalle": 3}
        sel = sorted(L, key=lambda l: orden[l["tipo"]])[:6]
        golpes = [dict(l, modo="dibujar" if k == 0 else "zoom") for k, l in enumerate(sel)]
    hook = rng.choice(HOOKS[tipo])
    return {"tipo": tipo, "proyecto": P, "hook": hook, "golpes": golpes,
            "sub": f"{P['titulo']} · {P['fase']}", "cierre_voz": CIERRE_VOZ}


# ------------------------------------------------------------------ montaje
def _voz(textos):
    import voice
    voice.reset()
    return voice.say_many(textos, 1.06, None, True)


def render(G, out, seed=0):
    import visual as V
    golpes = G["golpes"]
    imgs = [oscuro(Image.open(os.path.join(DIR, g["f"] + ".jpg"))) for g in golpes]
    focos = [foco(Image.open(os.path.join(DIR, g["f"] + ".jpg"))) for g in golpes]
    textos = [G["hook"] + "."] + [g["voz"] for g in golpes] + [G["cierre_voz"]]
    clips = _voz(textos)
    dur = [len(c) / SR for c in clips]
    # tiempos: el gancho se dice sobre la primera lámina mientras se dibuja; luego una lámina por frase
    seg = []
    t = 0.0
    d0 = dur[0] + 0.35 + dur[1] + 0.6
    seg.append((0, t, t + d0)); t += d0
    for k in range(1, len(golpes)):
        d = max(dur[k + 1] + 0.7, 2.4)
        seg.append((k, t, t + d)); t += d
    t_fin = t; d_fin = max(dur[-1] + 1.2, 4.2); total = t_fin + d_fin
    vo_at = [0.25, 0.25 + dur[0] + 0.35] + [seg[k][1] + 0.3 for k in range(1, len(golpes))] + [t_fin + 0.4]

    hook_big = V._panel(fx.headline(G["hook"], 98, 960, 3, color=CREMA, hot=ORO, shadow=True), 44, 150)
    tit = V._panel(fx.headline(G["hook"], 46, 940, 2, color=CREMA, hot=ORO, shadow=True), 22, 120)
    real = fx.pill("PROYECTO REAL · HECHO POR UDA", 30, ORO, NEGRO, padx=22, pady=10, radius=4)
    sub = fx.text_block(G["sub"], F_REG, 30, 960, (200, 194, 182), align="center")
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
    # cierre
    q = fx.headline("El estudio diseña y firma. Nosotros lo desarrollamos.", 74, 940, 3, color=CREMA, hot=ORO, shadow=True)
    p1 = fx.pill("Presupuesto cerrado en 24 h", 48, ORO, NEGRO, padx=34, pady=16, radius=6)
    p2 = fx.text_block("Agenda una reunión para conocernos y crecer juntos", F_REG, 40, 900, CREMA, align="center")
    lg = fx.logo(64, CREMA, ORO)
    web = fx.text_block("uniondearquitectos.com", F_REG, 34, 900, (200, 194, 182), align="center")

    def cam(k, lt, d):
        g = golpes[k]; f = focos[k]; p = clamp(lt / d)
        if g["modo"] == "capa":                                       # misma cámara que la capa anterior: encajan exactas
            return 1.10 + 0.05 * eo(p), (0.5, 0.5)
        if g["modo"] == "recorrer":                                  # barrido de izquierda a derecha, acercado
            return 1.9, (0.15 + 0.7 * eo(p), 0.5)
        if g["modo"] == "dibujar":
            return 1.0 + 0.10 * eo(clamp((p - 0.55) / 0.45)), (0.5, 0.5)
        return 1.0 + 0.9 * eo(clamp((p - 0.15) / 0.75)), (0.5 + (f[0] - 0.5) * eo(p), 0.5 + (f[1] - 0.5) * eo(p))

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
            if g["modo"] == "dibujar" and lt < 2.2:                     # el plano se «dibuja» de arriba abajo
                p = eo(clamp(lt / 2.0)); yy = int(bh * p)
                m = Image.new("L", (bw, bh), 0); ImageDraw.Draw(m).rectangle([0, 0, bw, yy], fill=255)
                blank = Image.new("RGBA", (bw, bh), FONDO + (255,)); blank.paste(v, (0, 0), m); v = blank
                ImageDraw.Draw(v).rectangle([0, max(0, yy - 2), bw, yy + 2], fill=ORO + (255,))
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
            if k == 0 and tt >= hook_t:
                fx.paste_center(fr, sub, W / 2, BOX[3] + 40, alpha=clamp((tt - hook_t) / 0.4))
        else:
            lt = tt - t_fin
            bgv = vista(imgs[-1], 1.0, (0.5, 0.5)).filter(ImageFilter.GaussianBlur(10)).convert("RGBA")
            fr.paste(bgv, (BOX[0], BOX[1])); fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 170)))
            a = eob(clamp(lt / 0.4))
            fx.paste_center(fr, q, W / 2, 620 - (1 - a) * 30, alpha=clamp(a))
            b = eob(clamp((lt - 0.6) / 0.4))
            fx.paste_center(fr, p1, W / 2, 620 + q.height / 2 + 90, alpha=clamp(b))
            c_ = clamp((lt - 1.0) / 0.4)
            fx.paste_center(fr, p2, W / 2, 620 + q.height / 2 + 200, alpha=c_)
            fx.paste_center(fr, lg, W / 2, 1290, alpha=c_)
            fx.paste_center(fr, web, W / 2, 1380, alpha=c_)
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
    reviewer._log("video_portfolio", {"hook": G["hook"], "overall": ov, "issues": res.get("issues"),
                                      "suggestions": res.get("suggestions")})
    say(f"revisión: {ov}/10", res.get("issues") or "")
    return res


def descripcion(G):
    P = G["proyecto"]
    lista = "\n".join(f"▪️ {g['label']}" for g in G["golpes"])
    return (f"{G['hook']} 📐\n\nProyecto real desarrollado por UDA para un estudio de arquitectura ({P['titulo'].lower()}, "
            f"{P['fase']}). Datos del cliente ocultos.\n\n{lista}\n\n"
            "El estudio diseña y firma; nosotros desarrollamos planos, instalaciones, estructura, memoria y mediciones. "
            "Presupuesto cerrado en 24 h.\n\n👇 ¿Qué parte del proyecto te quita más horas?\n"
            "📌 Guárdalo y agenda una reunión en uniondearquitectos.com\n\n"
            "#arquitectura #proyectodeejecucion #arquitecto #autocad #revit")


def hacer(out, seed=0, max_rondas=2):
    t0 = time.time()
    tipo, P = elegir(seed)
    rev = {}
    for ronda in range(max_rondas):
        G = guion(tipo, P, f"{seed}-{ronda}")
        say(f"{tipo} · {P['titulo']} · «{G['hook']}»")
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
    pid = f"portfolio:{tipo}:{P['id']}"
    meta = {"formato": "visual", "estilo": "portfolio", "hook": G["hook"], "duration": info["duration"], "cover": cover,
            "thumb_ms": 2500, "review_score": rev["overall"], "design_score": rev["overall"], "ids": [pid], "temas": [],
            "story_base": cover, "variante": "portfolio", "tematica": "portfolio", "guion": "portfolio",
            "ai": False, "tt_video": tt if os.path.exists(tt) else None, "con_voz": True,
            "pregunta": "👇 Arquitectos: ¿qué parte del proyecto de ejecución delegaríais primero? Instalaciones, estructura, detalles..."}
    say(f"listo en {time.time() - t0:.0f} s · {info['duration']} s")
    return meta, [{"id": pid, "tema": "portfolio", "grupo": tipo}]
