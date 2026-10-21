"""Narration voice for all reels.

Engine order (automatic, never blocks a reel):
  1. Gemini TTS (very natural, takes acting directions) when GEMINI_API_KEY is set.
     Story narration is recorded in ONE take so the intonation flows like a real narrator,
     then split into scenes at the natural pauses.
  2. Chatterbox (open source) if VOICE_ENGINE=chatterbox and its venv exists.
  3. Kokoro (local) as last resort.
"""
import base64, json, os, re, subprocess, tempfile, time
import numpy as np
import requests
import soundfile as sf

SR = 24000
HERE = os.path.dirname(os.path.abspath(__file__))
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "em_alex")      # voz masculina española de Kokoro (respaldo local)
CB_PY = os.environ.get("CHATTERBOX_PY", os.path.join(HERE, ".venv-cb", "bin", "python"))
REF_LINE = ("¿Te sabes esta pregunta de normativa? Vamos a comprobarlo. "
            "Lee bien las cuatro opciones antes de contestar.")

GEMINI_VOICE = os.environ.get("GEMINI_VOICE", "Orus")             # voz masculina firme (elige otra con "Muestras de voz")
API = "https://generativelanguage.googleapis.com/v1beta"
TTS_PREFERRED = ["gemini-3.8-flash-tts", "gemini-3.8-flash-tts-preview", "gemini-3.1-flash-tts-preview",
                 "gemini-3.1-flash-tts", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
# Indicaciones SOLO en inglés y cortas: el modelo no debe confundirlas con el texto en español (si alguna vez las lee,
# _leak() lo detecta con el reconocimiento de voz y la toma se repite).
NARRATOR = ("Voice profile: a man from Madrid, Spain, in his forties, with a clear CASTILIAN (peninsular, European) "
            "Spanish accent: distinción, so 'z' and 'c' before 'e'/'i' are pronounced like the English 'th' (θ) — "
            "'precio', 'hacer', 'proyecto de ejecución' — never seseo; crisp final 's'; the intonation of a Spaniard "
            "from Madrid, NOT Latin American, NOT Mexican, NOT neutral Latin. An experienced architect talking to "
            "colleagues: confident, direct and energetic, with punch and natural rhythm, emphasis on the key words. "
            "Never flat, never monotone, not an announcer. Acronyms and single letters pronounced the Spanish (Spain) way. "
            "Say each sentence exactly once: never repeat or restart a line.")
ENGINE_USED = None
LOCK = None          # engine chosen for the current reel: every line of one reel uses the same voice


class VoiceError(RuntimeError):
    """The engine locked for this reel failed; the caller must redo the whole reel with another engine."""


def reset(force=None):
    """Call at the start of every reel. force: None (best available), 'local' (no Gemini) or 'kokoro'."""
    global LOCK
    LOCK = force
    _CLIPS.clear()


# ------------------------------------------------------------------ speech recognition (captions + checks)
_asr_model, _asr_cache = None, {}


import threading
_asr_lock = threading.Lock()


def _asr(a, careful=False):
    with _asr_lock:
        return _asr_inner(a, careful)


def _asr_inner(a, careful=False):
    """[(word, start_s, end_s)] heard in a 24 kHz clip, or None if speech recognition is unavailable.
    careful=True: segunda opinión más lenta (beam 5 + VAD) para confirmar un fallo antes de descartar una toma, porque
    el reconocedor también se equivoca a veces (p. ej. repite la última frase al final de un audio)."""
    global _asr_model
    k = (len(a), round(float(np.sum(np.abs(a[::97]))), 3), careful)
    if k in _asr_cache:
        return _asr_cache[k]
    if _asr_model is False:
        return None
    try:
        if _asr_model is None:
            from faster_whisper import WhisperModel
            _asr_model = WhisperModel(os.environ.get("ASR_MODEL", "small"), device="cpu", compute_type="int8")
        a16 = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / SR)), np.arange(len(a)), a).astype(np.float32)
        segs, _ = _asr_model.transcribe(a16, language="es", beam_size=5 if careful else 1, word_timestamps=True,
                                        vad_filter=careful, condition_on_previous_text=False, temperature=0.0)
        out = [(w.word.strip(), float(w.start), float(w.end)) for sg in segs for w in (sg.words or []) if w.word.strip()]
    except Exception as e:
        if careful:                                  # la segunda opinión falló: no se desactiva el reconocedor
            print("voice: segunda transcripción no disponible:", str(e)[:150], flush=True)
            return None
        print("voice: speech recognition unavailable:", str(e)[:150], flush=True)
        _asr_model = False
        return None
    _asr_cache[k] = out
    return out


def _fold(t):
    """minúsculas sin tildes (á->a, ñ->n): el reconocedor a veces pone o quita tildes."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _norm(w):
    return re.sub(r"[^a-z0-9]", "", _fold(w))


def _num_words(n):
    try:
        from num2words import num2words
        return num2words(n, lang="es")
    except Exception:
        return str(n)


def _spoken(text):
    """Forma hablada solo con letras, para comparar lo que dice la voz con el texto: '55/2003' == 'cincuenta y cinco
    de dos mil tres', 'art. 4' == 'artículo cuatro'. Así la notación, los números o la puntuación no cuentan como error."""
    t = spoken_text(text).lower().replace("%", " por ciento ").replace("&", " y ")
    t = re.sub(r"\d+", lambda m: " " + _num_words(int(m.group())) + " ", t)
    return re.sub(r"[^a-z]", "", _fold(t))


