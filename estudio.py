"""Estudio creativo: 10 agentes especialistas que hacen cada reel más premium, más útil y más compartible para que un
arquitecto siga la cuenta y, cuando vaya justo de equipo, piense en UDA. Se suman a la sala de guionistas (agents.py)
y al verificador (verifier.py); TODO lo que estos agentes escriben y sale en pantalla o en la descripción pasa después
por el verificador, así que pueden ser creativos sin poder colar un dato falso.

  1. directora_creativa  concepto visual del reel y la idea de la ilustración (coherente con el estilo del día)
  2. ilustradora         genera la imagen ORIGINAL (Gemini) para el gancho, el caso de despacho y el estilo "ilustrado"
  3. revisora_visual     revisa la imagen: sin texto, arquitectura y construcción creíbles, nada de edificios famosos
  4. narradora_casos     convierte la pieza en una escena de despacho (encargo, entrega, obra) sin añadir datos
  5. memoria             invita a GUARDAR el reel para consultarlo en el próximo proyecto
  6. viralidad           retos para comentar y enviar el reel al socio o al compañero de despacho
  7. series              series fijas por día de la semana con número de capítulo y avance de mañana -> seguir
  8. embudo_web          lleva a uniondearquitectos.com solo con hechos ciertos de UDA (assets/uda/hechos.md)
  9. seo                 palabras que busca un arquitecto (Instagram, TikTok, LinkedIn)
 10. ritmo               velocidad de la voz y energía de la música según lo que retiene a la audiencia

Cada agente tiene su cuaderno en agents/estudio_<nombre>.md, reescrito cada día con los resultados reales.
Todo es opcional: si un agente falla, el reel sigue con lo que ya tenía.
"""
import datetime, json, os, re

import marca as M

HERE = os.path.dirname(os.path.abspath(__file__))
NB_DIR = os.path.join(HERE, "agents")
STAMP = os.path.join(NB_DIR, "estudio_last_update.txt")
IMG_LOG = os.path.join(HERE, "image_log.jsonl")

ROLES = {
    "directora_creativa": "DIRECTORA CREATIVA. Decides el concepto visual de cada reel y la idea de la ilustración, para que "
                          "la cuenta se vea editorial, sobria y premium (como un buen estudio de arquitectura), sin repetir ideas.",
    "ilustradora": "ILUSTRADORA. Conviertes la idea en una imagen original vertical de calidad editorial, con la paleta de UDA "
                   "premium de UDA: negro profundo con luz cálida dorada.",
    "revisora_visual": "REVISORA VISUAL. Revisas cada imagen como lo haría una arquitecta exigente y una directora de arte: sin "
                       "texto, construcción y planos creíbles, sin edificios famosos reconocibles, nada sensible.",
    "narradora_casos": "NARRADORA DE CASOS. Conviertes una pieza de normativa en una escena breve y realista de despacho (un "
                       "encargo que entra, una entrega que se acerca, una duda en obra) para que se sienta como el día a día del arquitecto.",
    "memoria": "EXPERTA EN UTILIDAD. Haces que la gente GUARDE el reel para consultarlo cuando redacte su próximo proyecto.",
    "viralidad": "ESPECIALISTA EN COMPARTIR. Creas retos y frases que hacen que la gente comente y envíe el reel a su socio o a "
                 "un compañero de despacho.",
    "series": "RESPONSABLE DE SERIES. Construyes citas fijas (una serie por día de la semana, con número de capítulo) para que "
              "seguir la cuenta tenga sentido.",
    "embudo_web": "RESPONSABLE DE CONVERSIÓN. Conectas cada reel con lo que UDA hace por un despacho (uniondearquitectos.com), "
                  "solo con hechos ciertos de UDA y sin vender en exceso.",
    "seo": "ESPECIALISTA EN BÚSQUEDA (SEO social). Eliges las palabras exactas que busca un arquitecto en Instagram, TikTok y "
           "LinkedIn (normativa, CTE, proyecto de ejecución, despacho...) y las colocas de forma natural.",
    "ritmo": "EDITORA DE RITMO Y RETENCIÓN. Decides la velocidad de la voz y la energía de la música para que no se vayan antes "
             "de la solución.",
}
NAMES = list(ROLES)

