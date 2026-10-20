"""Guionista: escribe los textos del reel (gancho, revelado, explicación, trampa, mito, puntos clave, escena, cierre)
a partir SOLO de la pieza del banco, su cita verificada y el fragmento real de la fuente.

Los textos verificados de la pieza (enunciado, opciones, puntos clave, fichas) NUNCA los reescribe la IA: salen tal cual.
Sin GEMINI_API_KEY (o si falla) se usa template(): textos fijos + la explicación de la propia pieza, sin nada inventado.
"""
import json, os, re

import questions as QB

FORMATS = {
    "test_normativa": "Test de normativa",
    "error_tipico": "Error típico en proyecto",
    "mito_realidad": "¿Mito o realidad?",
    "norma_30s": "Normativa en 30 segundos",
    "simulacro_3": "Test rápido: 3 preguntas",
    "caso_despacho": "Caso de despacho",
    "checklist": "Checklist de proyecto",
    "delegar": "Contratar o delegar",
    "uda_servicio": "Así trabaja UDA",
    "repaso_express": "Repaso exprés con 4 fichas",
}
AUDIENCE = """PÚBLICO: despachos y arquitectos autónomos de España que proyectan bloques de viviendas, promociones, conjuntos residenciales y edificios de envergadura (equipamientos, naves, rehabilitaciones de edificios completos). Profesionales
expertos, exigentes y con más encargos que horas: no les cuentes obviedades ni definiciones de manual; háblales de lo que
importa en un proyecto grande (uso residencial colectivo, aparcamientos, zonas comunes, sectorización, evacuación,
plazos y responsabilidades). Nivel PREMIUM: preciso, útil y con criterio de arquitecto senior. Registro: de colega a
colega, directo, con gancho y ritmo, nunca plano ni condescendiente ("¿sabías que...?" de manual no). Español de España, tuteo. Nada de promesas ("duplicarás tu
facturación"), ni estadísticas inventadas ("el 80 % de los despachos..."), ni decir o insinuar que UDA firma: la firma es
siempre del despacho."""

SCHEMAS = {
    "test_normativa": '"explicacion": str (18-38 palabras: por qué es la correcta, con lo que dice la fuente)',
    "error_tipico": '"trampa": "A"|"B"|"C"|"D" (la opción INCORRECTA más tentadora), "trampa_porque": str (16-34 palabras: por qué engaña esa opción y qué dice de verdad la norma)',
    "caso_despacho": '"escena": str (14-34 palabras, segunda persona y presente: un encargo o una situación real de despacho que lleva a la pregunta; SOLO ambientación, sin datos técnicos, cifras ni normas, sin revelar la respuesta), "escena_visual": str (máx. 40 palabras, la imagen de esa escena, sin texto), "explicacion": str (18-38 palabras: por qué es la correcta)',
    "repaso_express": '"cierre_line": str (6-16 palabras, pregunta cuántas fichas sabía e invita a comentarlo y a guardar el reel)',
    "mito_realidad": '"afirmacion": str (8-24 palabras, una frase afirmativa sacada de la pieza: o la respuesta correcta reformulada (REALIDAD) o una opción incorrecta reformulada (MITO)), "veredicto": "MITO"|"REALIDAD", "explicacion": str (14-34 palabras)',
    "norma_30s": '"titulo_norma": str (2-8 palabras), "puntos": [str, str, str] (3 ideas clave de 5-14 palabras cada una, SOLO con datos de la cita, el fragmento de la fuente o la explicación)',
    "simulacro_3": '"cierre_line": str (6-16 palabras, invita a comentar cuántas ha acertado, p. ej. 3/3)',
    "checklist": '"intro_line": str (6-16 palabras: la voz presenta las 3 claves de la pieza sin adelantarlas)',
    "delegar": '"intro_line": str (6-16 palabras: la voz presenta las 3 claves de la pieza sin adelantarlas)',
    "uda_servicio": '"intro_line": str (6-16 palabras: la voz presenta las 3 claves de la pieza sin adelantarlas)',
}
WEB_RX = re.compile(r"uni[oó]n ?de ?arquitectos|uniondearquitectos", re.I)


