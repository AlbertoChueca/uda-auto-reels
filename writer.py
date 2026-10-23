"""Guionista: escribe los textos del reel (gancho, revelado, explicación, trampa, mito, puntos clave, escena, cierre)
a partir SOLO de la pieza del banco, su cita verificada y el fragmento real de la fuente.

Los textos verificados de la pieza (enunciado, opciones, puntos clave, fichas) NUNCA los reescribe la IA: salen tal cual.
Sin GEMINI_API_KEY (o si falla) se usa template(): textos fijos + la explicación de la propia pieza, sin nada inventado.
"""
import json, os, re

import questions as QB

FORMATS = {
    "grafico": "Gráfico: las cifras que lo explican",
    "claves": "3 claves para el despacho",
    "comparativa": "Comparativa: dos formas de hacerlo",
    "dato": "Dato de proyecto que pocos conocen",
    "mito_realidad": "¿Mito o realidad?",
    "caso_despacho": "Caso de despacho",
}
AUDIENCE = """PÚBLICO: fundadores y socios de despachos de arquitectura y arquitectos autónomos de España que proyectan bloques
de viviendas, promociones y edificios de envergadura. Profesionales expertos con más encargos que horas que quieren
facturar más, cobrar mejor su hora y dedicar su tiempo a proyectar y a sus clientes. OBJETIVO: que vean, con datos
ciertos y criterio, que delegar la documentación técnica en UDA les hace crecer. TONO: premium, elegante y seguro, de
colega a colega, como un socio senior que comparte lo que sabe; con gancho y ritmo, nunca vendedor de teletienda, nunca
condescendiente ni con "¿sabías que...?" de manual. Español de España, tuteo. ESPAÑOL DE ESPAÑA (peninsular), nunca latinoamericano: tú y vosotros (nunca "ustedes" para el público), vocabulario de España (ordenador, móvil, vale, coger, pedir cita, encargo, obra, plantilla, autónomo); nunca "computadora", "celular", "agendar", "checar", "platicar", "chamba", "tomar un encargo" por coger.
Nada de promesas ("duplicarás tu
facturación"), ni estadísticas inventadas, ni decir o insinuar que UDA firma: la firma es siempre del despacho."""

