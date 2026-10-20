"""Generador del banco de piezas (sustituye al banco importado de la web app de TCAE).

Para cada llamada elige un bloque con poca reserva (normativa, proyecto, productividad, servicios), un tema de ese
bloque y UN fragmento real de su fuente (artículo o sección del BOE, o apartado de los documentos/web de UDA) y pide a
Gemini piezas sacadas SOLO de ese fragmento:
  test    pregunta + 4 opciones + correcta + explicación
  puntos  título + 3 ideas clave (checklist de proyecto / productividad / servicios)
  ficha   pregunta corta -> respuesta corta
Cada pieza trae su CITA LITERAL y el código comprueba que está de verdad en el fragmento; también que toda cifra que
afirma está en el fragmento, que un precio se presenta como precio de referencia y que nunca dice que UDA firma.
Lo que no pasa se descarta antes de guardarse. Después, el verificador (otro modelo, más estricto) revisa cada pieza;
solo las "ok" se publican.

    python generar_banco.py [llamadas]      (por defecto 14; cada llamada da 2-4 piezas)
"""
import datetime, hashlib, json, os, random, re, sys

import questions as QB
import verifier as V

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "banco", "generado.json")
TARGET = {"normativa": 70, "proyecto": 45, "productividad": 20, "servicios": 25}       # reserva deseada (sin usar)
PIDE = {"normativa": "2 de tipo test y 2 de tipo ficha", "proyecto": "1 de tipo puntos, 1 de tipo test y 1 de tipo ficha",
        "productividad": "1 de tipo puntos y 1 de tipo test", "servicios": "1 de tipo puntos, 1 de tipo test y 1 de tipo ficha"}
GUIA = {
    "normativa": "NORMATIVA: datos concretos y útiles para un arquitecto que redacta proyectos en España: qué exige la norma, "
                 "cuándo se aplica, qué documento o agente interviene, qué valor o límite fija (solo si está en el texto).",
    "proyecto": "CONSEJOS DE PROYECTO: qué conviene comprobar, incluir o justificar al redactar el Proyecto Básico o de "
                "Ejecución para cumplir este texto. Los puntos en imperativo y en segunda persona (\"Comprueba...\", "
                "\"Incluye...\", \"Justifica...\"), cada uno sacado directamente del texto, sin añadir requisitos.",
    "productividad": "PRODUCTIVIDAD DEL DESPACHO: cómo ganar capacidad y facturar más sin ampliar plantilla, qué cuesta "
                     "realmente contratar frente a delegar, recuperar tiempo para proyectar, plazos que no dependen de una "
                     "sola persona. SOLO lo que dice el texto de UDA; cifras exactamente como aparecen.",
    "servicios": "SERVICIOS DE UDA: qué hace UDA, qué incluye cada partida, cómo se presupuesta y se paga, CAD o Revit, "
                 "actuaciones específicas, condiciones, qué no incluye. Un precio SIEMPRE como \"precio de referencia\" "
                 "(el definitivo es el presupuesto cerrado). La firma corresponde siempre al despacho: UDA nunca firma.",
}
SCHEMA = """{"piezas": [
 {"tipo": "test", "pregunta": str (máx. 150 caracteres, clara, sin "según el texto"), "opciones": [str, str, str, str] (máx. 70 caracteres cada una, 1 correcta y 3 incorrectas verosímiles pero claramente falsas según el texto), "correcta": 0-3, "explicacion": str (15-40 palabras: por qué es la correcta), "cita": str, "referencia": str},
 {"tipo": "puntos", "titulo": str (2-7 palabras), "puntos": [str, str, str] (6-15 palabras cada uno), "citas": [str, ...] (1-3 citas literales que respaldan los puntos), "referencia": str},
 {"tipo": "ficha", "q": str (pregunta corta, máx. 100 caracteres), "a": str (respuesta corta y completa, máx. 140 caracteres), "cita": str, "referencia": str}
]}"""
AUD = ("Público: despachos y arquitectos autónomos de España que proyectan bloques de viviendas, promociones, conjuntos residenciales y edificios de envergadura (equipamientos, naves, rehabilitaciones de edificios completos). Son expertos: nivel PREMIUM, nada de obviedades ni "
       "definiciones de diccionario; prioriza lo que pesa en bloques y proyectos grandes (uso residencial colectivo, "
       "aparcamientos, zonas comunes, sectorización, evacuación, accesibilidad, ahorro de energía, agentes y responsabilidades)."
       "  Español de España, tuteo, registro profesional y directo; nada de promesas ni de estadísticas.")