def _brief(name):
    try:
        import agents
        return agents._brief(name)
    except Exception:
        return ""


def _material(items):
    import verifier
    return verifier.material(items)


def write(fmt, items, arms=None, avoid=(), notes=None):
    """Guion JSON del reel (Gemini). notes = problemas que encontró el verificador en un intento anterior."""
    import gemini, verifier
    arms = arms or {}
    pb = ""
    try:
        import strategy
        pb = strategy.playbook_text()
    except Exception:
        pass
    P = items[0]
    prompt = f"""Eres el GUIONISTA de los reels de UDA · Unión de Arquitectos (Instagram, TikTok y LinkedIn, @uniondearquitectos),
un estudio online que hace de departamento técnico externo para despachos de arquitectura (uniondearquitectos.com).
{AUDIENCE}

{_brief('guion')}
{_brief('gancho')}
{("LO QUE FUNCIONA CON NUESTRA AUDIENCIA (datos reales):" + chr(10) + pb) if pb else ""}

FORMATO DE HOY: {FORMATS[fmt]}. Estilo de gancho a probar (experimento): {arms.get('hook_style', 'el que mejor encaje')}.
MATERIAL (lo ÚNICO que puedes usar como dato; no añadas artículos, apartados, cifras, plazos ni nada que no esté aquí):
{_material(items)}
HECHOS CIERTOS DE UDA (solo para el cierre y la descripción):
{verifier.facts()}

Escribe en español de España, frases cortas para decir en voz alta (máx. 16 palabras por frase), números en cifra.
Cada campo es EXACTAMENTE lo que se dice o se lee en pantalla: nunca escribas indicaciones de tono, de voz o de actuación
(nada de "tono seguro", "como si fueras un arquitecto", "(sonriendo)", "Narrador:"), ni menciones a quién habla.
Campos:
- "screen_hook": texto GRANDE de los 2 primeros segundos (2-6 palabras, sin emojis): que un arquitecto deje de hacer scroll.
- "hook_line": lo primero que dice la voz (5-14 palabras); no repitas literal el screen_hook.
- "reveal_line": la voz da la solución (3-12 palabras), p. ej. "La correcta es la {P.get('letra', 'B')}." (solo la letra: NO vuelvas a leer el texto de la opción) (en formatos sin pregunta: una frase corta de transición).
- {SCHEMAS.get(fmt, SCHEMAS['test_normativa'])}
- "cta_line": cierre hablado (10-22 palabras) que lleve a uniondearquitectos.com con un hecho cierto de UDA (p. ej. delegar el proyecto con presupuesto cerrado en 24–72 horas); puedes decir "link en la bio".
- "caption_hook": primera línea de la descripción (máx. 12 palabras, como mucho 1 emoji).
- "comment_prompt": invitación a comentar (máx. 12 palabras), p. ej. "Comenta A, B, C o D antes de ver la solución".
No repitas ganchos recientes: {'; '.join(list(avoid)[-12:]) or 'ninguno'}.
{("CORRIGE ESTOS PROBLEMAS QUE ENCONTRÓ EL VERIFICADOR:" + chr(10) + json.dumps(notes, ensure_ascii=False)) if notes else ""}
Devuelve solo JSON con esos campos."""
    s = gemini.ask(prompt, 0.9)
    return clean(fmt, items, s)


# Indicaciones de actuación/registro que una IA puede colar en un texto que luego se LEE EN VOZ ALTA o sale en pantalla.
_ADJ = (r"(?:amable|cercan[oa]|c[aá]lid[oa]|alegre|did[aá]ctic[oa]|motivador[a]?|suave|segur[oa]|natural|neutr[oa]|"
        r"en[eé]rgic[oa]|c[oó]mplice|tranquil[oa]|firme|positiv[oa]|intrigante|rotund[oa]|claro|clara|amistos[oa]|"
        r"profesional|dulce|animad[oa]|emp[aá]tic[oa]|conversacional|informal|serio|seria|directo|directa|t[eé]cnic[oa])")