_SPELL = {"S": "ese", "I": "i", "U": "u", "A": "a", "H": "hache", "E": "e", "R": "erre", "C": "ce", "M": "eme", "F": "efe"}


def _db(m):
    """'DB SI' -> 'de be ese i', 'DB-SUA' -> 'de be sua', 'DB HE 1' -> 'de be hache e uno' (como lo dice un arquitecto)."""
    code = m.group(1).upper()
    said = "sua" if code == "SUA" else " ".join(_SPELL.get(c, c.lower()) for c in code)
    return ("de be " if m.group(0).upper().startswith("DB") else "") + said + (f" {m.group(2)}" if m.group(2) else "")


ABBR = [(r"\bart(?:s)?\.\s*", "artículo "), (r"\bnº\s*|\bn\.º\s*", "número "), (r"\bp\. ?ej\.", "por ejemplo"),
        (r"\bLO\b", "Ley Orgánica"), (r"\bRDL(?:eg)?\b", "Real Decreto Legislativo"), (r"\bRD\b", "Real Decreto"),
        (r"\bTRLSRU\b", "Ley de Suelo y Rehabilitación Urbana"), (r"\bLPH\b", "Ley de Propiedad Horizontal"),
        (r"\bLOE\b", "loe"), (r"\bCTE\b", "ce te e"), (r"\bUDA\b", "Uda"),
        (r"\bP\. ?B[áa]sico\b", "Proyecto Básico"), (r"\bP\. ?Ejecuci[óo]n\b", "Proyecto de Ejecución"),
        (r"\bBEP\b", "be e pe"), (r"\bBIM\b", "bim"), (r"\bCAD\b", "cad"), (r"\bIFC\b", "i efe ce"), (r"\bDWG\b", "de uve doble ge"),
        (r"\bRVT\b", "erre uve te"), (r"\bPDF\b", "pe de efe"), (r"\bCYPE\b", "cipe"), (r"\bLOD\b", "lod"),
        (r"\bRITE\b", "rite"), (r"\bREBT\b", "erre e be te"), (r"\bICT\b", "i ce te"), (r"\bPEM\b", "pe e eme"),
        (r"\bRCD\b", "erre ce de"), (r"\bSATE\b", "sate"), (r"\bPCI\b", "pe ce i"),
        (r"€\s*/\s*m²", " euros por metro cuadrado"), (r"€/año", " euros al año"), (r"\s?€", " euros"),
        (r"\bm²|\bm2\b", " metros cuadrados"), (r"\bm³|\bm3\b", " metros cúbicos"),
        (r"\bkg\b", "kilos"), (r"\bcm\b", "centímetros"), (r"\bmm\b", "milímetros"), (r"\bkW\b", "kilovatios"),
        (r"\bºC\b|\b° ?C\b", " grados"), (r"\bdB\b", "decibelios"), (r"\bh\b", "horas"), (r"\bEE\. ?UU\.", "Estados Unidos")]


LETTER_NAMES = {"A": "a", "B": "be", "C": "ce", "D": "de"}


def spoken_text(text):
    """Texto preparado para que la voz lo lea bien en español de España (lo que se ve en pantalla no cambia).
    Las letras de las opciones se escriben como se dicen en español ("be", "ce"...): escritas como "B." la voz las
    leía a veces en inglés ("bi", "si"), sobre todo delante de un término en inglés o latín."""
    t = str(text)
    t = re.sub(r"(?m)^\s*([ABCD])[.)]\s+", lambda m: LETTER_NAMES[m.group(1)] + ", ", t)          # "B. Fowler" -> "be, Fowler"
    t = re.sub(r"\b(la|las|letra|opci[oó]n|respuesta|y)\s+([ABCD])\b(?!\.\w)", lambda m: m.group(1) + " " + LETTER_NAMES[m.group(2)], t)
    t = re.sub(r"(?i)\buniondearquitectos\.com\b", "unión de arquitectos punto com", t)
    t = re.sub(r"\bDB[\s-]*(SUA|SI|SE|HE|HS|HR)(?:[\s-]*(\d))?\b", _db, t)       # DB SI -> de be ese i
    t = re.sub(r"\b(SUA|SI|HE|HS|HR)\s(\d)\b", _db, t)                      # SI 3 -> ese i 3
    t = re.sub(r"(\d)\.(\d{3})\b", r"\1\2", t)                     # 1.800 -> 1800
    t = re.sub(r"(\d+),(\d+)", r"\1 coma \2", t)                      # 0,50 -> 0 coma 50
    t = re.sub(r"(\d+)/(\d{4})", r"\1 de \2", t)                    # Ley 38/1999 -> Ley 38 de 1999
    t = re.sub(r"(\d+)\s*[-–]\s*(\d+)", r"\1 a \2", t)                 # 24–72 horas -> 24 a 72 horas
    for a, b in ABBR:
        t = re.sub(a, b, t)
    return re.sub(r"\s+", " ", t).strip()


