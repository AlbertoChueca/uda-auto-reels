"""Reel con presentadora creada con IA (solo Instagram): una ejecutiva elegante explica, en sencillo, cómo ayuda UDA.

    python presentadora.py modelos    # qué modelos de vídeo (Veo) e imagen puede usar la clave de Gemini
    python presentadora.py generar    # crea el vídeo -> previews/presentadora.mp4 (+ portada y transcripción). No publica.
    python presentadora.py publicar   # publica previews/presentadora.mp4 SOLO en Instagram (reel)

Cómo se hace:
  1. Retrato de la presentadora (Gemini imagen). Se guarda en assets/presentadora.png y se reutiliza siempre: es la
     misma persona en todos los planos y en futuros reels.
  2. Cada frase del guion es un plano de 8 s con Veo (vídeo + voz en el mismo modelo: los labios van sincronizados),
     partiendo del retrato. Se pide castellano de España.
  3. Cada plano se comprueba con Whisper: tiene que decir la frase del guion (si no, se repite, hasta 3 veces).
  4. Montaje: planos recortados al final de la frase + subtítulos en negro y oro + etiqueta + música suave + tarjeta
     final de UDA (Agenda una reunión). La descripción dice que la presentadora está creada con IA.
Guion: solo hechos de assets/uda/hechos.md.
"""
import base64, difflib, json, os, re, subprocess, sys, time

import numpy as np
import requests
from PIL import Image, ImageDraw

import fx
import gemini
import marca as M

HERE = os.path.dirname(os.path.abspath(__file__))
PREV = os.path.join(HERE, "previews")
RETRATO = os.path.join(HERE, "assets", "presentadora.png")
BASE = "https://generativelanguage.googleapis.com/v1beta"
W, H, FPS = 1080, 1920, 25

GUION = [
    "¿Tu estudio va a tope y no quieres contratar a nadie más? En UDA somos tu equipo técnico.",
    "Tú diseñas y firmas. Nosotros hacemos planos, estructuras, instalaciones, memorias y mediciones.",
    "Te damos un presupuesto cerrado en veinticuatro horas, y puedes repercutirlo a tu cliente.",
    "Así aceptas más encargos y facturas más. Agenda una reunión para conocernos y crecer juntos.",
]
SUBS = [g.replace("veinticuatro horas", "24 horas") for g in GUION]       # en pantalla, con cifras

RETRATO_PROMPT = (
    "Fotografía editorial hiperrealista, vertical 9:16. Una ejecutiva española elegante de unos 38 años, pelo castaño "
    "oscuro recogido en un moño bajo pulido, maquillaje natural, americana negra entallada sobre blusa de seda color "
    "crema, pendientes pequeños de oro. De pie, plano medio (de la cintura hacia arriba), mirando a cámara con una "
    "sonrisa serena y segura. Fondo: estudio de arquitectura contemporáneo y minimalista, hormigón visto, madera de "
    "roble, grandes ventanales con luz cálida de tarde, maquetas blancas desenfocadas al fondo. Paleta negra, crema y "
    "oro. Iluminación suave de cine, piel natural con textura real, enfoque nítido en la cara. Sin texto, sin logotipos.")

PLANO_PROMPT = (
    "La mujer de la imagen habla directamente a cámara, con naturalidad y seguridad, como una directora que explica algo "
    "sencillo a un colega. Gestos suaves y elegantes con las manos, ligera inclinación de cabeza, sonrisa cálida. "
    "Cámara fija en plano medio, con un leve acercamiento lento. Dice exactamente, en español de España (acento "
    "castellano peninsular, de Madrid, nada de acento latinoamericano), con voz femenina cálida, clara y profesional, "
    "a ritmo natural: \"{frase}\" "
    "Sonido: solo su voz, nítida, en un estudio tranquilo. Sin música, sin subtítulos, sin texto en pantalla.")
NEGATIVO = "subtítulos, texto, letras, marca de agua, música, acento latinoamericano, distorsión de la cara, manos deformes"