META = re.compile(r"\b(?:en )?(?:un )?tono " + _ADJ + r"|\btono de voz\b|como si fuer[ao]s?\b|como si (?:hablaras|estuvieras)\b|"
                  r"\b(?:con )?(?:una )?voz " + _ADJ + r"|\bvoz en off\b|"
                  r"\bnarrador(?:a)?\b|\blocutor(?:a)?\b|\bentonaci[oó]n\b|\bacento (?:peninsular|espa[nñ]ol|de espa[nñ]a|neutro)\b|"
                  r"\bparagraph\b|\btranscript\b|\bdirector'?s notes\b|\bnotas de (?:direcci[oó]n|actuaci[oó]n)\b|"
                  r"\bdelivery\b|\b(?:warm|friendly|calm|energetic|clear|punchy|confident) (?:tone|voice)\b|\bread (?:only|aloud)\b|"
                  r"\((?:[^)]*\b(?:voz|tono|sonr[ií]e|pausa|r[ií]e|susurr|enf[aá]tic)[^)]*)\)|\[[^\]]*\]|"
                  r"^\s*(?:narradora?|voz|locutora?|presentadora?)\s*:", re.I)
SPOKEN_KEYS = ("hook_line", "reveal_line", "cta_line", "explicacion", "trampa_porque", "afirmacion", "intro_line",
               "cierre_line", "escena", "puntos")


def has_meta(v):
    """True si el texto lleva indicaciones de tono/voz/escena en vez de solo lo que hay que decir o mostrar."""
    if isinstance(v, (list, tuple)):
        return any(has_meta(x) for x in v)
    return isinstance(v, str) and bool(META.search(v))


def strip_meta(fmt, items, s):
    """Última barrera: cualquier campo con indicaciones de actuación vuelve a la plantilla (o se elimina si es opcional)."""
    base = template(fmt, items)
    for k in list(s):
        if k in ("caption", "yt_title") or not has_meta(s[k]):
            continue
        if k in SPOKEN_KEYS and k not in base:
            raise ValueError(f"'{k}' lleva indicaciones de voz/tono")
        print(f"guion: quito indicaciones de voz/tono de '{k}': {str(s[k])[:80]!r}", flush=True)
        if k in base and not has_meta(base[k]):
            s[k] = base[k]
        else:
            s.pop(k)
    return s


def _w(v, lo, hi):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return v if lo <= len(v.split()) <= hi else None


def _nums(t):
    return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", str(t))}


def source_text(items):
    """Todo lo que el guion puede citar como dato: piezas, cita verificada, fragmento de la fuente y hechos de UDA."""
    import verifier
    return _material(items) + "\n" + verifier.facts()