def _similarity(a, text):
    """0..1 how well the audio says the text (None when we cannot check). Compared letter by letter on the
    spoken form, so notation, numbers and punctuation written differently by the recogniser do not count."""
    heard = _asr(a)
    if heard is None:
        return None
    import difflib
    x, y = _spoken(text), _spoken(" ".join(w for w, _, _ in heard))
    if not x or not y:
        return 0.0
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()


LEAK_WORDS = {"tono", "amable", "companero", "fueras", "fuera", "narradora", "narrador", "locutora", "cercana", "didactica",
              "man", "architect", "colleagues", "punchy", "forties", "energetic", "persuasive", "assured", "emphasis",
              "challenge", "hint", "smile", "listing", "storytelling", "suspense", "intriguing", "emphatic", "lively",
              "warning", "inviting", "quick", "short", "performance",
              "calida", "acento", "peninsular", "entonacion", "parrafo", "sonrisa", "intrigante", "rotunda", "complice",
              "motivadora", "energica", "transcript", "transcripcion", "notes", "notas", "director", "directora", "paragraph",
              "warm", "tone", "voice", "read", "style", "delivery", "upbeat", "playful", "friendly", "confident", "smiling",
              "natural", "clear", "brisk", "explaining", "profile", "spain", "spanish", "accent", "woman", "say", "letter",
              "letters", "option", "options", "pause"}
_LETTER_SOUNDS = {"bi": "be", "si": "ce", "di": "de", "ei": "a", "bee": "be", "see": "ce", "dee": "de", "uve": "be"}


def _toks(t):
    """Palabras habladas normalizadas (números en letra, letras de opción en español), para comparar texto y audio."""
    t = spoken_text(t).replace("%", " por ciento ")
    t = re.sub(r"\d+", lambda m: " " + _num_words(int(m.group())) + " ", t)
    single = {"b": "be", "c": "ce", "d": "de"}
    return [single.get(w, w) for w in (_norm(x) for x in re.split(r"[\s/\-]+", t)) if w]


def _issues(heard, text):
    """Lista de fallos de una toma según lo que se oye: lee indicaciones, dice la letra en inglés, repite un trozo
    (p. ej. la opción B dos veces) o mete palabras que no están en el texto."""
    import difflib
    from collections import Counter
    S = _toks(text); Hd = _toks(" ".join(w for w, _, _ in heard))
    out = []
    if not S:
        return out
    if not Hd:
        return ["no se oye nada"]
    extra = [w for w in Hd if w not in set(S)]
    leak = [w for w in extra if w in LEAK_WORDS]
    if leak:
        out.append(f"lee palabras que no están en el guion ({' '.join(leak[:4])})")
    eng = [w for w in Hd if w in _LETTER_SOUNDS and w not in set(S)]
    if eng:
        out.append(f"dice la letra en inglés ({eng[0]})")
    for n in (2, 3, 4):
        if n == 2 and len(S) > 6:                       # bigramas solo en textos cortos ("B. Agua")
            continue
        cs, ch = Counter(zip(*[S[i:] for i in range(n)])), Counter(zip(*[Hd[i:] for i in range(n)]))
        rep = [g for g, c in ch.items() if c > cs.get(g, 0) >= 1 and sum(len(w) for w in g) >= 5]
        if rep:
            out.append(f"repite '{' '.join(rep[0])}'"); break
    # letras de más (inserciones) comparando la forma hablada letra a letra: detecta un trozo de otra frase o una repetición
    x, y = "".join(S), "".join(Hd)
    ins = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
        if op == "insert":
            ins += j2 - j1
        elif op == "replace":
            ins += max(0, (j2 - j1) - (i2 - i1))
    if ins > max(6, 0.1 * len(x)):
        out.append(f"dice {ins} letras de más")
    if len(Hd) > len(S) * 1.25 + 1:
        out.append(f"{len(Hd)} palabras para un texto de {len(S)}")
    return out


def problem(a, text):
    """Motivo por el que una toma no vale, o None si está bien. Un fallo se confirma con una segunda transcripción más
    cuidadosa (así un error del reconocedor no tira una toma buena)."""
    heard = _asr(a)
    if heard is None:
        return None
    iss = _issues(heard, text)
    if not iss:
        return None
    second = _asr(a, careful=True)
    iss2 = _issues(second, text) if second is not None else iss
    if not iss2:
        print(f"voice: falso aviso del reconocedor ({iss[0]}) en {text[:40]!r}; la toma es buena", flush=True)
        return None
    heard_txt = " ".join(w for w, _, _ in second or heard)
    print(f"voice: toma descartada ({'; '.join(iss2)}) · texto {text[:60]!r} · se oye {heard_txt[:90]!r}", flush=True)
    return iss2[0]