def _h():
    return {"x-goog-api-key": gemini.key()}


def modelos():
    todos, tok = [], None
    while True:
        r = requests.get(f"{BASE}/models", params={"pageSize": 1000, **({"pageToken": tok} if tok else {})},
                         headers=_h(), timeout=60).json()
        todos += r.get("models", []); tok = r.get("nextPageToken")
        if not tok:
            break
    print("modelos en total:", len(todos), flush=True)
    out = {}
    for m in todos:
        n = m["name"].split("/")[-1]
        if any(x in n for x in ("veo", "image", "imagen")):
            out[n] = m.get("supportedGenerationMethods")
    print(json.dumps(out, indent=1), flush=True)
    return out


def _veo_model():
    pref = os.environ.get("VEO_MODEL")
    if pref:
        return pref
    ms = [n for n, met in modelos().items() if "veo" in n and "predictLongRunning" in (met or [])]
    ms.sort(key=lambda n: (-float((re.findall(r"veo-(\d+(?:\.\d+)?)", n) or ["0"])[0]), "fast" in n, "preview" in n))
    if not ms:
        raise RuntimeError("esta clave de Gemini no tiene acceso a Veo (vídeo)")
    return ms[0]


# ------------------------------------------------------------------ 1. retrato
def retrato():
    if os.path.exists(RETRATO):
        return Image.open(RETRATO).convert("RGB")
    im = gemini.image(RETRATO_PROMPT, aspect="9:16")
    os.makedirs(os.path.dirname(RETRATO), exist_ok=True)
    im.save(RETRATO)
    print("retrato nuevo guardado en", RETRATO, flush=True)
    return im


# ------------------------------------------------------------------ 2. planos con Veo
def veo(model, frase, img, out, seed=None):
    import io
    b = io.BytesIO(); img.save(b, "PNG")
    inst = {"prompt": PLANO_PROMPT.format(frase=frase),
            "image": {"bytesBase64Encoded": base64.b64encode(b.getvalue()).decode(), "mimeType": "image/png"}}
    params = {"aspectRatio": "9:16", "personGeneration": "allow_adult", "negativePrompt": NEGATIVO, "durationSeconds": 8}
    if seed is not None:
        params["seed"] = seed
    body = {"instances": [inst], "parameters": params}
    r = requests.post(f"{BASE}/models/{model}:predictLongRunning", headers={**_h(), "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code >= 400 and "seed" in r.text:              # algunos modelos no aceptan semilla
        params.pop("seed", None)
        r = requests.post(f"{BASE}/models/{model}:predictLongRunning", headers={**_h(), "Content-Type": "application/json"},
                          json=body, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Veo {r.status_code}: {r.text[:500]}")
    op = r.json()["name"]
    for _ in range(90):                                         # hasta ~15 min
        time.sleep(10)
        j = requests.get(f"{BASE}/{op}", headers=_h(), timeout=60).json()
        if j.get("done"):
            if j.get("error"):
                raise RuntimeError(f"Veo: {j['error']}")
            resp = j.get("response", {}).get("generateVideoResponse", {})
            samples = resp.get("generatedSamples") or []
            if not samples:
                raise RuntimeError(f"Veo no devolvió vídeo (¿filtro?): {json.dumps(resp)[:400]}")
            uri = samples[0]["video"]["uri"]
            v = requests.get(uri, headers=_h(), timeout=300, allow_redirects=True)
            open(out, "wb").write(v.content)
            return out
    raise RuntimeError("Veo: tiempo de espera agotado")


_ASR = []


def transcribe(path):
    from faster_whisper import WhisperModel
    if not _ASR:
        _ASR.append(WhisperModel(os.environ.get("ASR_MODEL", "small"), device="cpu", compute_type="int8"))
    segs, info = _ASR[0].transcribe(path, language="es", word_timestamps=True, vad_filter=True)
    words = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])]
    return words, info


def _norm(t):
    return re.sub(r"[^a-záéíóúñü ]", "", t.lower().replace("24", "veinticuatro")).split()


def parecido(a, b):
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


