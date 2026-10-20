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
TARGET = {"negocio": 45, "contratar": 30, "servicios": 40, "proyecto": 40}          # reserva deseada (sin usar)
PIDE = {"negocio": "1 de tipo puntos, 1 de tipo dato y 1 de tipo mito",
        "contratar": "1 de tipo comparativa (columnas \"Contratar en plantilla\" y \"Contratar por servicios\"), 1 de tipo puntos y 1 de tipo mito",
        "servicios": "1 de tipo comparativa (columnas \"En tu despacho\" y \"Delegado en UDA\"), 1 de tipo puntos y 1 de tipo dato",
        "proyecto": "2 de tipo dato y 1 de tipo puntos"}
GUIA = {
    "negocio": "NEGOCIO DEL DESPACHO: cómo facturar más delegando, cómo mejorar el precio por hora del despacho, cómo ganar "
               "capacidad para aceptar más encargos sin ampliar plantilla, dónde se va el tiempo del arquitecto (revisar, "
               "formar, supervisar) frente a lo que se cobra mejor (proyectar, cliente, dirección). Se permiten conclusiones "
               "y consejos razonados a partir del texto, pero toda cifra tiene que estar en el texto tal cual.",
    "contratar": "CONTRATAR EN PLANTILLA O POR SERVICIOS: qué implica contratar a alguien indefinidamente (contrato, coste "
                 "haya proyectos o no, formación, vacaciones, bajas, extinción) frente a contratar un servicio cerrado por "
                 "proyecto. Con el Estatuto de los Trabajadores solo datos literales de la ley, sin asesoramiento laboral "
                 "concreto; con los textos de UDA, sus datos tal cual.",
    "servicios": "SERVICIOS DE UDA: cada tarea que UDA hace por el despacho (planimetría, memoria y CTE, instalaciones, "
                 "estructuras con CYPE, mediciones, pliego, estudio de seguridad y salud, gestión de residuos, modelo Revit, "
                 "actuaciones específicas...) y qué implicaría hacerla con equipo propio. Un precio SIEMPRE como \"precio de "
                 "referencia\" (el definitivo es el presupuesto cerrado). La firma corresponde siempre al despacho.",
    "proyecto": "DATOS DE PROYECTO QUE POCOS CONOCEN: lo que exige la norma que contenga un Proyecto Básico o de Ejecución, "
                "qué documentos son obligatorios y cuándo, quién responde de qué, qué cambia en edificios grandes o de uso "
                "residencial colectivo. Un dato sorprendente pero exacto, útil para un despacho que hace bloques.",
}
AUD = ("Público: fundadores y socios de despachos de arquitectura y arquitectos autónomos de España que proyectan bloques "
       "de viviendas, promociones y edificios de envergadura. Son expertos con más encargos que horas: quieren facturar más, "
       "mejorar su precio por hora y dedicar su tiempo a proyectar y a sus clientes. Nivel PREMIUM y elegante: nada de "
       "obviedades ni definiciones de manual. Español de España, tuteo, de colega a colega; sin promesas ni estadísticas.")
SCHEMA = """{"piezas": [
 {"tipo": "puntos", "titulo": str (2-7 palabras, con gancho), "puntos": [str, str, str] (6-15 palabras cada uno), "citas": [str, ...] (1-3 citas literales que respaldan los puntos), "referencia": str},
 {"tipo": "comparativa", "titulo": str (2-7 palabras), "col_a": str (1-4 palabras), "col_b": str (1-4 palabras), "filas": [{"aspecto": str (1-4 palabras), "a": str (2-10 palabras), "b": str (2-10 palabras)}, x3], "citas": [str, ...] (1-3 citas literales), "referencia": str},
 {"tipo": "dato", "afirmacion": str (8-24 palabras: el dato, claro y sorprendente), "explicacion": str (15-38 palabras: por qué le importa a un despacho), "cita": str, "referencia": str},
 {"tipo": "mito", "afirmacion": str (8-22 palabras: una creencia habitual en los despachos), "veredicto": "MITO"|"REALIDAD", "explicacion": str (15-38 palabras: lo que dice de verdad la fuente), "cita": str, "referencia": str}
]}"""
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
    if t == "comparativa":
        filas = [{"aspecto": sp(f.get("aspecto")), "a": sp(f.get("a")), "b": sp(f.get("b"))} for f in (raw.get("filas") or [])[:3]]
        citas = [sp(x) for x in (raw.get("citas") or [])][:3]
        if (len(filas) != 3 or not all(1 <= W(f["aspecto"]) <= 5 and 1 <= W(f["a"]) <= 12 and 1 <= W(f["b"]) <= 12 for f in filas)
                or not 1 <= W(raw.get("col_a")) <= 5 or not 1 <= W(raw.get("col_b")) <= 5 or not citas):
            return None, "comparativa no válida"
        p.update(titulo=sp(raw.get("titulo")), col_a=sp(raw.get("col_a")), col_b=sp(raw.get("col_b")), filas=filas,
                 cita=citas[0], citas_extra=citas[1:])
        claims = " ".join([p["titulo"]] + [f"{f['aspecto']} {f['a']} {f['b']}" for f in filas])
        main = claims
    elif t in ("dato", "mito"):
        p.update(afirmacion=sp(raw.get("afirmacion")), explicacion=sp(raw.get("explicacion")), cita=sp(raw.get("cita")))
        if t == "mito":
            p["veredicto"] = sp(raw.get("veredicto")).upper()
            if p["veredicto"] not in ("MITO", "REALIDAD"):
                return None, "veredicto no válido"
        if not 6 <= W(p["afirmacion"]) <= 26 or not 10 <= W(p["explicacion"]) <= 44:
            return None, "longitudes"
        claims = p["explicacion"] + (" " + p["afirmacion"] if t == "dato" or p.get("veredicto") == "REALIDAD" else "")
        main = p["afirmacion"]
        citas = [p["cita"]]
    elif t == "test":
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


def choose(st, rng, extra=None):
    """(bloque, tema, (norma, etiqueta, texto)) con más necesidad. extra = piezas ya creadas en esta ejecución."""
    pub, pend = QB.stock()
    extra = extra or {}
    only = [b for b in os.environ.get("BLOQUES", "").split(",") if b in QB.BLOQUES] or list(QB.BLOQUES)
    need = sorted(only, key=lambda b: (pub[b] + pend[b] + extra.get(b, 0)) / TARGET[b])
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
        hechas = {}
        for p in added:
            hechas[p["bloque"]] = hechas.get(p["bloque"], 0) + 1
        ch = choose(st, rng, hechas)
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