def clean(fmt, items, s):
    """Valida longitudes y campos; lo que no cumple se sustituye por la plantilla segura."""
    base = template(fmt, items)
    out = dict(base)
    for k, lo, hi in (("screen_hook", 2, 6), ("hook_line", 4, 16), ("reveal_line", 2, 12), ("cta_line", 8, 24),
                      ("caption_hook", 3, 14), ("comment_prompt", 3, 14), ("explicacion", 10, 40),
                      ("trampa_porque", 12, 36), ("afirmacion", 6, 26), ("intro_line", 5, 18),
                      ("titulo_norma", 1, 8), ("cierre_line", 5, 18)):
        val = _w(s.get(k), lo, hi)
        if val:
            out[k] = val
    out["screen_hook"] = re.sub(r"[^\w\s¿?¡!,.:'-]", "", out["screen_hook"]).strip()
    P = items[0]
    letra = P.get("letra")
    m = re.search(r"\b(?:la|opci[oó]n|respuesta)\s+([ABCD])\b", out["reveal_line"])
    if letra and fmt not in ("simulacro_3", "repaso_express", "mito_realidad") and (not m or m.group(1) != letra):
        out["reveal_line"] = base["reveal_line"]              # la voz nunca puede decir una letra que no es la correcta
    if letra and fmt not in ("simulacro_3", "repaso_express", "mito_realidad") and P.get("op"):
        ok_txt = re.findall(r"\w+", P["op"][P["ok"]].lower())
        rv = " ".join(re.findall(r"\w+", out["reveal_line"].lower()))
        if len(ok_txt) >= 2 and any(" ".join(ok_txt[i:i + 3]) in rv for i in range(max(1, len(ok_txt) - 2))):
            out["reveal_line"] = base["reveal_line"]          # no vuelve a leer la opción: ya se ve marcada en pantalla
    if not WEB_RX.search(out["cta_line"]):
        out["cta_line"] = base["cta_line"]
    if fmt == "error_tipico":
        t = str(s.get("trampa") or "").strip().upper()[:1]
        if t in QB.LETTERS and t != letra and out.get("trampa_porque"):
            out["trampa"] = t
        else:
            raise ValueError("trampa no válida")
    if fmt == "mito_realidad":
        ver = str(s.get("veredicto") or "").strip().upper()
        if ver not in ("MITO", "REALIDAD") or not _w(s.get("afirmacion"), 6, 26):
            raise ValueError("mito/realidad no válido")
        out["veredicto"] = ver
    if fmt == "caso_despacho":
        if not (_w(s.get("escena"), 12, 36) and not re.search(r"\d", s.get("escena", ""))):
            raise ValueError("escena no válida")
        out["escena"] = re.sub(r"\s+", " ", s["escena"]).strip()
        if _w(s.get("escena_visual"), 5, 45):
            out["escena_visual"] = s["escena_visual"].strip()
    if fmt == "norma_30s":
        pts = [p for p in (s.get("puntos") or []) if _w(p, 4, 16)]
        if len(pts) != 3:
            raise ValueError("puntos no válidos")
        out["puntos"] = [re.sub(r"\s+", " ", p).strip() for p in pts]
    if fmt in QB.POINTS_ONLY:                                 # los puntos verificados de la pieza, tal cual
        out["titulo_norma"], out["puntos"] = P["titulo"], list(P["puntos"])
    allowed = _nums(source_text(items)) | {"3", "4", "30", "2"}
    for k, v in out.items():
        if k in ("trampa", "veredicto"):
            continue
        extra = _nums(v if isinstance(v, str) else " ".join(map(str, v))) - allowed
        if extra:
            if k in base and not (_nums(base[k]) - allowed) and k not in ("puntos", "titulo_norma", "explicacion",
                                                                             "trampa_porque", "afirmacion", "escena"):
                out[k] = base[k]
            else:
                raise ValueError(f"cifra {sorted(extra)[0]} en '{k}' que no está en el material (posible dato inventado)")
    return out


def _short_expl(text, max_words=40):
    """Explicación recortada por frases completas (nunca a mitad de frase)."""
    sent = re.split(r"(?<=[.;])\s+", (text or "").strip())
    out = []
    for s_ in sent:
        if out and len(" ".join(out + [s_]).split()) > max_words:
            break
        out.append(s_)
    res = " ".join(out)
    return res if len(res.split()) <= max_words + 12 else None


CTA_DEFAULT = "Y si vas justo de equipo, delega el proyecto: presupuesto cerrado en 24–72 horas en uniondearquitectos.com."