# ------------------------------------------------------------------ 3. montaje
def _sub_img(text, size=58):
    """Subtítulo: texto crema con la palabra clave en oro, sobre una franja negra translúcida (zona segura)."""
    tb = fx.text_block(text, fx.F_BOLD, size, 900, fx.CREMA, align="center")
    bb = tb.getbbox() or (0, 0, tb.width, tb.height)
    pad = 26
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width - 1, im.height - 1], 14, fill=(10, 10, 10, 190))
    im.alpha_composite(tb.crop(bb), (pad, pad))
    return im


def _chunks(words, n=4):
    """Subtítulos de 3-5 palabras sincronizados con la voz (tiempos de Whisper)."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or w[0].endswith((".", ",", "?", "!")):
            out.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2])); cur = []
    if cur:
        out.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2]))
    return out


def montar(clips, out):
    """clips: [(ruta, fin_de_frase_en_s, palabras)] -> reel final con subtítulos, etiqueta, música y tarjeta final."""
    import soundfile as sf
    import themes
    import make_quiz as MQ
    T = themes.get("negro"); MQ.T = T
    tmpd = os.path.join(PREV, "tmp"); os.makedirs(tmpd, exist_ok=True)
    # 3a. planos recortados y normalizados (1080x1920, 25 fps, audio 48 kHz) y unidos
    parts, offs, t0 = [], [], 0.0
    for k, (p, fin, words) in enumerate(clips):
        q = os.path.join(tmpd, f"p{k}.mp4"); dur = fin
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", p, "-t", f"{dur:.2f}", "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                        f"fade=t=in:st=0:d=0.12,fade=t=out:st={max(0, dur - 0.12):.2f}:d=0.12",
                        "-af", f"afade=t=in:d=0.05,afade=t=out:st={max(0, dur - 0.08):.2f}:d=0.08",
                        "-ar", "48000", "-ac", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", q],
                       check=True)
        parts.append(q); offs.append(t0); t0 += dur
    lst = os.path.join(tmpd, "lista.txt"); open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    joined = os.path.join(tmpd, "unido.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    habla = t0
    END = 3.6                                                    # tarjeta final
    total = habla + END
    # subtítulos con tiempos globales
    subs = []
    for (p, fin, words), off, frase in zip(clips, offs, SUBS):
        ws = [(w, s + off, e + off) for w, s, e in words if e <= fin + 0.05]
        if not ws:
            continue
        # se muestran las palabras del GUION (sin faltas), repartidas con los tiempos de Whisper
        g = frase.split(); n = max(1, len(ws))
        tt = [(g[i], ws[min(n - 1, int(i * n / len(g)))][1], ws[min(n - 1, int(i * n / len(g)))][2]) for i in range(len(g))]
        subs += _chunks(tt)
    sub_imgs = [(_sub_img(t), a, b) for t, a, b in subs]
    tag = fx.pill("UDA · UNIÓN DE ARQUITECTOS", 30, T.label, fx.NEGRO, padx=24, pady=11, radius=4)
    final = MQ._brand_final(900)
    # 3b. audio: voz de los planos + música muy suave + brillo en la tarjeta final
    a_path = os.path.join(tmpd, "voz.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-vn", "-ac", "1", "-ar", str(fx.SR), a_path], check=True)
    vo, _ = sf.read(a_path, dtype="float32")
    n = int(fx.SR * total); voz = np.zeros(n, np.float32); voz[:min(n, len(vo))] = vo[:n]
    mus = fx.premium_beat(total, 80, seed="presentadora")
    mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]
    env = np.ones(n, np.float32) * 0.13; env[int(habla * fx.SR):] = 0.42       # bajo la voz casi no se oye
    sfx = np.zeros(n, np.float32); sh = fx.shimmer(); i = int((habla + 0.1) * fx.SR); sfx[i:i + len(sh)] += sh[: n - i] * 0.6
    w2 = fx.whoosh2(); i = int(max(0, habla - 0.35) * fx.SR); sfx[i:i + len(w2)] += w2[: n - i]
    mix = fx.dehiss(np.tanh((voz * 1.1 + mus * env + sfx) * 1.02) * 0.95)
    wav = os.path.join(tmpd, "mezcla.wav"); sf.write(wav, mix, fx.SR)
    # 3c. vídeo: fotogramas de los planos + capas
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", joined, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + fx.enc_args(out, scale=False),
                           stdin=subprocess.PIPE)
    last = None; f = 0
    while True:
        raw = dec.stdout.read(W * H * 3)
        if len(raw) < W * H * 3:
            break
        t = f / FPS; fr = Image.frombytes("RGB", (W, H), raw).convert("RGBA")
        fx.paste_center(fr, tag, W / 2, 300)
        for im, a, b in sub_imgs:
            if a - 0.05 <= t <= b + 0.15:
                p = min(1.0, (t - a + 0.05) / 0.12)
                fx.paste_center(fr, im, W / 2, 1300 + (1 - p) * 14, alpha=max(0.0, p))
                break
        last = fr; enc.stdin.write(fr.convert("RGB").tobytes()); f += 1
    dec.wait()
    nend = int(END * FPS)
    from themes import ImageBG
    bg = ImageBG(last.convert("RGB"), dark=0.72, blur=14).frame(0).convert("RGBA") if last is not None else None
    for k in range(nend):
        p = min(1.0, k / (FPS * 0.4))
        fr = (bg or Image.new("RGBA", (W, H), (12, 12, 12, 255))).copy()
        fx.paste_center(fr, final, W / 2, 960 + (1 - p) * 40, alpha=p)
        enc.stdin.write(fr.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()
    return total


def portada(img, out):
    """Portada (cuadrícula del perfil): la presentadora + titular grande + marco dorado."""
    import infoviz as IV, themes
    T = themes.get("negro")
    base = img.convert("RGB").resize((W, H)) if img.size != (W, H) else img.convert("RGB")
    base = base.convert("RGBA")
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    for yy in range(0, H, 4):
        d.rectangle([0, yy, W, yy + 4], fill=(0, 0, 0, int(200 * max(0, (yy / H) - 0.45) / 0.55)))
    base.alpha_composite(sh)
    IV.frame(base, T)
    pill = fx.pill("TU EQUIPO TÉCNICO", 38, T.label, fx.NEGRO, padx=30, pady=14, radius=4)
    hl = fx.headline("¿Tu estudio va a tope?", 108, 920, 2, color=fx.CREMA, hot=T.label, hot_words=("tope?",), shadow=True)
    lg = fx.logo(52, fx.CREMA, T.label)
    y = 1600 - lg.height - 30 - hl.height - 20 - pill.height        # todo encima del logo, dentro del recorte 3:4
    fx.paste_center(base, pill, W / 2, y + pill.height / 2); y += pill.height + 20
    fx.paste_center(base, hl, W / 2, y + hl.height / 2); y += hl.height + 30
    fx.paste_center(base, lg, W / 2, y + lg.height / 2)
    base.convert("RGB").save(out, "JPEG", quality=92)


CAPTION = (
    "¿Tu estudio va a tope y no quieres ampliar plantilla? 👩‍💼\n\n"
    "En UDA somos tu equipo técnico externo: tú diseñas y firmas; nosotros hacemos planos, estructuras, instalaciones, "
    "memorias y mediciones.\n\n"
    "✔️ Presupuesto cerrado en 24 h\n✔️ Repercútelo a tu cliente\n✔️ Acepta más encargos y factura más\n\n"
    f"👉 {M.CTA}: {M.WEB}\n\n"
    "Presentadora creada con IA.\n\n"
    "#arquitectura #despachodearquitectura #arquitectos #proyectodeejecucion #estudiodearquitectura #BIM")


def generar():
    os.makedirs(PREV, exist_ok=True)
    try:
        model = _veo_model(); print("modelo de vídeo:", model, flush=True)
    except RuntimeError as e:
        print(f"{e}: hago el reel con el retrato animado y voz de Google", flush=True)
        return generar_retratos()
    img = retrato()
    clips, info, presupuesto = [], [], 7                       # como mucho 7 planos de Veo en total (coste)
    for k, frase in enumerate(GUION):
        best = None
        for intento in range(3):
            if presupuesto <= 0:
                raise RuntimeError("se han agotado los intentos de Veo; no se publica nada")
            presupuesto -= 1
            p = os.path.join(PREV, "tmp", f"veo{k}_{intento}.mp4"); os.makedirs(os.path.dirname(p), exist_ok=True)
            try:
                veo(model, frase, img, p, seed=1000 + k)
            except Exception as e:
                print(f"plano {k + 1}: {str(e)[:300]}", flush=True); continue
            words, ai = transcribe(p)
            dicho = " ".join(w for w, _, _ in words)
            sim = parecido(dicho, frase)
            print(f"plano {k + 1} intento {intento + 1}: {sim:.2f} · «{dicho}»", flush=True)
            if best is None or sim > best[0]:
                best = (sim, p, words, dicho)
            if sim >= 0.85:
                break
        if best is None or best[0] < 0.7:
            raise RuntimeError(f"el plano {k + 1} no dice bien la frase; no se publica")
        sim, p, words, dicho = best
        fin = min(8.0, (words[-1][2] if words else 7.5) + 0.45)
        clips.append((p, fin, words)); info.append({"frase": frase, "dicho": dicho, "parecido": round(sim, 2), "fin": fin})
    out = os.path.join(PREV, "presentadora.mp4")
    total = montar(clips, out)
    portada(img, os.path.join(PREV, "presentadora_portada.jpg"))
    json.dump({"modelo": model, "duracion": round(total, 1), "planos": info, "caption": CAPTION},
              open(os.path.join(PREV, "presentadora.json"), "w"), ensure_ascii=False, indent=1)
    print("listo:", out, f"({total:.1f} s)", flush=True)


# ------------------------------------------------------------------ modo sin Veo: retrato animado + voz femenina de España
VOZ_PRESENTADORA = os.environ.get("PRESENTADORA_VOZ", "es-ES-Chirp3-HD-Kore")   # femenina, firme y profesional
PLANOS = [  # (archivo, escena) — la misma mujer en cada plano, con el retrato como referencia
    ("presentadora.png", None),
    ("presentadora_planos.png",
     "sentada en una gran mesa de trabajo de roble revisando planos de arquitectura impresos y un portátil abierto, "
     "levanta la vista hacia cámara con una sonrisa serena"),
    ("presentadora_maqueta.png",
     "de pie junto a una mesa con una maqueta blanca de un edificio contemporáneo, la señala con una mano mientras "
     "mira a cámara con seguridad"),
    ("presentadora_brazos.png",
     "de pie con los brazos cruzados, sonrisa amplia y segura, mirando a cámara, ventanal con luz dorada de atardecer "
     "detrás"),
]


def retratos():
    base = retrato(); out = [base]
    for nombre, escena in PLANOS[1:]:
        p = os.path.join(HERE, "assets", nombre)
        if not os.path.exists(p):
            im = gemini.image(
                "Fotografía editorial hiperrealista, vertical 9:16. La MISMA mujer de la imagen de referencia (misma cara, "
                "mismo peinado, misma americana negra y blusa crema, mismos pendientes de oro), " + escena + ". Mismo "
                "estudio de arquitectura minimalista de hormigón, roble y grandes ventanales; luz cálida de cine; paleta "
                "negra, crema y oro. Plano medio, cara nítida y natural. Sin texto, sin logotipos.", aspect="9:16", refs=[base])
            im.save(p); print("plano nuevo:", p, flush=True)
        out.append(Image.open(p).convert("RGB"))
    return out


def voz_frases():
    """Cada frase con la voz femenina de Google (Chirp 3 HD, castellano de España), comprobada con Whisper."""
    import soundfile as sf
    os.environ["GOOGLE_TTS_VOICE"] = VOZ_PRESENTADORA
    import importlib, voice
    importlib.reload(voice)
    key = os.environ.get("GOOGLE_TTS_KEY") or gemini.key()
    out = []
    for k, frase in enumerate(GUION):
        best = None
        for intento in range(3):
            a = voice._google_line(frase, key, speed=1.04)
            p = os.path.join(PREV, "tmp", f"voz{k}_{intento}.wav"); os.makedirs(os.path.dirname(p), exist_ok=True)
            sf.write(p, a, voice.SR)
            words, _ = transcribe(p)
            sim = parecido(" ".join(w for w, _, _ in words), frase)
            print(f"voz {k + 1}: {sim:.2f}", flush=True)
            if best is None or sim > best[0]:
                best = (sim, a, words)
            if sim >= 0.85:
                break
        if best[0] < 0.7:
            raise RuntimeError(f"la voz de la frase {k + 1} no sale bien; no se publica")
        out.append((best[1], best[2]))
    return out, voice.SR


def _kb(img, t, dur, k):
    """Movimiento de cámara lento (zoom y desplazamiento suaves, distinto en cada plano)."""
    p = t / max(dur, 0.1); p = p * p * (3 - 2 * p)
    z = 1.04 + 0.08 * (p if k % 2 == 0 else 1 - p)
    dx = (0.5 + (0.06 if k % 3 == 1 else -0.05 if k % 3 == 2 else 0) * (p - 0.5))
    dy = 0.42 + 0.04 * (p - 0.5) * (1 if k % 2 else -1)
    iw, ih = img.size; cw, ch = iw / z, ih / z
    x0 = (iw - cw) * dx; y0 = (ih - ch) * dy
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BICUBIC)


def montar_retratos(imgs, voces, sr, out):
    import soundfile as sf
    import themes
    import make_quiz as MQ
    T = themes.get("negro"); MQ.T = T
    big = [im.resize((int(W * 1.12), int(H * 1.12)), Image.LANCZOS) if im.size != (int(W * 1.12), int(H * 1.12)) else im
           for im in imgs]
    GAP = 0.35; XF = 0.4; END = 3.6
    durs = [len(a) / sr + GAP for a, _ in voces]
    starts = [sum(durs[:k]) + 0.4 for k in range(len(durs))]      # 0,4 s de entrada antes de la primera frase
    habla = starts[-1] + durs[-1]; total = habla + END
    n = int(fx.SR * total); voz = np.zeros(n, np.float32)
    for (a, _), s0 in zip(voces, starts):
        a = a if sr == fx.SR else np.interp(np.linspace(0, len(a), int(len(a) * fx.SR / sr), endpoint=False),
                                            np.arange(len(a)), a).astype(np.float32)
        i = int(s0 * fx.SR); voz[i:i + len(a)] += a[: n - i]
    mus = fx.premium_beat(total, 80, seed="presentadora"); mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]
    env = np.ones(n, np.float32) * 0.2; env[int(habla * fx.SR):] = 0.45
    sfx = np.zeros(n, np.float32)
    for s0 in starts[1:] + [habla]:
        w2 = fx.whoosh2(); i = int(max(0, s0 - 0.45) * fx.SR); sfx[i:i + len(w2)] += w2[: n - i] * 0.8
    sh = fx.shimmer(); i = int((habla + 0.1) * fx.SR); sfx[i:i + len(sh)] += sh[: n - i] * 0.6
    mix = fx.dehiss(np.tanh((voz * 1.15 + mus * env + sfx) * 1.02) * 0.95)
    tmpd = os.path.join(PREV, "tmp"); wav = os.path.join(tmpd, "mezcla.wav"); sf.write(wav, mix, fx.SR)
    subs = []
    for (a, words), s0, frase in zip(voces, starts, SUBS):
        g = frase.split(); nw = max(1, len(words))
        tt = [(g[i], s0 + words[min(nw - 1, int(i * nw / len(g)))][1], s0 + words[min(nw - 1, int(i * nw / len(g)))][2])
              for i in range(len(g))] if words else []
        subs += _chunks(tt)
    sub_imgs = [(_sub_img(t), a_, b_) for t, a_, b_ in subs]
    tag = fx.pill("UDA · UNIÓN DE ARQUITECTOS", 30, T.label, fx.NEGRO, padx=24, pady=11, radius=4)
    final = MQ._brand_final(900)
    from themes import ImageBG
    bg_end = ImageBG(imgs[-1], dark=0.72, blur=14).frame(0).convert("RGBA")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", wav, "-shortest"] + fx.enc_args(out, scale=False),
                           stdin=subprocess.PIPE)
    seg_a = [0.0] + starts[1:]; seg_b = starts[1:] + [habla]
    for f in range(int(total * FPS)):
        t = f / FPS
        if t >= habla:
            p = min(1.0, (t - habla) / 0.4)
            fr = bg_end.copy()
            last = _kb(big[-1], seg_b[-1] - seg_a[-1], seg_b[-1] - seg_a[-1], len(big) - 1).convert("RGBA")
            fr = Image.blend(last, fr, p)
            fx.paste_center(fr, final, W / 2, 960 + (1 - p) * 40, alpha=p)
        else:
            k = max(i for i in range(len(seg_a)) if seg_a[i] <= t)
            fr = _kb(big[k % len(big)], t - seg_a[k], seg_b[k] - seg_a[k], k).convert("RGBA")
            if k + 1 < len(seg_a) and t > seg_b[k] - XF:                      # fundido al plano siguiente
                nxt = _kb(big[(k + 1) % len(big)], 0, seg_b[k + 1] - seg_a[k + 1], k + 1).convert("RGBA")
                fr = Image.blend(fr, nxt, (t - (seg_b[k] - XF)) / XF)
            if t < 0.4:
                fr = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), fr, t / 0.4)
            fx.paste_center(fr, tag, W / 2, 300)
            for im, a_, b_ in sub_imgs:
                if a_ - 0.05 <= t <= b_ + 0.15:
                    q = min(1.0, (t - a_ + 0.05) / 0.12)
                    fx.paste_center(fr, im, W / 2, 1300 + (1 - q) * 14, alpha=max(0.0, q))
                    break
        enc.stdin.write(fr.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()
    return total


def generar_retratos():
    os.makedirs(os.path.join(PREV, "tmp"), exist_ok=True)
    imgs = retratos()
    voces, sr = voz_frases()
    out = os.path.join(PREV, "presentadora.mp4")
    total = montar_retratos(imgs, voces, sr, out)
    portada(imgs[0], os.path.join(PREV, "presentadora_portada.jpg"))
    json.dump({"modo": "retrato animado (sin Veo)", "voz": VOZ_PRESENTADORA, "duracion": round(total, 1),
               "frases": GUION, "caption": CAPTION}, open(os.path.join(PREV, "presentadora.json"), "w"),
              ensure_ascii=False, indent=1)
    print("listo:", out, f"({total:.1f} s)", flush=True)


def publicar():
    import publish_ig as IG, publish_zernio as Z
    v = os.path.join(PREV, "presentadora.mp4"); c = os.path.join(PREV, "presentadora_portada.jpg")
    cover_url = None
    try:
        cover_url = Z.upload(c)
    except Exception as e:
        print("portada no subida (se usa un fotograma):", str(e)[:150], flush=True)
    m = IG.publish_reel(v, CAPTION, cover_url=cover_url, thumb_ms=None if cover_url else 2000)
    print("publicado en Instagram:", m, flush=True)
    with open(os.path.join(HERE, "log.jsonl"), "a") as f:
        import datetime
        f.write(json.dumps({"date": str(datetime.date.today()), "slot": "manual", "formato": "presentadora",
                            "tematica": "presentadora", "hook": "¿Tu estudio va a tope?",
                            "publicado": {"instagram_reel": f"ig:{m.get('id')}"},
                            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
                           ensure_ascii=False) + "\n")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "modelos"
    {"modelos": modelos, "generar": generar, "publicar": publicar}[modo]()
