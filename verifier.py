"""Agente verificador: nada se publica sin pasar por aquí.

1. verify_piezas(): revisa cada pieza del banco ANTES de usarla, contra el texto REAL de su fuente (fuentes/*.txt:
   BOE descargado o documentos/web de UDA). Exige una CITA LITERAL que luego se comprueba en código: si la cita no
   aparece de verdad en el texto, la pieza no se publica (fuente_ok = false). Una respuesta de test debe ser la correcta
   y la única; unos puntos clave no pueden añadir nada que no diga la fuente; un precio de UDA tiene que presentarse como
   precio de referencia; si dos fuentes de UDA no coinciden (p. ej. plazos de la web frente a la tabla), "dudosa".
2. verify_script(): revisa lo que han escrito los agentes para el reel (explicación, trampa, mito, puntos, ganchos,
   cierre, descripción): solo puede decir lo que respaldan la pieza, su cita, la fuente y los hechos de UDA.
3. python verifier.py [N]  -> verifica N piezas pendientes y escribe banco/informe_verificacion.md.
"""
import datetime, json, os, re, sys, unicodedata

import questions as QB

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "fuentes")
REPORT = os.path.join(HERE, "banco", "informe_verificacion.md")
FACTS = os.path.join(HERE, "assets", "uda", "hechos.md")
STOP = set("de la el los las y o a en por para con que del al se su sus es un una lo le como mas más ser son este esta "
           "estos estas cual cuál cuales indique señale opcion opción correcta incorrecta respuesta según segun ley "
           "siguiente siguientes entre sobre sin no si real decreto artículo articulo".split())

ROLE = """Eres el VERIFICADOR de contenidos de UDA · Unión de Arquitectos, un estudio online que hace de departamento
técnico externo para arquitectos autónomos y despachos de España (Proyectos Básicos y de Ejecución, en CAD o Revit,
precio cerrado, la firma es del despacho). Publicamos normativa (CTE y sus DB, LOE, certificación energética, seguridad
y salud, residuos, Ley de Suelo, Propiedad Horizontal), consejos de proyecto, productividad del despacho y los servicios
de UDA. Tu trabajo es evitar que publiquemos un error: un arquitecto que proyecta con un dato falso tiene un problema
real con su proyecto, y nuestra credibilidad desaparece. Eres estricto y preciso, nunca inventas normativa, artículos,
apartados, cifras ni datos de UDA. Ante la duda, marcas "dudosa"."""