def state():
    try:
        return json.load(open(GEN))
    except Exception:
        return {"chunks": {}, "temas": {}}


def chash(key, lab, txt):
    return hashlib.sha1(f"{key}|{lab}|{txt[:400]}".encode()).hexdigest()[:12]


def _nums(t):
    return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", t)}


def _jacc(a, b):
    a, b = set(V.toks(a)), set(V.toks(b))
    return len(a & b) / max(1, len(a | b))


def clean(raw, tema, bloque, key, lab, txt, existing):
    """Valida una pieza propuesta. Devuelve la pieza lista para guardar o (None, motivo)."""
    t = raw.get("tipo")
    W = lambda s: len(str(s or "").split())
    sp = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
    p = {"tema": tema, "bloque": bloque, "tipo": t, "norma": key, "fuente": lab, "referencia": sp(raw.get("referencia"))[:90]}
    if t == "test":
        ops = [sp(o) for o in (raw.get("opciones") or [])]
        try:
            c = int(raw.get("correcta"))
        except Exception:
            return None, "correcta no válida"
        if len(ops) != 4 or len(set(o.lower() for o in ops)) != 4 or not 0 <= c < 4 or not all(1 <= len(o) <= 80 for o in ops):
            return None, "opciones no válidas"
        p.update(pregunta=sp(raw.get("pregunta")), opciones=ops, correcta=c, explicacion=sp(raw.get("explicacion")),
                 cita=sp(raw.get("cita")))
        if not 15 <= len(p["pregunta"]) <= 170 or not 10 <= W(p["explicacion"]) <= 45:
            return None, "longitudes"
        claims = " ".join([p["pregunta"], ops[c], p["explicacion"]])
        main = p["pregunta"] + " " + ops[c]
        citas = [p["cita"]]
    elif t == "puntos":
        pts = [sp(x) for x in (raw.get("puntos") or [])]
        citas = [sp(x) for x in (raw.get("citas") or [])][:3]
        if len(pts) != 3 or not all(4 <= W(x) <= 18 for x in pts) or not 1 <= W(raw.get("titulo")) <= 8 or not citas:
            return None, "puntos no válidos"
        p.update(titulo=sp(raw.get("titulo")), puntos=pts, cita=citas[0], citas_extra=citas[1:])
        claims = " ".join([p["titulo"]] + pts)
        main = claims
    elif t == "ficha":
        p.update(q=sp(raw.get("q")), a=sp(raw.get("a")), cita=sp(raw.get("cita")))
        if not 10 <= len(p["q"]) <= 110 or not 3 <= len(p["a"]) <= 160:
            return None, "ficha no válida"
        claims = p["q"] + " " + p["a"]
        main = claims
        citas = [p["cita"]]
    else:
        return None, f"tipo {t!r}"
    if not all(c and V.quote_in(c, [txt]) for c in citas):
        return None, "la cita no está literalmente en el fragmento"
    falt = _nums(claims) - _nums(txt)
    if falt:
        return None, f"cifras que no están en la fuente: {sorted(falt)[:4]}"
    if "€" in claims and not re.search(r"referencia|orientativ|estimativ", claims, re.I):
        return None, "precio sin decir que es de referencia"
    if re.search(r"\bUDA\b[^.]{0,30}\b(firma|visa|asume la responsabilidad)", claims, re.I):
        return None, "dice que UDA firma"
    import writer
    if writer.has_meta(claims):
        return None, "lleva indicaciones de tono"
    for e in existing:
        if e["tipo"] == t and _jacc(main, e["_main"]) > 0.72:
            return None, "repetida"
    p["id"] = QB.pid(tema, t, main)
    p["fuente_ok"] = True
    p["fecha"] = str(datetime.date.today())
    p["_main"] = main
    return p, "ok"


def choose(st, rng):
    """(bloque, tema, (norma, etiqueta, texto)) con más necesidad."""
    pub, pend = QB.stock()
    need = sorted(QB.BLOQUES, key=lambda b: (pub[b] + pend[b]) / TARGET[b])
    temas = QB.cfg()["temas"]
    for b in need:
        cands = [t for t, d in temas.items() if b in d["bloques"]]
        rng.shuffle(cands)
        cands.sort(key=lambda t: st["temas"].get(t, ""))                  # el tema que hace más que no se genera
        for t in cands:
            chunks = V.chunks_for_tema(t)
            if not chunks:
                continue
            fresh = [c for c in chunks if chash(*c) not in st["chunks"]]
            pool = fresh or sorted(chunks, key=lambda c: st["chunks"].get(chash(*c), {}).get("veces", 0))[:4]
            if not fresh and not t.startswith("uda_"):
                continue                                                 # norma agotada: otro tema
            return b, t, rng.choice(pool)
    return None