SCHEMAS = {
    "grafico": '"intro_line": str (6-14 palabras: la voz plantea la pregunta que responde el gráfico, sin dar las cifras)',
    "claves": '"intro_line": str (6-16 palabras: la voz presenta las 3 claves sin adelantarlas)',
    "comparativa": '"intro_line": str (6-16 palabras: la voz plantea la disyuntiva de la comparativa)',
    "dato": '"intro_line": str (6-16 palabras: la voz prepara el dato sin desvelarlo)',
    "mito_realidad": '"intro_line": str (6-16 palabras: la voz presenta la creencia que vamos a comprobar)',
    "caso_despacho": '"escena": str (14-34 palabras, segunda persona y presente: una situación real de despacho (un encargo grande que entra, una entrega encima, el equipo a tope) que lleve a las 3 claves; SOLO ambientación, sin cifras ni datos nuevos), "escena_visual": str (máx. 40 palabras, la imagen de esa escena, sin texto)',
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

Escribe en español de España, frases MUY cortas y sencillas para decir en voz alta (máx. 12 palabras por frase), números en cifra.
Un fundador tiene que entenderlo a la primera: nada de jerga técnica ni normativa en lo que se dice.
Cada campo es EXACTAMENTE lo que se dice o se lee en pantalla: nunca escribas indicaciones de tono, de voz o de actuación
(nada de "tono seguro", "como si fueras un arquitecto", "(sonriendo)", "Narrador:"), ni menciones a quién habla.
Campos:
- "screen_hook": texto GRANDE de los 2 primeros segundos (2-6 palabras, sin emojis): que un arquitecto deje de hacer scroll.
- "hook_line": lo primero que dice la voz (5-14 palabras); no repitas literal el screen_hook.
- {SCHEMAS[fmt]}
- "cta_line": cierre hablado (10-22 palabras), elegante y nada agresivo, que lleve a uniondearquitectos.com con un hecho cierto de UDA (p. ej. delegar el proyecto con presupuesto cerrado en 24 horas, tu firma al final); puedes decir "link en la bio".
- "caption_hook": primera línea de la descripción (máx. 12 palabras, como mucho 1 emoji).
- "comment_prompt": invitación a comentar (máx. 12 palabras), una pregunta abierta a un colega.
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
    if fmt == "caso_despacho":
        if not (_w(s.get("escena"), 12, 36) and not re.search(r"\d", s.get("escena", ""))):
            raise ValueError("escena no válida")
        out["escena"] = re.sub(r"\s+", " ", s["escena"]).strip()
        if _w(s.get("escena_visual"), 5, 45):
            out["escena_visual"] = s["escena_visual"].strip()
    out.update(verified(fmt, P))                              # el contenido verificado de la pieza, tal cual
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


# Cierres hablados: todos dicen lo mismo que la tarjeta (24 h · repercutible al cliente · factura más · agenda una reunión)
CTAS = ["Presupuesto cerrado en 24 horas, que puedes repercutir a tu cliente, para que tu estudio facture más. "
        "Agenda una reunión desde el enlace del perfil para conocernos y crecer juntos.",
        "Mándanos tu próximo proyecto: en 24 horas tienes un presupuesto cerrado que puedes repercutir a tu cliente. "
        "Factura más sin ampliar plantilla. Agenda una reunión desde el perfil y crezcamos juntos.",
        "Seremos tu equipo técnico de confianza: presupuesto cerrado en 24 horas, repercutible a tu cliente, y más "
        "facturación para tu estudio. Agenda una reunión desde el perfil para conocernos."]
CTA_DEFAULT = CTAS[0]                                    # sin leer la web en voz alta


def verified(fmt, P):
    """Textos verificados de la pieza que el reel usa TAL CUAL (la IA nunca los reescribe)."""
    if P["tipo"] == "puntos":
        return {"titulo_norma": P["titulo"], "puntos": list(P["puntos"])}
    if P["tipo"] == "comparativa":
        return {"titulo_norma": P["titulo"], "col_a": P["col_a"], "col_b": P["col_b"], "filas": [dict(f) for f in P["filas"]]}
    if P["tipo"] == "cifras":
        return {"titulo_norma": P["titulo"], "barras": [dict(b) for b in P["barras"]], "conclusion": P["conclusion"]}
    if P["tipo"] == "curiosidad":
        return {"titulo_norma": P["screen_hook"], "beats": list(P["beats"]), "puente": P["puente"], "render": list(P["render"]),
                "badge": P["badge"], "fuente": P["fuente"]}
    if P["tipo"] == "caso":
        return {"titulo_norma": P["titulo"], "barras": [dict(b) for b in P["barras"]], "conclusion": P["conclusion"],
                "puntos": list(P["puntos"]), "puntos_titulo": P["puntos_titulo"], "escena": P["escena"],
                "infografia": P.get("infografia")}
    if P["tipo"] in ("dato", "mito"):
        out = {"afirmacion": P["afirmacion"], "explicacion": P["explicacion"]}
        if P["tipo"] == "mito":
            out["veredicto"] = P["veredicto"]
        return out
    return {}


def template(fmt, items):
    """Textos seguros sin IA: frases fijas + el contenido verificado de la pieza."""
    P = items[0]
    hooks = {"grafico": ("Las cifras lo dicen", "Mira lo que dicen las cifras."),
             "claves": ("3 claves para tu despacho", "Tres claves que cambian cómo funciona un despacho."),
             "comparativa": ("¿Contratar o delegar?", "Dos formas de sacar el trabajo. Compáralas."),
             "dato": ("Pocos lo saben", "Un dato de proyecto que pocos arquitectos tienen presente."),
             "mito_realidad": ("¿Mito o realidad?", "Mito o realidad. Piénsalo antes de que lo diga."),
             "caso_despacho": ("Caso de despacho", "Caso de despacho. Imagina que te llega este encargo."),
             "caso_coste": (P.get("screen_hook", ""), P.get("escena", "")),
             "infografia": (P.get("screen_hook", ""), P.get("escena", "")),
             "render": (P.get("screen_hook", ""), P.get("hook_line", ""))}
    sh, hl = hooks[fmt]
    if fmt == "comparativa" and P.get("col_a"):
        b = P["col_b"] if P["col_b"][:3].isupper() or P["col_b"].split()[0].isupper() else P["col_b"][0].lower() + P["col_b"][1:]
        sh = f"{P['col_a']} o {b}" if len(f"{P['col_a']} o {b}".split()) <= 6 else sh
    if fmt == "grafico" and P.get("titulo") and 2 <= len(P["titulo"].split()) <= 7:
        sh = P["titulo"]                                  # el gancho dice qué enseña el gráfico, no "las cifras lo dicen"
        hl = P["titulo"].rstrip(".") + ". Mira las cifras."
    ig = P.get("infografia") or {}
    extra_ig = {}
    if ig.get("cta"):                                     # tests, encuestas, atajos: cierre propio + invitación a comentar
        extra_ig = {"cta_line": ig["cta"], "comment_prompt": "¿Qué has contestado? Te leemos en comentarios",
                    "caption_hook": {"test": "Test para arquitectos 📐", "vf": "¿Verdadero o falso? 📐",
                                     "encuesta": "Encuesta para arquitectos 📐", "atajos": "Guárdalo 📌"}.get(ig.get("variante"),
                                                                                                         "Para arquitectos 📐")}
    return {"screen_hook": sh, "hook_line": hl, "reveal_line": "Vamos allá.",
            "intro_line": "Mira cómo cambian las cifras." if fmt == "grafico" else "Tres claves. Guárdalo para cuando lo necesites.",
            "cta_line": CTA_DEFAULT,
            "caption_hook": (P.get("hook_line", "") + " 🏛️") if fmt == "render" else P["escena"] + " 📐" if fmt in ("caso_coste", "infografia") else {"comparativa": "Dos formas de sacar el trabajo adelante 📐", "dato": "Un dato de proyecto que pocos tienen presente 📐",
                             "mito_realidad": "¿Mito o realidad en tu despacho? 📐"}.get(fmt, "Lo que cambia en un despacho que delega 📐"),
            "comment_prompt": {"render": "¿Lo sabías? Te leemos en comentarios",
                               "caso_coste": "¿Cuántos encargos tienes ahora mismo? Te leemos en comentarios",
                               "infografia": "¿Cuántos encargos tienes ahora mismo? Te leemos en comentarios",
                               "mito_realidad": "¿Mito o realidad? Te leemos en comentarios",
                               "comparativa": "¿Tú qué eliges? Te leemos en comentarios"}.get(fmt, "¿Qué añadirías tú? Te leemos en comentarios"),
            "cierre_line": "", **verified(fmt, P), **extra_ig}


def script_for(fmt, items, arms=None, avoid=(), verify=True, series_info=None):
    """Guion verificado. Hasta 2 intentos con IA; si no pasa el verificador -> plantilla segura (formatos que lo permiten)."""
    notes = None
    if fmt in ("caso_coste", "infografia", "render"):    # cifras calculadas / curiosidades comprobadas: textos fijos, la IA no reescribe nada
        s = strip_meta(fmt, items, template(fmt, items))
        if series_info:
            s["series"] = series_info["series"]; s["follow_line"] = f"Mañana: {series_info['manana']}. Síguenos"
        return s, fmt, "calculado"
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
    if fmt == "caso_despacho":
        raise RuntimeError(f"el formato {fmt} necesita un guion verificado")
    s = strip_meta(fmt, items, template(fmt, items))
    if series_info:
        s["series"] = series_info["series"]; s["follow_line"] = f"Mañana: {series_info['manana']}. Síguenos"
    return s, fmt, "plantilla"