def fold(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def toks(t):
    return [w for w in re.findall(r"[a-z0-9]+", fold(t)) if w not in STOP and len(w) > 2]


def facts():
    try:
        return "\n".join(l.strip() for l in open(FACTS) if l.strip().startswith("-"))
    except Exception:
        return ""


# ------------------------------------------------------------------ fuentes
_CFG, _TXT, _ART = {}, {}, {}


def cfg():
    if not _CFG:
        _CFG.update(json.load(open(os.path.join(SRC_DIR, "fuentes.json"))))
    return _CFG


def norma(key):
    return cfg()["normas"].get(key) or {}


def norm_text(key):
    if key not in _TXT:
        p = os.path.join(SRC_DIR, norma(key).get("archivo", "-"))
        _TXT[key] = open(p).read() if os.path.exists(p) else ""
    return _TXT[key]


HEAD = re.compile(r"^(?:Art[íi]culo\s+\d+|Disposici[óo]n\s+(?:adicional|transitoria|final|derogatoria)|ANEJO|Anejo\s+[IVXL\d]+|"
                  r"Secci[óo]n\s+\S+|Documento\s+B[áa]sico|CAP[IÍ]TULO|Cap[íi]tulo\s+[IVXL\d]+|T[ÍI]TULO|"
                  r"\d{2}\s+[¿A-ZÁÉÍÓÚ]|\d+(?:\.\d+){0,2}\.?\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+)")
MAJOR = re.compile(r"^(?:Documento\s+B[áa]sico|Secci[óo]n|ANEJO|Anejo|Art[íi]culo|Disposici[óo]n|CAP[IÍ]TULO|Cap[íi]tulo|"
                   r"T[ÍI]TULO|\d{2}\s+[¿A-ZÁÉÍÓÚ])")


def articles(key, max_len=3200, min_len=420):
    """[(etiqueta, texto)] partiendo la fuente por artículos, secciones y apartados (y por longitud si hace falta).
    La etiqueta es el primer encabezado del fragmento, precedido del encabezado mayor (DB, sección, anejo...) si es otro."""
    if key in _ART:
        return _ART[key]
    lines = [l.strip() for l in norm_text(key).split("\n") if l.strip() and not l.startswith("# ")]
    out, cur, label, ctx, major = [], [], "", "", ""

    def flush():
        if cur:
            lab = label or cur[0][:70]
            out.append(((f"{ctx} · {lab}" if ctx and not MAJOR.match(lab) and not lab.startswith(ctx[:25]) else lab)[:110],
                        "\n".join(cur)))

    for s in lines:
        is_head = bool(HEAD.match(s)) and len(s) < 160
        size = sum(len(x) + 1 for x in cur)
        if cur and ((is_head and size >= min_len) or size + len(s) > max_len):
            flush()
            cur, ctx = [], major
            label = s[:90] if is_head else ((label or "") + (" (cont.)" if not (label or "").endswith("(cont.)") else ""))
        elif not cur:
            label, ctx = (s[:90] if is_head else ""), major
        if is_head and MAJOR.match(s):
            major = s[:70]
        cur.append(s)
    flush()
    _ART[key] = out
    return out


def chunks_for_tema(tema):
    """[(norma, etiqueta, texto)] de las fuentes del tema, filtradas por su expresión (si la tiene)."""
    t = cfg()["temas"][tema]
    rx = re.compile(t["filtro"], re.I) if t.get("filtro") else None
    out = []
    for key in t["normas"]:
        for lab, txt in articles(key):
            if len(txt) < 250 or re.search(r"(?i)^(?:pre[áa]mbulo|exposici[óo]n de motivos)", lab):
                continue
            if rx is None or rx.search(lab + " " + txt):
                out.append((key, lab, txt))
    return out


def sources_for(p):
    """Normas del tema de la pieza + cualquier norma cuyo número (p. ej. "38/1999") aparezca en su texto."""
    keys = list((cfg()["temas"].get(p.get("tema")) or {}).get("normas", []))
    if p.get("norma") and p["norma"] not in keys:
        keys.insert(0, p["norma"])
    txt = QB.text_of(p)
    for k, n in cfg()["normas"].items():
        nums = [c for c in n.get("clave", []) if re.match(r"\d+/\d{4}$", c)]
        if nums and any(re.search(rf"(?<!\d){re.escape(c)}(?!\d)", txt) for c in nums) and k not in keys:
            keys.append(k)
    return [k for k in keys if norm_text(k)]


def passages(p, k=3, max_chars=8000):
    """Fragmentos de la fuente más relacionados con la pieza (primero el que contiene su cita)."""
    want = set(toks(QB.text_of(p) + " " + p.get("cita", "")))
    scored, own = [], []
    for key in sources_for(p):
        title = norma(key).get("corto") or norma(key).get("titulo")
        for lab, txt in articles(key):
            if p.get("cita") and quote_in(p["cita"], [txt]):
                own.append((title, lab, txt)); continue
            s = len(want & set(toks(txt))) / (1 + 0.002 * len(txt))
            scored.append((s, title, lab, txt))
    scored.sort(key=lambda x: -x[0])
    out, total = [], 0
    for title, lab, txt in own[:2] + [(t, l, x) for _, t, l, x in scored[:k]]:
        txt = txt[:3200]
        out.append({"norma": title, "articulo": lab, "texto": txt}); total += len(txt)
        if total > max_chars:
            break
    return out


def quote_in(cita, texts):
    """¿La cita aparece de verdad en el texto de la fuente? (sin tildes ni mayúsculas, tolerante a puntuación)."""
    c = " ".join(re.findall(r"[a-z0-9]+", fold(cita)))
    if len(c.split()) < 5:
        return False
    hay = " ".join(re.findall(r"[a-z0-9]+", fold(" ".join(texts))))
    if c in hay:
        return True
    w = c.split(); grams = [" ".join(w[i:i + 5]) for i in range(max(1, len(w) - 4))]
    return sum(g in hay for g in grams) / len(grams) >= 0.85


def full_texts(p):
    return [norm_text(k) for k in sources_for(p)]


# ------------------------------------------------------------------ 1. piezas
def describe(p, i=None):
    head = f"### PIEZA {i} (id {p['id']}) · " if i else ""
    head += f"tipo {p['tipo']} · bloque {p['bloque']} · tema {QB.tema_titulo(p['tema'])}\n"
    if p["tipo"] == "test":
        body = (f"{p['pregunta']}\n" + "\n".join(f"{QB.LETTERS[k]}) {o}" for k, o in enumerate(p["opciones"]))
                + f"\nMarcada como correcta: {QB.LETTERS[p['correcta']]}\nExplicación: {p.get('explicacion')}\n")
    elif p["tipo"] == "puntos":
        body = f"Título: {p['titulo']}\n" + "\n".join(f"- {x}" for x in p["puntos"]) + "\n"
    else:
        body = f"Pregunta: {p['q']}\nRespuesta: {p['a']}\n"
    citas = [p.get("cita")] + list(p.get("citas_extra") or [])
    return head + body + f"Referencia propuesta: {p.get('referencia')}\nCita propuesta: " + " || ".join(c for c in citas if c) + "\n"


def verify_piezas(ps):
    """Verifica una lista de piezas y guarda el resultado en banco/verificacion.json. Devuelve {id: resultado}."""
    import gemini
    v = QB.verif()
    blocks = []
    for i, p in enumerate(ps, 1):
        src = passages(p)
        notas = "; ".join(f"{norma(k).get('corto')}: {norma(k)['nota']}" for k in sources_for(p) if norma(k).get("nota"))
        blocks.append(describe(p, i) + (f"Notas de vigencia: {notas}\n" if notas else "")
                      + ("TEXTO REAL DE LA FUENTE (fragmentos):\n" + "\n".join(f"[{s['norma']} · {s['articulo']}]\n{s['texto']}" for s in src)
                         if src else "TEXTO DE LA FUENTE: no disponible.") + "\n")
    res = gemini.ask(f"""{ROLE}

Revisa estas {len(ps)} piezas. Para cada una decide:
- "ok": TODO lo que afirma está respaldado por el texto real de la fuente que se da; si es un test, la respuesta marcada
  es correcta y es la ÚNICA correcta (las otras opciones son claramente incorrectas según la fuente) y el enunciado no
  es ambiguo; si son puntos clave, cada punto se deduce directamente de la fuente sin añadir datos, excepciones ni
  generalizaciones ("siempre", "nunca", "todos") que no estén; si es una ficha, la respuesta es correcta y completa.
- "dudosa": no puedes confirmarlo con el texto dado, es ambigua, el apartado puede haber cambiado (lee las notas de
  vigencia), dos fuentes de UDA dan datos distintos, o simplifica tanto que un arquitecto podría aplicarlo mal.
- "error": algo es falso o hay más de una respuesta correcta.
Además, en piezas de UDA: un precio solo es "ok" si se presenta como precio de referencia u orientativo; nunca puede
decir o insinuar que UDA firma, visa o asume la responsabilidad del proyecto (la firma es del despacho); nada de
promesas ni de estadísticas que no estén literalmente en la fuente.
"calidad": 1-10, cuánto le sirve de verdad a un despacho que proyecta bloques de viviendas y proyectos de envergadura
(10 = dato que evita un error caro o una incidencia en visado; 5 = correcto pero obvio o de manual; 1 = irrelevante).
"cita": un fragmento COPIADO LITERALMENTE del texto de la fuente (10-40 palabras) que demuestre la pieza (si no lo
hay, ""); "referencia": norma y artículo/sección/apartado exactos según el texto (p. ej. "CTE, Parte I, art. 11" o
"Tabla de presupuestos de UDA, apartado 07"); "motivo": una frase en español; "correccion": si es "error", qué es lo correcto.

{chr(10).join(blocks)}
Devuelve JSON: {{"resultados": [{{"id": str, "veredicto": "ok"|"dudosa"|"error", "calidad": number, "motivo": str,
"referencia": str, "cita": str, "correccion": str}}]}}""", 0.1, careful=True)
    lst = res.get("resultados") or res.get("results") or (res if isinstance(res, list) else [])
    lst = [r for r in lst if isinstance(r, dict)]
    got = {str(r.get("id")).strip(): r for r in lst}
    if lst and not any(p["id"] in got for p in ps) and len(lst) == len(ps):        # el modelo cambió los ids: por orden
        got = {p["id"]: r for p, r in zip(ps, lst)}
    out = {}
    for p in ps:
        r = got.get(p["id"])
        if not r:
            continue
        ver = r.get("veredicto") if r.get("veredicto") in ("ok", "dudosa", "error") else "dudosa"
        texts = full_texts(p)
        cita = (r.get("cita") or "").strip()
        fuente_ok = bool(texts and ((cita and quote_in(cita, texts)) or (p.get("cita") and quote_in(p["cita"], texts))))
        if not (cita and quote_in(cita, texts)):
            cita = p.get("cita", "") if fuente_ok else ""
        ref = (r.get("referencia") or p.get("referencia") or "").strip()
        try:
            cal = round(min(10.0, max(0.0, float(r.get("calidad")))), 1)
        except Exception:
            cal = 0.0
        out[p["id"]] = {"veredicto": ver, "calidad": cal, "motivo": (r.get("motivo") or "")[:300], "fuente_ok": fuente_ok,
                        "referencia": ref[:90] if fuente_ok else "", "cita": cita[:420] if fuente_ok else "",
                        "correccion": (r.get("correccion") or "")[:200] if ver == "error" else None,
                        "fecha": str(datetime.date.today())}
    v.update(out); QB.save_verif(v)
    n_ok = sum(1 for p in ps if QB.publishable(p, v))
    print(f"verificador: {len(out)} piezas revisadas, {n_ok} publicables", flush=True)
    return out


# ------------------------------------------------------------------ 2. guion del reel
SCRIPT_KEYS = ("hook_line", "screen_hook", "reveal_line", "explicacion", "trampa", "trampa_porque", "afirmacion",
               "veredicto", "puntos", "titulo_norma", "intro_line", "caption_hook", "comment_prompt", "escena", "save_line",
               "save_caption", "reto_line", "share_line", "tag_caption", "cta_line", "web_caption", "seo_line",
               "follow_line", "follow_caption", "cierre_line")


def material(items):
    """Material de referencia del reel: piezas, su cita comprobada y el fragmento de la fuente."""
    v = QB.verif(); ctx = []
    for P in items:
        r = v.get(P["id"], {})
        src = passages(P, k=1, max_chars=2500)
        ctx.append(describe(P).replace("Marcada como correcta", "Correcta")
                   + (f"Fuente verificada ({r.get('referencia')}): \"{r.get('cita')}\"\n" if r.get("fuente_ok") else "")
                   + ("Fragmento de la fuente:\n" + src[0]["texto"][:1800] + "\n" if src else ""))
    return "\n".join(ctx)


def verify_script(items, script, fmt):
    """items: piezas preparadas del reel. Devuelve (ok, problemas). Si el verificador falla, NO se aprueba."""
    import gemini
    texts = {k: script.get(k) for k in SCRIPT_KEYS if script.get(k)}
    try:
        res = gemini.ask(f"""{ROLE}
Formato del reel: {fmt}.
MATERIAL DE REFERENCIA (lo único que vale como verdad):
{material(items)}
HECHOS CIERTOS DE UDA (se pueden afirmar en ganchos, cierres y descripción):
{facts()}

TEXTOS QUE VAN A SALIR EN EL VÍDEO / DESCRIPCIÓN:
{json.dumps(texts, ensure_ascii=False, indent=1)}

Comprueba frase a frase: ¿todo lo que afirman estos textos está respaldado por el material o por los hechos de UDA?
Cualquier dato nuevo (artículo, apartado, cifra, plazo, porcentaje, precio, requisito, estadística del tipo "el 80 % de
los despachos...") que no esté ahí es un problema. La letra correcta, la trampa y el veredicto MITO/REALIDAD deben ser
coherentes con la pieza. También es un problema: prometer resultados ("duplicarás tu facturación"), decir o insinuar que
UDA firma o asume la responsabilidad del proyecto, dar un precio sin presentarlo como precio de referencia, o un tono
condescendiente con el arquitecto.
Devuelve JSON: {{"ok": bool, "problemas": [{{"campo": str, "frase": str, "motivo": str}}]}}""", 0.1, careful=True)
    except Exception as e:
        return False, [{"campo": "-", "frase": "-", "motivo": f"verificador no disponible: {str(e)[:150]}"}]
    probs = res.get("problemas") or []
    return bool(res.get("ok")) and not probs, probs


# ------------------------------------------------------------------ 3. informe del banco
def report():
    v = QB.verif(); ps = {p["id"]: p for p in QB.load()}
    rows = [(k, r) for k, r in v.items() if k in ps]
    pub, pend = QB.stock()
    bad = [(k, r) for k, r in rows if r["veredicto"] in ("error", "dudosa")]
    sin = [(k, r) for k, r in rows if r["veredicto"] == "ok" and not r.get("fuente_ok")]
    L = [f"# Informe del verificador ({datetime.date.today()})\n",
         f"- Piezas en el banco: {len(ps)} · revisadas: {len(rows)} · **publicables sin usar: {sum(pub.values())}** "
         f"({', '.join(f'{b} {n}' for b, n in pub.items())}) · pendientes: {sum(pend.values())}",
         f"- Errores: {sum(r['veredicto'] == 'error' for _, r in bad)} · dudosas: {sum(r['veredicto'] == 'dudosa' for _, r in bad)}"
         f" · correctas pero sin cita comprobada: {len(sin)}\n",
         "Las piezas con error o dudosas nunca se publican. Si alguna dudosa te parece correcta, no hace falta hacer nada: "
         "el generador crea piezas nuevas cada semana.\n"]
    for title, lst in (("Errores", [x for x in bad if x[1]["veredicto"] == "error"]),
                       ("Dudosas", [x for x in bad if x[1]["veredicto"] == "dudosa"])):
        L.append(f"\n## {title} ({len(lst)})\n")
        for k, r in lst[-150:]:
            p = ps[k]
            L.append(f"- **[{QB.tema_titulo(p['tema'])} · {p['tipo']}]** {QB.text_of(p)[:220]}\n  - {r.get('motivo')}"
                     + (f" · corrección: {r['correccion']}" if r.get("correccion") else ""))
    open(REPORT, "w").write("\n".join(L) + "\n")
    return f"verificador: {sum(pub.values())} publicables sin usar · {len(rows)} revisadas · {len(ps)} en el banco"


def run(n=80):
    v = QB.verif()
    import random
    pend = [p for p in QB.load() if p.get("fuente_ok") and (p["id"] not in v or (v[p["id"]].get("veredicto") == "ok"
                                                                               and "calidad" not in v[p["id"]]))]
    random.Random(str(datetime.date.today())).shuffle(pend)          # mezcla temas y bloques en cada tanda
    for k in range(0, min(n, len(pend)), 8):
        try:
            verify_piezas(pend[k:k + 8])
        except Exception as e:
            print("lote fallido:", str(e)[:200], flush=True)
    msg = report(); print(msg)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(open(REPORT).read()[:60000])
    return msg


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 80)