# Serie fija de cada día (0 = lunes). El reel de las 12:00 sigue la serie; los de las 8:00 y las 15:00 los elige el piloto.
SERIES = {0: ("Lunes de cifras", "grafico"), 1: ("Martes de contratar o delegar", "comparativa"),
          2: ("Miércoles de claves para crecer", "claves"), 3: ("Jueves de mitos del despacho", "mito_realidad"),
          4: ("Viernes de cifras", "grafico"), 5: ("Sábado de casos de despacho", "caso_despacho"),
          6: ("Domingo de lo que delegas", "comparativa")}

AUDIENCE = ("Público: fundadores y socios de despachos de arquitectura y arquitectos autónomos de España que proyectan "
            "bloques, promociones y edificios de envergadura; quieren facturar más, cobrar mejor su hora y delegar. "
            "Contenido premium y elegante, nada de obviedades. ESPAÑOL DE ESPAÑA (peninsular), nunca latinoamericano: tú y vosotros (nunca \"ustedes\" para el público), vocabulario de España (ordenador, móvil, vale, coger, pedir cita, encargo, obra, plantilla, autónomo); nunca \"computadora\", \"celular\", \"agendar\", \"checar\", \"platicar\", \"chamba\", \"tomar un encargo\" por coger. "
            " Español de España, de colega a colega, profesional y directo, nunca condescendiente; sin "
            "promesas ni estadísticas inventadas; UDA nunca firma (la firma es del despacho).")


def _ask(prompt, temperature=0.7, careful=False, parts=None):
    import gemini
    return gemini.ask(parts or prompt, temperature, careful=careful)


def notebook(name):
    try:
        return open(os.path.join(NB_DIR, f"estudio_{name}.md")).read().strip()[:1200]
    except Exception:
        return ""


def brief(name):
    nb = notebook(name)
    com = ""
    try:
        import agents
        com = agents.notebook("comunidad")
    except Exception:
        pass
    return (f"Eres la {ROLES[name]}\n{AUDIENCE}" + (f"\nTU CUADERNO (lecciones de nuestros datos reales):\n{nb}" if nb else "")
            + (f"\nLO QUE DICE LA AUDIENCIA:\n{com}" if com else ""))


def _w(v, lo, hi):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return v if lo <= len(v.split()) <= hi else None


def _clean(v):
    return re.sub(r"[^\w\s¿?¡!,.:'()/–-]", "", v or "").strip()


def _log(kind, data):
    try:
        import reviewer
        reviewer._log("estudio_" + kind, data)
    except Exception:
        pass


def _desc(items):
    import questions as QB
    P = items[0]
    tema = QB.tema_titulo(P.get("tema"))
    if P["tipo"] == "ficha":
        return f"Fichas de {tema}: " + " | ".join(f"{f['q']} -> {f['a']}" for f in items)
    if P["tipo"] == "puntos":
        return f"Tema: {tema}. {P['titulo']}: " + " | ".join(P["puntos"])
    return f"Tema: {tema}. Pregunta: {P['pregunta']} Respuesta correcta: {P['op'][P['ok']]}"


# ------------------------------------------------------------------ 7. series (sin IA: siempre cierto)
def series_today(today=None, slot="mediodia"):
    today = today or datetime.date.today()
    name, fmt = SERIES[today.weekday()]
    n = 1
    try:
        for line in open(os.path.join(HERE, "log.jsonl")):
            if json.loads(line).get("series") == name:
                n += 1
    except Exception:
        pass
    nxt = SERIES[(today.weekday() + 1) % 7][0]
    return {"series": f"{name} · Nº {n}", "series_name": name, "series_fmt": fmt, "manana": nxt}


def series_lines(info, S):
    """Línea de seguir con el avance REAL de mañana (la serie de mañana es fija)."""
    out = {"follow_line": f"Mañana: {info['manana']}. Síguenos"}
    try:
        res = _ask(f"""{brief('series')}
Hoy es "{info['series']}". Mañana toca "{info['manana']}".
Escribe follow_line (máx. 8 palabras) para la tarjeta final que invite a seguir la cuenta para no perderse lo de mañana;
debe nombrar "{info['manana']}" tal cual. Y follow_caption (máx. 18 palabras) para la descripción.
Devuelve JSON: {{"follow_line": str, "follow_caption": str}}""")
        fl = _w(res.get("follow_line"), 3, 9)
        if fl and info["manana"].lower() in fl.lower():
            out["follow_line"] = _clean(fl)
        fc = _w(res.get("follow_caption"), 4, 20)
        if fc and info["manana"].lower() in fc.lower():
            out["follow_caption"] = fc
    except Exception as e:
        print("estudio series omitido:", str(e)[:120], flush=True)
    return out