def _leak(a, text):
    """Compatibilidad: True si la toma tiene algún fallo."""
    return bool(problem(a, text))


def align(a, text):
    """Word timings for captions: [(t_seconds, word)] matching what is actually heard in the clip."""
    ws = text.split()
    heard = _asr(a)
    if heard:
        import difflib
        sm = difflib.SequenceMatcher(None, [_norm(w) for w in ws], [_norm(w) for w, _, _ in heard])
        if _similarity(a, text) < 0.6:                         # voice said something else: show what it said
            return [(st, w) for w, st, _ in heard]
        t = [None] * len(ws)
        for i, j, n in sm.get_matching_blocks():
            for d in range(n):
                t[i + d] = heard[j + d][1]
        dur = len(a) / SR
        known = [(i, v) for i, v in enumerate(t) if v is not None]
        xs = [-1] + [i for i, _ in known] + [len(ws)]
        ys = [0.0] + [v for _, v in known] + [dur * 0.95]
        t = list(np.interp(range(len(ws)), xs, ys))
        for i in range(1, len(t)):                             # keep order
            t[i] = max(t[i], t[i - 1] + 0.05)
        return list(zip(t, ws))
    L = sum(len(w) + 1 for w in ws); acc = 0; out = []        # fallback: proportional to characters
    for w in ws:
        out.append(((len(a) / SR) * acc / L * 0.95, w)); acc += len(w) + 1
    return out


# ------------------------------------------------------------------ helpers
def _trim(a):
    if len(a) == 0:
        return a
    thr = max(0.01, 0.04 * float(np.max(np.abs(a))))
    nz = np.nonzero(np.abs(a) > thr)[0]
    return a[max(0, nz[0] - 240): nz[-1] + 1600] if len(nz) else a