def generate_one(b, tema, chunk, existing):
    import gemini
    key, lab, txt = chunk
    n = V.norma(key)
    prev = [e["_main"][:110] for e in existing if e["tema"] == tema][-25:]
    prompt = f"""Eres el EDITOR TÉCNICO de UDA · Unión de Arquitectos (estudio online que hace de departamento técnico externo
para despachos de arquitectura). Preparas piezas para reels y carruseles de Instagram, TikTok y LinkedIn.
{AUD}
{GUIA[b]}

FUENTE: {n.get('titulo')}{(' · nota: ' + n['nota']) if n.get('nota') else ''}
FRAGMENTO ({lab}):
\"\"\"
{txt[:6000]}
\"\"\"

Escribe {PIDE[b]}, sacadas EXCLUSIVAMENTE de este fragmento. Reglas:
- Nada que no diga el fragmento: ni artículos, ni apartados, ni cifras, ni excepciones, ni ejemplos inventados.
- "cita"/"citas": fragmentos COPIADOS LITERALMENTE del texto (10-40 palabras cada uno, sin cambiar ni una palabra).
- "referencia": norma y artículo/sección/apartado exactos según el fragmento (p. ej. "{n.get('corto', 'CTE')}, art. 4").
- Que sirvan de verdad a un arquitecto (no obviedades ni definiciones de diccionario). Si el fragmento no da para una
  pieza buena (índices, firmas, derogaciones), devuelve menos piezas o ninguna.
- No repitas estas ideas ya publicadas: {'; '.join(prev) or 'ninguna'}.
- Solo lo que se lee: nada de indicaciones de tono ni de diseño.
Devuelve JSON exactamente con esta forma:
{SCHEMA}"""
    res = gemini.ask(prompt, 0.6)
    return res.get("piezas") or []


def run(calls=14, seed=None):
    rng = random.Random(seed or str(datetime.datetime.utcnow()))
    st = state()
    bank = QB.load()
    existing = [{**p, "_main": (p.get("pregunta", "") + " " + (p["opciones"][p["correcta"]] if p.get("opciones") else "")
                                if p["tipo"] == "test" else QB.text_of(p))} for p in bank]
    ids = {p["id"] for p in bank}
    added, rejected = [], {}
    for k in range(calls):
        ch = choose(st, rng)
        if not ch:
            print("generador: no quedan fragmentos nuevos en ninguna fuente", flush=True); break
        b, tema, chunk = ch
        try:
            raws = generate_one(b, tema, chunk, existing)
        except Exception as e:
            print(f"generador: llamada fallida ({str(e)[:150]})", flush=True); continue
        new = 0
        for raw in raws if isinstance(raws, list) else []:
            if not isinstance(raw, dict):
                continue
            p, why = clean(raw, tema, b, *chunk, existing)
            if p is None or p["id"] in ids:
                rejected[why if p is None else "repetida"] = rejected.get(why if p is None else "repetida", 0) + 1
                continue
            ids.add(p["id"]); existing.append(p); added.append(p); new += 1
        h = chash(*chunk)
        st["chunks"][h] = {"tema": tema, "fuente": chunk[1][:80], "fecha": str(datetime.date.today()),
                           "veces": st["chunks"].get(h, {}).get("veces", 0) + 1}
        st["temas"][tema] = str(datetime.datetime.utcnow())
        print(f"generador: [{b}] {QB.tema_titulo(tema)} · {chunk[1][:60]} -> {new} piezas", flush=True)
    for p in added:
        p.pop("_main", None)
    QB.save(bank + added)
    json.dump(st, open(GEN, "w"), ensure_ascii=False, indent=0)
    by = {}
    for p in added:
        by[f"{p['bloque']}/{p['tipo']}"] = by.get(f"{p['bloque']}/{p['tipo']}", 0) + 1
    msg = (f"generador: {len(added)} piezas nuevas ({', '.join(f'{k} {v}' for k, v in sorted(by.items())) or '-'}); "
           f"descartadas: {sum(rejected.values())} {rejected or ''}")
    print(msg, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(f"## Generar banco\n\n- {msg}\n")
    return added


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Falta GEMINI_API_KEY")
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 14)