# ------------------------------------------------------------------ 1. directora creativa
def directora(fmt, items, estilo, S):
    recent = []
    try:
        for line in open(IMG_LOG):
            recent.append(json.loads(line).get("idea"))
    except Exception:
        pass
    try:
        res = _ask(f"""{brief('directora_creativa')}
Reel de hoy: formato {fmt}, estilo visual "{estilo}". {_desc(items)}
Gancho: "{S.get('screen_hook')}". {('Escena: ' + S['escena']) if S.get('escena') else ''}
Propón:
- concepto: el concepto visual del reel en una frase (máx. 14 palabras).
- imagen_idea: UNA fotografía vertical editorial que acompañe (máx. 45 palabras): estudio de arquitectura luminoso,
  socios revisando planos de espaldas, maqueta de un bloque de viviendas, edificio residencial contemporáneo, obra de un
  bloque con grúa al atardecer, mesa con portátil y planos... relacionada con el tema (negocio, equipo, crecer) (sin texto ni cotas
  legibles, sin edificios famosos, sin logotipos). Que no se parezca a estas recientes: {'; '.join([r for r in recent if r][-10:]) or 'ninguna'}.
- usar_imagen_gancho: true si la imagen hará el gancho más potente que el fondo de marca.
Devuelve JSON: {{"concepto": str, "imagen_idea": str, "usar_imagen_gancho": bool}}""", 0.9)
        idea = _w(res.get("imagen_idea"), 6, 60)
        return {"concepto": _w(res.get("concepto"), 3, 16) or "", "imagen_idea": idea,
                "usar_imagen": True}                       # siempre: el gancho con foto se ve más premium
    except Exception as e:
        print("estudio directora omitida:", str(e)[:120], flush=True)
        return {"imagen_idea": None, "usar_imagen": False}


# ------------------------------------------------------------------ 2 + 3. ilustradora y revisora visual
ART = {"negro": "fotografía de arquitectura premium en clave baja: fondo casi negro, luz cálida dorada rasante, hormigón, piedra "
                "y detalles de latón, elegante y sobria, como una revista de arquitectura de lujo",
       "ilustrado": "fotografía de arquitectura editorial, luz natural lateral suave, tonos cálidos piedra y carbón con acentos bronce",
       "carbon": "fotografía de arquitectura en clave baja, sombras profundas y luz cálida puntual, tonos carbón y bronce",
       "plano": "ilustración técnica de línea fina sobre papel color piedra, estilo croquis de arquitecto",
       "ficha": "fotografía cenital sobria de una mesa de trabajo de arquitecto, papel, escalímetro y planos sin texto legible",
       "minimal": "fotografía minimalista de arquitectura, mucho espacio vacío, hormigón y madera, luz suave",
       "piedra": "fotografía editorial de arquitectura, tonos piedra y arena, luz natural suave"}
RULES = ("Imagen vertical 9:16. NADA de texto, letras, números, cotas legibles, carteles, logotipos ni marcas. Arquitectura "
         "genérica y verosímil (no edificios famosos ni reconocibles), construcción y detalles coherentes, sin personas "
         "identificables (si aparecen, de espaldas o desenfocadas), sin accidentes ni riesgos en obra (si hay obra, EPI "
         "correctos: casco, chaleco, calzado). El motivo principal en el centro y la parte inferior más oscura y despejada "
         "(ahí irá texto).")


def ilustradora(idea, estilo, seed=0):
    import gemini
    prompt = f"{ART.get(estilo, ART['negro'])}. Escena: {idea}. {RULES}"
    return gemini.image(prompt), prompt