def template(fmt, items):
    """Textos seguros sin IA: frases fijas + la explicación verificada de la pieza."""
    P = items[0]
    ex = _short_expl(P.get("explicacion", "")) or ""
    letra = P.get("letra", "")
    tema = QB.tema_corto(P.get("tema"))
    hooks = {"test_normativa": ("¿Te lo sabes?", "Pregunta de normativa para arquitectos. A ver si la aciertas."),
             "error_tipico": ("Ojo con la trampa", "Esta pregunta tiene trampa. Y en un proyecto, sale cara."),
             "mito_realidad": ("¿Mito o realidad?", "Mito o realidad. Piénsalo antes de que lo diga."),
             "norma_30s": ("Normativa en 30 segundos", "Normativa en treinta segundos. Lo que tienes que saber."),
             "simulacro_3": ("¿Aciertas las 3?", "Tres preguntas rápidas de normativa. ¿Cuántas aciertas?"),
             "caso_despacho": ("Caso de despacho", "Caso de despacho. Imagina que te llega este encargo."),
             "checklist": ("Antes de entregar", "Tres cosas que revisar antes de entregar el proyecto."),
             "delegar": ("¿Contratar o delegar?", "Contratar o delegar. Tres claves antes de decidir."),
             "uda_servicio": ("Así trabaja UDA", "Así trabajamos en UDA, en tres claves."),
             "repaso_express": ("4 fichas de repaso", f"Repaso exprés de {tema}. ¿Cuántas sabes?")}
    sh, hl = hooks[fmt]
    return {"screen_hook": sh, "hook_line": hl, "reveal_line": f"La correcta es la {letra}." if letra else "Vamos allá.",
            "explicacion": ex, "intro_line": "Tres claves. Guárdalo para tu próximo proyecto.",
            "cta_line": CTA_DEFAULT,
            "caption_hook": {"delegar": "¿Contratar a alguien o delegar? 📐", "uda_servicio": "Así trabajamos en UDA 📐",
                             "checklist": "Revísalo antes de entregar el proyecto 📐"}.get(fmt, "¿La aciertas sin mirar la norma? 📐"),
            "comment_prompt": ("Comenta cuántas sabías, del 0 al 4" if fmt == "repaso_express"
                               else "¿Qué añadirías tú? Te leemos en comentarios" if fmt in QB.POINTS_ONLY
                               else "Comenta A, B, C o D antes de ver la solución"),
            "cierre_line": ("¿Cuántas sabías? Coméntalo y guarda el reel para repasar." if fmt == "repaso_express"
                            else "¿Cuántas has acertado? Comenta tu resultado, del cero al tres.")}


def script_for(fmt, items, arms=None, avoid=(), verify=True, series_info=None):
    """Guion verificado. Hasta 2 intentos con IA; si no pasa el verificador -> plantilla segura (formatos que lo permiten)."""
    notes = None
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("QUIZ_MOCK") != "1":
        for attempt in range(2):
            try:
                s = write(fmt, items, arms, avoid, notes)
            except Exception as e:
                print(f"guionista: intento {attempt + 1} fallido: {str(e)[:150]}", flush=True); continue
            try:                                          # revisor: pule gancho/descripción (no toca datos)
                import reviewer
                s = reviewer.improve_script(s, fmt, items, arms)
            except Exception as e:
                print("revisor omitido:", str(e)[:120], flush=True)
            try:                                          # estudio creativo: memoria, viralidad, embudo, SEO, series...
                import estudio
                s = estudio.text_pass(fmt, items, s, series_info)
            except Exception as e:
                print("estudio creativo omitido:", str(e)[:120], flush=True)
            try:
                s = strip_meta(fmt, items, s)
            except ValueError as e:
                notes = [str(e) + ": escribe solo lo que se dice, sin indicaciones de tono ni de voz"]
                print("guionista:", e, flush=True); continue
            if not verify:
                return s, fmt, "ia"
            import verifier
            ok, probs = verifier.verify_script(items, s, fmt)
            if ok:
                print("guionista: guion verificado", flush=True)
                return s, fmt, "ia"
            notes = probs
            print(f"verificador: guion rechazado: {json.dumps(probs, ensure_ascii=False)[:300]}", flush=True)
    if fmt in ("error_tipico", "mito_realidad", "norma_30s", "caso_despacho"):
        raise RuntimeError(f"el formato {fmt} necesita un guion verificado")
    s = strip_meta(fmt, items, template(fmt, items))
    if fmt in QB.POINTS_ONLY:
        s["titulo_norma"], s["puntos"] = items[0]["titulo"], list(items[0]["puntos"])
    if series_info:
        s["series"] = series_info["series"]; s["follow_line"] = f"Mañana: {series_info['manana']}. Síguenos"
    if not s["explicacion"] and fmt not in ("simulacro_3", "repaso_express") and fmt not in QB.POINTS_ONLY:
        raise RuntimeError("la explicación de la pieza es demasiado larga para el reel")
    return s, fmt, "plantilla"
