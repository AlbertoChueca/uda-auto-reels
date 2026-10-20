"""Banco de piezas de UDA: elegir la(s) pieza(s) de cada reel sin repetir, solo entre las verificadas.

Una "pieza" es una unidad de contenido sacada de una fuente (fuentes/): BOE (CTE, LOE, RD 390/2021, RD 1627/1997,
RD 105/2008, TRLSRU, LPH) o los documentos y la web de UDA. Tipos:
  test    pregunta tipo test (4 opciones, una correcta) + explicación
  puntos  título + 3 ideas clave (checklist de proyecto, productividad del despacho, servicios de UDA)
  ficha   pregunta corta -> respuesta corta (repaso exprés)
Bloques: normativa · proyecto (consejos de proyecto) · productividad (escalar el despacho, delegar) · servicios (UDA).

Reglas (igual que en TCAE, más estrictas):
- Toda pieza lleva una CITA LITERAL de su fuente y el código comprueba que esa cita existe de verdad en el texto
  descargado (verifier.quote_in). Sin cita comprobada no se publica nunca, sea normativa o un dato de UDA.
- Además, el verificador (modelo "pro", temperatura baja) la revisa contra el texto de la fuente: solo las "ok" salen.
- Nunca se repite una pieza hasta agotar las elegibles; se evita repetir tema en los últimos reels.
- Las opciones de los test se barajan (salvo "todas/ninguna/A y B...") para que la correcta no sea siempre la misma.
"""
import datetime, hashlib, json, os, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "banco", "piezas.json")
VERIF = os.path.join(HERE, "banco", "verificacion.json")
USED = os.path.join(HERE, "used.json")
LETTERS = "ABCD"
BLOQUES = ("normativa", "proyecto", "productividad", "servicios")
LIMITS = {"normal": (170, 80), "corta": (115, 58)}
NO_SHUFFLE = re.compile(r"\b(todas|ninguna|ambas|anteriores|las dos|son correctas|son ciertas|a y b|b y c|a y c|a, b|"
                        r"opciones? [abcd]\b|respuestas? [abcd]\b)", re.I)

# formato -> (tipo de pieza, bloques que admite)
FORMAT_SPEC = {
    "test_normativa": ("test", ("normativa", "proyecto")),
    "error_tipico": ("test", ("normativa", "proyecto")),
    "mito_realidad": ("test", ("normativa", "proyecto", "productividad", "servicios")),
    "norma_30s": ("test", ("normativa",)),
    "simulacro_3": ("test", ("normativa", "proyecto")),
    "caso_despacho": ("test", ("proyecto", "normativa")),
    "checklist": ("puntos", ("proyecto",)),
    "delegar": ("puntos", ("productividad",)),
    "uda_servicio": ("puntos", ("servicios",)),
    "repaso_express": ("ficha", ("normativa", "proyecto")),
}
POINTS_ONLY = {"checklist", "delegar", "uda_servicio"}            # sin pregunta: hook -> 3 claves -> cierre