def _tighten(a, max_gap=0.45):
    """Shorten long internal silences (dramatic pauses, breaths) so short lines stay short."""
    hop = int(SR * 0.01)
    if len(a) < hop * 10:
        return a
    env = np.sqrt(np.convolve(a ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop]
    quiet = env < max(0.01, 0.05 * np.percentile(env, 95))
    keep = np.ones(len(a), bool); i = 0; mg = int(max_gap * 100)
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]: j += 1
            if j - i > mg:
                keep[(i + mg // 2) * hop:(j - mg // 2) * hop] = False
            i = j
        else:
            i += 1
    return a[keep]


def degate(a):
    """Remove breaths, hiss and noise between words and at the edges of every clip.
    Frames (20 ms) are 'voiced' when they are loud and tonal. Any run of non-voiced frames longer than 120 ms
    (breath, hiss, room noise) is faded down to near silence; short ones (s, f, sh, t inside words) are kept.
    Leading/trailing non-voiced audio is cut off completely."""
    a = a.astype(np.float32)
    fr = int(SR * 0.02)
    n = len(a) // fr
    if n < 5:
        return a
    X = np.abs(np.fft.rfft(a[: n * fr].reshape(n, fr) * np.hanning(fr), axis=1)) + 1e-9
    rms = np.sqrt(np.mean(a[: n * fr].reshape(n, fr) ** 2, axis=1))
    flat = np.exp(np.mean(np.log(X[:, 3:]), axis=1)) / np.mean(X[:, 3:], axis=1)
    p90 = np.percentile(rms, 90) + 1e-9
    quiet = rms < 0.12 * p90
    hiss = flat > 0.75                                   # white-noise-like (speech sounds stay below ~0.72)
    breathy = (flat > 0.55) & (rms < 0.35 * p90)         # breaths: noisy and softer than speech
    g = np.ones(n, np.float32)

    def gate(mask, min_run):
        i = 0
        while i < n:
            if mask[i]:
                j = i
                while j < n and mask[j]: j += 1
                if j - i >= min_run or i == 0 or j == n:
                    g[i:j] = 0.02
                i = j
            else:
                i += 1
    gate(quiet | hiss, 4)                                # silence/hiss runs >= 80 ms
    gate(breathy, 8)                                     # breaths >= 160 ms
    keep = g > 0.5
    if not keep.any():
        return a
    first, last = int(np.argmax(keep)), n - 1 - int(np.argmax(keep[::-1]))
    gs = np.repeat(g, fr)
    gs = np.concatenate([gs, np.full(len(a) - len(gs), gs[-1])])
    ramp = int(SR * 0.012)                          # smooth 12 ms gain changes (no clicks)
    gs = np.convolve(gs, np.ones(ramp) / ramp, "same")
    out = (a * gs)[max(0, first * fr - int(SR * 0.03)): min(len(a), (last + 1) * fr + int(SR * 0.08))]
    fade = min(int(SR * 0.015), len(out) // 4)
    if fade > 1:
        out[:fade] *= np.linspace(0, 1, fade); out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)


def polish(a, light=False):
    """Cleanup: breath/hiss gate, then a high-pass + level (local TTS gets a bit more 'mic' colour)."""
    a = degate(a.astype(np.float32))
    if len(a) < 10:
        return a
    k = int(SR / 80)
    a = a - np.convolve(a, np.ones(k) / k, "same")                                    # high-pass ~80 Hz
    if not light:
        hi = a - np.convolve(a, np.ones(6) / 6, "same")
        a = a + 0.25 * hi
        a = a / (np.max(np.abs(a)) + 1e-6)
        a = np.sign(a) * (1 - np.exp(-1.6 * np.abs(a))) / (1 - np.exp(-1.6))
    tail = np.zeros(int(SR * 0.1), np.float32)
    out = np.concatenate([a, tail])
    return (out / (np.max(np.abs(out)) + 1e-6) * 0.9).astype(np.float32)


def _resample(a, sr):
    if sr == SR:
        return a.astype(np.float32)
    n = int(len(a) * SR / sr)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def _words(t):
    return max(1, len(re.findall(r"[A-Za-zÀ-ÿ0-9']+", t)))


# ------------------------------------------------------------------ Gemini TTS
_models = None


def _tts_models(key):
    global _models
    if _models is not None:
        return _models
    found = []
    try:
        r = requests.get(f"{API}/models", params={"key": key, "pageSize": 200}, timeout=30)
        for m in r.json().get("models", []):
            n = m["name"].split("/")[-1]
            if "tts" in n and "generateContent" in m.get("supportedGenerationMethods", []):
                found.append(n)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Gemini unreachable: {e}")
    except Exception as e:
        print("voice: could not list models:", e, flush=True)
    env = os.environ.get("GEMINI_TTS_MODEL")
    order = ([env] if env else []) + [m for m in TTS_PREFERRED if not found or m in found]

    def rank(n):  # newest flash (not lite) first
        v = re.findall(r"(\d+(?:\.\d+)?)", n)
        return (-float(v[0]) if v else 0, "lite" in n, "pro" in n, "preview" in n)
    order += sorted([m for m in found if m not in order], key=rank)
    _models = list(dict.fromkeys(order))
    return _models


_LANG = ["es-ES"]                    # se quita solo si un modelo no acepta languageCode


def _gemini_call(prompt, key):
    last = None
    for model in _tts_models(key):
        for attempt in range(4):
            try:
                r = requests.post(f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": key},
                                  timeout=180, json={
                                      "contents": [{"parts": [{"text": prompt}]}],
                                      "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                          **({"languageCode": _LANG[0]} if _LANG[0] else {}),
                                          "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE}}}}})
                if r.status_code == 400 and "language" in r.text.lower() and _LANG[0]:
                    print("voice: el modelo no acepta languageCode; sigo solo con la indicación de acento", flush=True)
                    _LANG[0] = None; continue
                if r.status_code in (429, 500, 502, 503, 504):
                    last = RuntimeError(f"{model} {r.status_code}"); time.sleep(8 * (attempt + 1)); continue
                if r.status_code != 200:
                    last = RuntimeError(f"{model} {r.status_code}: {r.text[:200]}"); break
                for p in r.json()["candidates"][0]["content"]["parts"]:
                    d = p.get("inlineData") or p.get("inline_data")
                    if d:
                        mime = d.get("mimeType") or d.get("mime_type") or ""
                        rate = int((re.findall(r"rate=(\d+)", mime) or [24000])[0])
                        pcm = np.frombuffer(base64.b64decode(d["data"]), dtype="<i2").astype(np.float32) / 32768
                        return _resample(pcm, rate)
                last = RuntimeError(f"{model}: no audio in response"); break
            except requests.exceptions.ConnectionError as e:
                raise RuntimeError(f"Gemini unreachable: {e}")
            except Exception as e:
                last = e; time.sleep(4)
    raise last or RuntimeError("no Gemini TTS model available")


def _ratio(audio, text):
    return (len(audio) / SR) / (_words(spoken_text(text)) / 2.6 + 0.6)


def _sane(audio, text, factor=2.6):
    """Reject takes where the model read the stage directions aloud or cut the line."""
    r = _ratio(audio, text)
    return 0.3 < r < factor


def _clean_edges(a, text):
    """Cut any extra words the model spoke before/after the line (e.g. a stray "Say..." or an acting note),
    using the word timings from speech recognition."""
    heard = _asr(a)
    ws = [_spoken(w) for w in text.split()]
    ws = [w for w in ws if w]
    if not heard or not ws:
        return a
    hw = [_spoken(w) for w, _, _ in heard]
    start = end = None
    for j in range(min(4, len(hw))):                       # first spoken word of the line
        if hw[j] and (hw[j] == ws[0] or (len(ws) > 1 and hw[j] == ws[1] and j > 0)):
            start = j if hw[j] == ws[0] else j - 1; break
    for j in range(len(hw) - 1, max(-1, len(hw) - 5), -1):  # last spoken word of the line
        if hw[j] and hw[j] == ws[-1]:
            end = j; break
    t0 = heard[start][1] - 0.08 if start else 0.0
    t1 = heard[end][2] + 0.25 if end is not None and end < len(hw) - 1 else None
    if start or t1:
        print(f"voice: trimmed extra words around {text[:40]!r}", flush=True)
        _asr_cache.clear()
        b = a[int(max(0, t0) * SR): int(t1 * SR) if t1 else len(a)]
        return b if len(b) > SR * 0.3 else a
    return a


def _gemini_line(text, style, key, pace):
    """Up to 3 takes with different prompt shapes. A take is accepted when it says the right words with a
    natural length; otherwise the best acceptable one is kept. Fails only if every take is clearly wrong."""
    hint = f"{style}, {pace}" if style else pace
    prompts = [f"{NARRATOR}\nPerformance: {hint}.\nSpeak only the Spanish text after the colon, word for word.\n"
               f"Text: {text}",
               f"Say naturally in Castilian Spanish from Madrid (Spain accent, distinción, no seseo), {hint}: {text}",
               text]
    takes = []
    for pr in prompts + prompts[:2]:                 # hasta 5 tomas antes de rendirse
        try:
            a = _clean_edges(_tighten(_trim(_gemini_call(pr, key))), text)
        except Exception as e:
            if "unreachable" in str(e) or "no Gemini TTS" in str(e):
                raise
            print("voice: take error:", str(e)[:150], flush=True); continue
        sim = _similarity(a, text)
        if problem(a, text):
            continue                                   # leyó indicaciones o repitió: esta toma no vale nunca
        if (sim is None or sim >= 0.7) and _sane(a, text):
            return a
        print(f"voice: retake {text!r} ({len(a) / SR:.1f}s, match {sim if sim is None else round(sim, 2)})", flush=True)
        if 0.3 < _ratio(a, text) < 3.5 and (sim is None or sim >= 0.6):
            takes.append(((sim or 0.7), -abs(np.log(_ratio(a, text))), a))
    if takes:
        return max(takes, key=lambda x: (x[0], x[1]))[2]
    raise RuntimeError(f"bad take for: {text!r}")


def _split_takes(a, texts):
    """Split one continuous take into len(texts) pieces at the longest natural pauses."""
    n = len(texts)
    if n == 1:
        return [a]
    hop = int(SR * 0.01)
    env = np.sqrt(np.convolve(a ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop]
    thr = max(0.012, 0.06 * np.percentile(env, 95))
    silent = env < thr
    runs, i = [], 0
    while i < len(silent):
        if silent[i]:
            j = i
            while j < len(silent) and silent[j]: j += 1
            if j - i >= 12 and i > 20 and j < len(silent) - 20:     # >=120 ms, not at the edges
                runs.append((j - i, (i + j) // 2))
            i = j
        else:
            i += 1
    # expected cut points from word counts, choose the longest pause near each one
    w = np.array([_words(t) for t in texts], float)
    exp_cuts = np.cumsum(w)[:-1] / w.sum() * len(env)
    cuts, used = [], set()
    for ec in exp_cuts:
        cands = [(ln, c) for ln, c in runs if c not in used and abs(c - ec) < 0.22 * len(env)]
        if not cands:
            raise RuntimeError("no pause found to split the take")
        ln, c = max(cands, key=lambda x: x[0] - 0.02 * abs(x[1] - ec))
        cuts.append(c); used.add(c)
    if cuts != sorted(cuts):
        raise RuntimeError("pauses out of order")
    edges = [0] + [c * hop for c in cuts] + [len(a)]
    parts = [_clean_edges(_tighten(_trim(a[edges[k]:edges[k + 1]])), texts[k]) for k in range(n)]
    for p, t in zip(parts, texts):
        sim = _similarity(p, t)
        if not _sane(p, t, 3.2) or (sim is not None and sim < 0.75) or problem(p, t):
            raise RuntimeError("split pieces do not match the text")
    return parts


def _gemini_many(texts, styles, key, one_take, pace):
    for attempt in range(2 if one_take and len(texts) > 1 else 0):   # una sola toma = un solo timbre (2 intentos)
        try:
            cues = ("all paragraphs -> " + styles[0]) if styles and len(set(styles)) == 1 and styles[0] else \
                "; ".join(f"{i + 1}: {st}" for i, st in enumerate(styles) if st)
            script = "\n\n".join(texts)
            prompt = (f"{NARRATOR}\nPerformance: one continuous take, {pace}, a short breath pause between paragraphs"
                      + (f"; mood per paragraph -> {cues}" if cues else "") + ".\n"
                      f"Speak only the Spanish text below the line, word for word, nothing else.\n---\n{script}")
            take = _trim(_gemini_call(prompt, key))
            print(f"voice: one take {len(take) / SR:.1f}s for {sum(_words(t) for t in texts)} words", flush=True)
            if len(take) / SR > 2.2 * sum(_words(t) / 2.7 + 0.6 for t in texts) + 2:
                raise RuntimeError("one take far too long (model added extra speech)")
            if problem(take, " ".join(texts)):
                raise RuntimeError("one take includes repeated or extra words")
            return _split_takes(take, texts)
        except Exception as e:
            if "unreachable" in str(e) or "no Gemini TTS" in str(e):
                raise
            print(f"voice: one-take narration failed (intento {attempt + 1}):", str(e)[:200], flush=True)
    from concurrent.futures import ThreadPoolExecutor        # 3 lines recorded at the same time
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda ts: _gemini_line(ts[0], ts[1], key, pace), zip(texts, styles)))


# ------------------------------------------------------------------ ElevenLabs (opcional, la más natural)
ELEVEN = "https://api.elevenlabs.io/v1"
_EVOICE = []


def _eleven_voice(key):
    """ELEVENLABS_VOICE_ID o, si no se indica, la primera voz masculina española de tu cuenta."""
    vid = os.environ.get("ELEVENLABS_VOICE_ID")
    if vid:
        return vid
    if not _EVOICE:
        r = requests.get(f"{ELEVEN}/voices", headers={"xi-api-key": key}, timeout=60)
        r.raise_for_status()
        vs = r.json().get("voices", [])

        def score(v):
            lab = {k: str(x).lower() for k, x in (v.get("labels") or {}).items()}
            txt = " ".join(lab.values()) + " " + str(v.get("name", "")).lower()
            return (lab.get("gender") == "male", any(w in txt for w in ("spanish", "españ", "castil", "spain", "peninsular")))
        vs.sort(key=score, reverse=True)
        if not vs:
            raise RuntimeError("tu cuenta de ElevenLabs no tiene voces; añade una de la Voice Library")
        _EVOICE.append(vs[0]["voice_id"]); print("voice: elevenlabs voz", vs[0].get("name"), flush=True)
    return _EVOICE[0]


def _eleven_many(texts):
    key = os.environ["ELEVENLABS_API_KEY"]; vid = _eleven_voice(key)
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    out = []
    for i, t in enumerate(texts):
        body = {"text": t, "model_id": model,
                "voice_settings": {"stability": float(os.environ.get("ELEVENLABS_STABILITY", "0.45")), "similarity_boost": 0.8,
                                   "style": float(os.environ.get("ELEVENLABS_STYLE", "0.25")), "use_speaker_boost": True}}
        if i:                                       # contexto: la entonación enlaza con la frase anterior y la siguiente
            body["previous_text"] = texts[i - 1]
        if i + 1 < len(texts):
            body["next_text"] = texts[i + 1]
        out.append(_eleven_take(body, vid, key))
    return out


def _eleven_take(body, vid, key):
    """Una frase con ElevenLabs, comprobada: si repite o dice algo de más, se vuelve a grabar (la 2ª vez sin contexto,
    porque a veces el contexto "next_text" se cuela en el audio)."""
    t = body["text"]
    for take in range(3):
        if take == 1:
            body = {k: v for k, v in body.items() if k not in ("previous_text", "next_text")}
        for attempt in range(3):
            r = requests.post(f"{ELEVEN}/text-to-speech/{vid}?output_format=pcm_24000", json=body, timeout=180,
                              headers={"xi-api-key": key, "Content-Type": "application/json"})
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(8 * (attempt + 1)); continue
            if r.status_code >= 400:
                raise RuntimeError(f"elevenlabs {r.status_code}: {r.text[:200]}")
            break
        else:
            raise RuntimeError("elevenlabs: demasiados reintentos")
        a = _trim(np.frombuffer(r.content, dtype="<i2").astype(np.float32) / 32768)
        sim = _similarity(a, t)
        if not problem(a, t) and (sim is None or sim >= 0.7) and _sane(a, t):
            return a
        print(f"voice: elevenlabs retake {take + 1} for {t[:40]!r}", flush=True)
    raise RuntimeError(f"elevenlabs: ninguna toma buena para {t[:40]!r}")


# ------------------------------------------------------------------ local engines
_K = None


def _kokoro(text, speed=1.08):
    global _K
    if _K is None:
        from kokoro_onnx import Kokoro
        _K = Kokoro(os.path.join(HERE, "models", "kokoro.onnx"), os.path.join(HERE, "models", "voices.bin"))
    s, sr = _K.create(text, voice=KOKORO_VOICE, speed=speed, lang="es")
    return _trim(_resample(np.asarray(s, np.float32), sr))


def _mock(text, speed=1.0):
    """Voz simulada para pruebas sin red (VOICE_ENGINE=mock): un tono suave por sílaba aproximada."""
    n = max(1, len(re.findall(r"[aeiouáéíóú]+", _fold(text))))
    out = []
    for k in range(n):
        t = np.arange(int(SR * 0.16 / speed)) / SR
        out.append(np.sin(2 * np.pi * (180 + 20 * (k % 3)) * t) * np.sin(np.pi * t / t[-1]) * 0.3)
        if k % 6 == 5: out.append(np.zeros(int(SR * 0.12)))
    return np.concatenate(out).astype(np.float32)


CB_SCRIPT = r'''
import json, sys, torch, torchaudio
from chatterbox.tts import ChatterboxTTS
job = json.load(open(sys.argv[1]))
m = ChatterboxTTS.from_pretrained(device="cpu")
for i, t in enumerate(job["texts"]):
    w = m.generate(t, audio_prompt_path=job["ref"], exaggeration=job["exag"], cfg_weight=job["cfg"])
    torchaudio.save(f"{job['dir']}/{i}.wav", w, m.sr)
print("ok")
'''


def _chatterbox_batch(texts):
    d = tempfile.mkdtemp()
    ref = os.path.join(d, "ref.wav")
    sf.write(ref, _kokoro(REF_LINE, 1.0), SR)
    job = os.path.join(d, "job.json"); scr = os.path.join(d, "cb.py")
    json.dump({"texts": texts, "ref": ref, "dir": d, "exag": float(os.environ.get("VOICE_EXAG", "0.65")),
               "cfg": float(os.environ.get("VOICE_CFG", "0.45"))}, open(job, "w"))
    open(scr, "w").write(CB_SCRIPT)
    r = subprocess.run([CB_PY, scr, job], capture_output=True, text=True, timeout=1500)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    outs = []
    for i in range(len(texts)):
        a, sr = sf.read(os.path.join(d, f"{i}.wav"), dtype="float32")
        if a.ndim > 1: a = a.mean(1)
        outs.append(_trim(_resample(a, sr)))
    return outs


# ------------------------------------------------------------------ public
def say_many(texts, speed=1.08, styles=None, one_take=False, force=False):
    """Returns a list of float32 arrays at 24 kHz, one per text.
    styles: optional acting direction per line ("hushed, suspenseful"...).
    one_take: record all lines as one continuous performance (used for the story narration).
    All calls inside one reel use the same engine (see reset/LOCK); if that engine fails later in the
    reel, VoiceError is raised so the caller can redo the reel with a single consistent voice."""
    global ENGINE_USED, LOCK
    texts = [spoken_text(t) for t in texts]
    ck = (tuple(texts), tuple(styles or ()), one_take, LOCK)
    if ck in _CLIPS and not force:                   # force=True: grabar de nuevo aunque ya esté en la caché
        return [c.copy() for c in _CLIPS[ck]]
    out = _say_many(texts, speed, styles, one_take)
    _CLIPS[(tuple(texts), tuple(styles or ()), one_take, LOCK)] = [c.copy() for c in out]
    return out


_CLIPS = {}


def _say_many(texts, speed, styles, one_take):
    global ENGINE_USED, LOCK
    styles = list(styles or [None] * len(texts))
    pace = ("ritmo natural de conversación, sin prisa" if speed <= 1.03 else "ritmo ágil pero natural")
    key = os.environ.get("GEMINI_API_KEY")
    engine = os.environ.get("VOICE_ENGINE", "gemini").lower()
    if engine == "mock":
        ENGINE_USED = LOCK = "mock"
        return [_mock(t, speed) for t in texts]
    if os.environ.get("ELEVENLABS_API_KEY") and LOCK in (None, "elevenlabs"):
        try:                                       # la voz más humana disponible (de pago, opcional)
            clips = _eleven_many(texts)
            ENGINE_USED = LOCK = "elevenlabs"
            print(f"voice: elevenlabs ({len(texts)} lines)", flush=True)
            return [polish(c, light=True) for c in clips]
        except Exception as e:
            if LOCK == "elevenlabs":
                raise VoiceError(f"elevenlabs failed mid-reel: {str(e)[-200:]}")
            print("voice: elevenlabs failed, using gemini:", str(e)[-300:], flush=True)
    allow_gemini = (key and engine in ("gemini", "auto", "chatterbox", "elevenlabs") and os.environ.get("VOICE_NO_GEMINI") != "1"
                    and LOCK in (None, "gemini"))
    allow_cb = os.path.exists(CB_PY) and engine != "kokoro" and LOCK in (None, "local", "chatterbox")
    if allow_gemini:
        try:
            clips = _gemini_many(texts, styles, key, one_take, pace)
            ENGINE_USED = LOCK = "gemini"
            print(f"voice: gemini {GEMINI_VOICE} ({len(texts)} lines, one_take={one_take})", flush=True)
            return [polish(c, light=True) for c in clips]
        except Exception as e:
            if LOCK == "gemini":
                raise VoiceError(f"gemini failed mid-reel: {str(e)[-200:]}")
            print("voice: gemini failed, trying local voices:", str(e)[-300:], flush=True)
    if allow_cb:
        try:
            clips = _chatterbox_batch(texts); ENGINE_USED = LOCK = "chatterbox"
            print(f"voice: chatterbox ({len(texts)} lines)", flush=True)
            return [polish(c) for c in clips]
        except Exception as e:
            if LOCK == "chatterbox":
                raise VoiceError(f"chatterbox failed mid-reel: {str(e)[-200:]}")
            print("voice: chatterbox failed, using kokoro:", str(e)[-300:], flush=True)
    if LOCK not in (None, "local", "kokoro"):
        raise VoiceError(f"{LOCK} not available")
    clips = [_kokoro(t, speed) for t in texts]; ENGINE_USED = LOCK = "kokoro"
    print(f"voice: kokoro ({len(texts)} lines)", flush=True)
    return [polish(c) for c in clips]


def next_engine():
    """Engine to force after a VoiceError."""
    return {"elevenlabs": "gemini", "gemini": "local", "chatterbox": "kokoro"}.get(LOCK, "kokoro")