def revisora(img, idea):
    """Devuelve (ok, motivo, mejor_idea)."""
    import base64, io
    b = io.BytesIO(); im = img.copy(); im.thumbnail((640, 640)); im.convert("RGB").save(b, "JPEG", quality=82)
    try:
        res = _ask(None, 0.2, parts=[{"text": f"""{brief('revisora_visual')}
Idea pedida: {idea}
Revisa la imagen: ¿hay texto, letras, números, cotas legibles o logotipos? ¿la arquitectura o la construcción es
incoherente (estructuras imposibles, escaleras sin sentido, carpinterías absurdas)? ¿parece un edificio famoso? ¿hay
personas identificables, riesgos en obra o EPI incorrectos? ¿se ve editorial y sobria? ¿el centro y la parte de abajo
dejan sitio para texto?
"ok" = true solo si no hay ningún problema que un arquitecto notaría.
Devuelve JSON: {{"ok": bool, "problemas": [str], "mejor_idea": str}}"""},
                                         {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}])
        return bool(res.get("ok")), "; ".join(res.get("problemas") or [])[:300], _w(res.get("mejor_idea"), 6, 60)
    except Exception as e:
        return False, f"revisora no disponible: {str(e)[:100]}", None


def imagen_para(fmt, items, estilo, S, out_base):
    """Directora -> ilustradora -> revisora (1 redibujo). Devuelve (imagen o None, info)."""
    d = directora(fmt, items, estilo, S)
    idea = d.get("imagen_idea") or S.get("escena_visual")
    if S.get("escena_visual") and fmt == "caso_despacho":
        idea = S["escena_visual"]
    if not idea or not d.get("usar_imagen"):
        return None, d
    for attempt in range(2):
        try:
            img, prompt = ilustradora(idea, estilo)
        except Exception as e:
            print("estudio ilustradora: sin imagen:", str(e)[:150], flush=True)
            return None, d
        ok, why, better = revisora(img, idea)
        print(f"estudio revisora visual: {'ok' if ok else 'rechazada'} {why[:120]}", flush=True)
        try:
            with open(IMG_LOG, "a") as f:
                f.write(json.dumps({"date": str(datetime.date.today()), "idea": idea, "ok": ok, "problemas": why},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        if ok:
            img.save(out_base + "_ilustracion.jpg", quality=90)
            d["imagen_idea"] = idea
            return img, d
        idea = better or idea
    return None, d


# ------------------------------------------------------------------ 4. narradora de casos
def narradora(items, S):
    """Pule la escena del caso de despacho y da la idea visual. Sin datos técnicos ni normativos nuevos."""
    try:
        res = _ask(f"""{brief('narradora_casos')}
{_desc(items)}
Escena actual: "{S.get('escena')}"
Reescribe la escena (14-34 palabras, segunda persona, presente: "Te entra un encargo de..."): situación concreta y
creíble de despacho, de entrega o de obra que lleve a la pregunta. Prohibido añadir datos técnicos, cifras, plazos o
normas: solo ambientación (qué encargo, qué fase del proyecto, quién pregunta). No reveles la respuesta.
Y escena_visual: descripción de la imagen de esa escena (máx. 40 palabras, sin texto).
Devuelve JSON: {{"escena": str, "escena_visual": str}}""", 0.8)
        out = {}
        if _w(res.get("escena"), 12, 36) and not re.search(r"\d", res["escena"]):
            out["escena"] = res["escena"].strip()
        if _w(res.get("escena_visual"), 6, 45):
            out["escena_visual"] = res["escena_visual"].strip()
        return out
    except Exception as e:
        print("estudio narradora omitida:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ 5. memoria (utilidad)
def memoria(fmt, items, S):
    try:
        res = _ask(f"""{brief('memoria')}
Formato {fmt}. {_desc(items)}
Escribe:
- save_line: texto corto en pantalla (máx. 6 palabras) que invite a GUARDAR el reel (p. ej. "Guárdalo para tu próximo proyecto").
- save_caption: una línea para la descripción (máx. 22 palabras) sobre cuándo le será útil volver a este reel (al redactar
  la memoria, antes de visar, al revisar planos...). Sin datos técnicos nuevos, sin promesas.
Devuelve JSON: {{"save_line": str, "save_caption": str}}""", 0.8)
        out = {}
        if _w(res.get("save_line"), 2, 6): out["save_line"] = _clean(res["save_line"])
        if _w(res.get("save_caption"), 6, 24) and not re.search(r"\d", res["save_caption"]): out["save_caption"] = res["save_caption"].strip()
        return out
    except Exception as e:
        print("estudio memoria omitida:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ 6. viralidad
def viralidad(fmt, items, S):
    try:
        res = _ask(f"""{brief('viralidad')}
Formato {fmt}. {_desc(items)} Gancho: "{S.get('screen_hook')}".
Escribe:
- reto_line: reto en pantalla durante la cuenta atrás (máx. 6 palabras), p. ej. "¿Tu socio la acierta?".
- share_line: línea de la tarjeta final (máx. 7 palabras) para enviar el reel a un socio o compañero de despacho.
- tag_caption: línea de la descripción (máx. 18 palabras) para mencionar a un compañero de profesión con un mini reto.
Sin datos técnicos, sin desvelar la respuesta, sin promesas, nada que ridiculice a nadie.
Devuelve JSON: {{"reto_line": str, "share_line": str, "tag_caption": str}}""", 0.9)
        out = {}
        if _w(res.get("reto_line"), 2, 6): out["reto_line"] = _clean(res["reto_line"])
        if _w(res.get("share_line"), 2, 7): out["share_line"] = _clean(res["share_line"])
        if _w(res.get("tag_caption"), 4, 20): out["tag_caption"] = res["tag_caption"].strip()
        return out
    except Exception as e:
        print("estudio viralidad omitida:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ 8. embudo a la web (solo hechos ciertos)
def embudo(fmt, items, S):
    import verifier
    hechos = verifier.facts()
    try:
        res = _ask(f"""{brief('embudo_web')}
Formato {fmt}. {_desc(items)}
HECHOS CIERTOS DE UDA (usa solo estos; ninguna cifra que no esté aquí):
{hechos}
Escribe:
- cta_line: cierre hablado (10-22 palabras) que conecte el tema del reel con delegar el proyecto en UDA; nombra
  "uniondearquitectos.com". Sin vender en exceso, de colega a colega.
- web_caption: línea de la descripción (máx. 24 palabras) con un hecho cierto de UDA relacionado con el reel.
Devuelve JSON: {{"cta_line": str, "web_caption": str}}""", 0.7)
        out = {}
        allowed = set(re.findall(r"\d[\d.,–-]*\d|\d", hechos))
        for k, lo, hi in (("cta_line", 8, 24), ("web_caption", 5, 26)):
            v = _w(res.get(k), lo, hi)
            nums = re.findall(r"\d[\d.,–-]*\d|\d", v or "")
            if v and all(n in allowed for n in nums) and (k != "cta_line" or "uniondearquitectos" in v.lower().replace(" ", "")):
                out[k] = v
        return out
    except Exception as e:
        print("estudio embudo omitido:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ 9. SEO
def seo(fmt, items, S):
    try:
        res = _ask(f"""{brief('seo')}
Formato {fmt}. {_desc(items)} Gancho: "{S.get('screen_hook')}".
Escribe seo_line: una frase natural para la descripción (máx. 20 palabras) con 2-3 búsquedas típicas de un arquitecto
(p. ej. "normativa CTE", "proyecto de ejecución", "despacho de arquitectura", el DB o la ley del tema), sin datos nuevos.
Devuelve JSON: {{"seo_line": str}}""", 0.6)
        v = _w(res.get("seo_line"), 5, 22)
        return {"seo_line": v.strip()} if v and not re.search(r"\d+ ?%", v) else {}
    except Exception as e:
        print("estudio seo omitido:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ 10. ritmo
def ritmo(fmt, S):
    perf = []
    try:
        for r in json.load(open(os.path.join(HERE, "performance.json"))).values():
            if r.get("views"):
                perf.append(f"{r.get('formato')}/{r.get('estilo')}: views {r.get('views')}, visionado medio "
                            f"{r.get('ig_reels_avg_watch_time')} ms, velocidad voz {r.get('voice_speed')}, música {r.get('music')}")
    except Exception:
        pass
    try:
        res = _ask(f"""{brief('ritmo')}
Formato {fmt}. Datos de retención reales: {'; '.join(perf[-20:]) or 'aún no hay'}.
Elige voice_speed (entre 1.00 y 1.12; 1.05 es normal) y music ("calma", "normal" o "energica") para que el público se quede
hasta el final sin agobiarse. Devuelve JSON: {{"voice_speed": number, "music": str, "why": str}}""", 0.4)
        out = {}
        try:
            out["voice_speed"] = round(min(1.12, max(1.0, float(res.get("voice_speed")))), 2)
        except Exception:
            pass
        if res.get("music") in ("calma", "normal", "energica"):
            out["music"] = res["music"]
        return out
    except Exception as e:
        print("estudio ritmo omitido:", str(e)[:120], flush=True)
        return {}


# ------------------------------------------------------------------ pasada de textos (antes del verificador)
def text_pass(fmt, items, S, series_info=None):
    """Agentes 4-10 en paralelo. Devuelve S ampliado (todo esto lo revisa después el verificador)."""
    from concurrent.futures import ThreadPoolExecutor
    jobs = {"memoria": lambda: memoria(fmt, items, S), "viralidad": lambda: viralidad(fmt, items, S),
            "seo": lambda: seo(fmt, items, S), "ritmo": lambda: ritmo(fmt, S), "embudo": lambda: embudo(fmt, items, S)}
    if fmt == "caso_despacho":
        jobs["narradora"] = lambda: narradora(items, S)
    if series_info:
        jobs["series"] = lambda: series_lines(series_info, S)
    out = dict(S)
    with ThreadPoolExecutor(7) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                res = f.result(timeout=240) or {}
                out.update(res)
                _log(k, {"campos": list(res)})
            except Exception as e:
                print(f"estudio {k} omitido:", str(e)[:120], flush=True)
    if series_info:
        out["series"] = series_info["series"]
        out.setdefault("follow_line", f"Mañana: {series_info['manana']}. Síguenos")
    return out


# ------------------------------------------------------------------ aprendizaje diario
def daily_learning(force=False):
    os.makedirs(NB_DIR, exist_ok=True)
    today = str(datetime.date.today())
    if not force and os.path.exists(STAMP) and open(STAMP).read().strip() == today:
        return "estudio: cuadernos ya actualizados hoy"
    try:
        perf = json.load(open(os.path.join(HERE, "performance.json")))
    except Exception:
        perf = {}
    rows = [r for r in perf.values() if r.get("hook")]
    if len(rows) < 3:
        return "estudio: esperando resultados (hacen falta 3+ publicaciones medidas)"
    import strategy
    rows.sort(key=lambda r: -(strategy.reward(r) or 0))
    table = "\n".join(
        f"- score {strategy.reward(r) or 0:.2f} | views {r.get('views')} | guardados {r.get('saved')} | compartidos {r.get('shares')} | "
        f"comentarios {r.get('comments')} | clics {r.get('clicks')} | visionado {r.get('ig_reels_avg_watch_time')} ms | "
        f"{r.get('formato')} | estilo {r.get('estilo')} | serie {r.get('series')} | imagen {'sí' if r.get('imagen') else 'no'} | "
        f"gancho: {r.get('hook')}" for r in rows[:30])
    imgs = []
    try:
        imgs = [json.loads(l) for l in open(IMG_LOG)][-15:]
    except Exception:
        pass
    old = {n: notebook(n) for n in NAMES}
    try:
        res = _ask(f"""Coordinas el estudio creativo (10 agentes) de los reels de UDA · Unión de Arquitectos. Roles:
{json.dumps(ROLES, indent=1, ensure_ascii=False)}

RESULTADOS REALES (mejores primero; suma de Instagram, TikTok y LinkedIn):
{table}

ÚLTIMAS IMÁGENES (idea, aprobada o no, problemas): {json.dumps(imgs, ensure_ascii=False)[:2500]}

CUADERNOS ACTUALES: {json.dumps(old, ensure_ascii=False)[:6000]}

Reescribe el cuaderno de cada agente (máx. 90 palabras, viñetas: Seguir haciendo / Dejar de hacer / Probar), concreto y
basado en estos datos. Si los datos no bastan, dilo. Devuelve JSON con una clave por agente: {json.dumps(NAMES)}""", 0.4)
    except Exception as e:
        return f"estudio: aprendizaje omitido ({str(e)[:120]})"
    n = 0
    for name in NAMES:
        txt = (res.get(name) or "").strip()
        if 20 <= len(txt) <= 1200:
            open(os.path.join(NB_DIR, f"estudio_{name}.md"), "w").write(f"# Cuaderno de {name} ({today})\n\n{txt}\n")
            n += 1
    open(STAMP, "w").write(today)
    return f"estudio: {n}/10 cuadernos actualizados"