def pid(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def load():
    try:
        return json.load(open(BANK))
    except Exception:
        return []


def save(ps):
    os.makedirs(os.path.dirname(BANK), exist_ok=True)
    json.dump(ps, open(BANK, "w"), ensure_ascii=False, indent=0)


def cfg():
    return json.load(open(os.path.join(HERE, "fuentes", "fuentes.json")))


def tema_titulo(tema):
    return (cfg()["temas"].get(tema) or {}).get("titulo", tema)


def tema_corto(tema):
    return (cfg()["temas"].get(tema) or {}).get("corto", tema)


def verif():
    try:
        return json.load(open(VERIF))
    except Exception:
        return {}


def save_verif(v):
    os.makedirs(os.path.dirname(VERIF), exist_ok=True)
    json.dump(v, open(VERIF, "w"), ensure_ascii=False, indent=0)


def used():
    try:
        return json.load(open(USED))
    except Exception:
        return []


def mark_used(ps, fmt):
    u = used()
    for p in ps:
        u.append({"id": p["id"], "tema": p.get("tema"), "fecha": str(datetime.date.today()), "formato": fmt})
    json.dump(u, open(USED, "w"), indent=0)


def text_of(p):
    """Todo el texto visible de una pieza (para buscar fuentes y comparar)."""
    if p["tipo"] == "test":
        return " ".join([p["pregunta"]] + p["opciones"] + [p.get("explicacion", "")])
    if p["tipo"] == "puntos":
        return " ".join([p["titulo"]] + p["puntos"])
    return p["q"] + " " + p["a"]


def fits(p, kind="normal"):
    if p["tipo"] != "test":
        if p["tipo"] == "puntos":
            return all(4 <= len(x.split()) <= 18 for x in p["puntos"]) and len(p["titulo"]) <= 60
        return 10 <= len(p["q"]) <= 110 and 3 <= len(p["a"]) <= 160
    ql, ol = LIMITS[kind]
    return len(p["pregunta"]) <= ql and all(len(o) <= ol for o in p["opciones"])


def publishable(p, v=None):
    v = verif() if v is None else v
    r = v.get(p["id"])
    return bool(r and r.get("veredicto") == "ok" and r.get("fuente_ok") and p.get("fuente_ok"))


def candidates(fmt, bloque=None, seed=0):
    """Piezas que encajan con el formato (tipo, bloque, longitud), sin usar todavía y mezcladas con la semilla."""
    tipo, bloques = FORMAT_SPEC[fmt]
    kind = "corta" if fmt == "simulacro_3" else "normal"
    ps = [p for p in load() if p["tipo"] == tipo and p.get("bloque") in bloques and fits(p, kind)]
    if bloque and bloque != "mixto" and bloque in bloques:
        ps = [p for p in ps if p["bloque"] == bloque] or ps
    if fmt == "error_tipico":                                     # necesita una explicación con contenido
        ps = [p for p in ps if len(p.get("explicacion", "").split()) >= 8] or ps
    u = used()
    done = {x["id"] for x in u}
    fresh = [p for p in ps if p["id"] not in done] or ps          # banco agotado para este formato: vuelve a empezar
    recent = {x.get("tema") for x in u[-6:]}
    rng = random.Random(seed)
    rng.shuffle(fresh)
    fresh.sort(key=lambda p: p.get("tema") in recent)             # temas recientes al final
    return fresh


def pick(fmt, bloque=None, seed=0, n=1, verify=None, max_checks=32):
    """Devuelve n piezas publicables (temas distintos). Las aún no verificadas se verifican aquí (en lotes)."""
    cands = candidates(fmt, bloque, seed)
    out, temas, errs = [], set(), []
    v = verif()
    for p in cands:
        if publishable(p, v) and p.get("tema") not in temas:
            out.append(p); temas.add(p.get("tema"))
        if len(out) == n:
            return out
    if verify:
        pending = [p for p in cands if p["id"] not in v and p.get("fuente_ok")][:max_checks]
        for k in range(0, len(pending), 8):
            try:
                verify(pending[k:k + 8])
            except Exception as e:
                errs.append(str(e)[:160]); print("verificador: lote fallido:", str(e)[:200], flush=True)
                if len(errs) >= 2:
                    break
            v = verif()
            for p in pending[k:k + 8]:
                if publishable(p, v) and p.get("tema") not in temas:
                    out.append(p); temas.add(p.get("tema"))
                if len(out) == n:
                    return out
    if bloque and bloque != "mixto":                              # el bloque del experimento no tiene piezas listas
        return pick(fmt, None, seed, n, verify, max_checks)
    tally = {}
    for p in cands:
        r = v.get(p["id"]); k = r.get("veredicto") if r else "sin verificar"
        tally[k] = tally.get(k, 0) + 1
    raise LookupError(f"no hay suficientes piezas verificadas para '{fmt}' ({len(out)}/{n}); candidatas {tally or 0}"
                      + (f"; errores del verificador: {' | '.join(errs)}" if errs else "")
                      + ("" if verify else "; el verificador no está activo (¿falta GEMINI_API_KEY?)")
                      + ". Ejecuta 'Generar banco' y 'Verificar banco'")


def prepare(p, seed=0):
    """Pieza lista para el vídeo. En los test: opciones (quizá barajadas) con letra y letra correcta."""
    if p["tipo"] != "test":
        return dict(p)
    idx = list(range(4))
    if not any(NO_SHUFFLE.search(o) for o in p["opciones"]):
        random.Random(f"{p['id']}-{seed}").shuffle(idx)
    opts = [p["opciones"][i] for i in idx]
    c = idx.index(p["correcta"])
    return {**p, "op": opts, "ok": c, "letra": LETTERS[c], "orden": idx}


def pick_fichas(seed=0, n=4, verify=None, max_temas=4):
    """4 fichas verificadas del MISMO tema (repaso exprés)."""
    ps = [p for p in load() if p["tipo"] == "ficha" and fits(p)]
    u = used(); done = {x["id"] for x in u}; recent = {x.get("tema") for x in u[-8:]}
    by = {}
    for p in ps:
        by.setdefault(p["tema"], []).append(p)
    groups = [(t, [p for p in fs if p["id"] not in done] or fs) for t, fs in by.items()]
    rng = random.Random(seed); rng.shuffle(groups); groups.sort(key=lambda g: g[0] in recent)
    for tema, fs in groups[:max_temas]:
        v = verif()
        good = [p for p in fs if publishable(p, v)]
        if len(good) < n and verify:
            pend = [p for p in fs if p["id"] not in v and p.get("fuente_ok")][:12]
            if pend:
                try:
                    verify(pend)
                except Exception as e:
                    print("verificador de fichas: lote fallido:", str(e)[:200], flush=True)
                v = verif(); good = [p for p in fs if publishable(p, v)]
        if len(good) >= n:
            rng.shuffle(good)
            return good[:n]
    raise LookupError("no hay 4 fichas verificadas del mismo tema; ejecuta 'Generar banco' y 'Verificar banco'")


def stock():
    """{bloque: piezas publicables sin usar} y {bloque: pendientes de verificar}."""
    v = verif(); done = {x["id"] for x in used()}
    pub, pend = {b: 0 for b in BLOQUES}, {b: 0 for b in BLOQUES}
    for p in load():
        b = p.get("bloque")
        if b not in pub:
            continue
        if publishable(p, v) and p["id"] not in done:
            pub[b] += 1
        elif p["id"] not in v and p.get("fuente_ok"):
            pend[b] += 1
    return pub, pend
