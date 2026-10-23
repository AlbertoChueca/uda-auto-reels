"""Amplía solo el banco de interacción cuando se ha usado el 80 % de un tipo (tests, verdadero o falso, encuestas,
atajos y curiosidades). Lo lanza el workflow diario después de publicar; si no hace falta, no hace nada.

    python ampliar_banco.py            # amplía lo que pase del 80 %
    python ampliar_banco.py --estado   # solo muestra el uso de cada tipo
    python ampliar_banco.py --forzar test   # amplía ese tipo aunque no llegue al 80 % (pruebas)

Cómo se asegura de que no entra nada falso ni feo:
  1. Un agente (Gemini) propone piezas nuevas, distintas de las que ya hay, para arquitectos autónomos y fundadores de
     despacho: cultura de arquitectura, obras, arquitectos, construcción general, BIM y software. Nunca normativa
     (BOE, CTE, decretos), nunca cifras inventadas ni nada sobre UDA.
  2. Un segundo agente, independiente y con búsqueda en Google, comprueba cada pieza una a una: la respuesta es
     correcta y es la ÚNICA correcta, el dato es cierto y la fuente lo respalda. Solo entra lo que sale «ok».
  3. Controles automáticos: longitudes, 4 opciones distintas, sin duplicados (ni parecidos) con el banco, sin palabras
     prohibidas y que la escena quepa en la zona segura del vídeo (se renderiza de verdad).
  4. Las piezas nuevas se AÑADEN al final (las antiguas conservan su identificador y su historial de uso).
El «puente» de las curiosidades (la frase que enlaza con UDA) no lo escribe la IA: se elige entre los ya aprobados.
"""
import datetime, difflib, json, os, random, re, sys

import tematicas

HERE = os.path.dirname(os.path.abspath(__file__))
F_INT = os.path.join(HERE, "fuentes", "interaccion.json")
F_CUR = os.path.join(HERE, "fuentes", "curiosidades.json")
UMBRAL = float(os.environ.get("AMPLIAR_UMBRAL", "0.8"))
CUANTOS = {"tests": 20, "vf": 10, "encuestas": 8, "atajos": 4, "curiosidades": 6}
VARIANTE = {"tests": "test", "vf": "vf", "encuestas": "encuesta", "atajos": "atajos"}
PROHIBIDO = re.compile(r"\b(CTE|BOE|C[óo]digo T[ée]cnico|real decreto|decreto|DB[- ]?(SI|SUA|HE|HS|HR|SE)|UDA|"
                       r"Uni[óo]n de Arquitectos)\b", re.I)
PUBLICO = ("arquitectos autónomos y fundadores de despachos de arquitectura en España (45-55 años, Campo Baeza y Moneo "
           "como referentes, trabajan en AutoCAD, Revit o ArchiCAD)")


def norm(t):
    return re.sub(r"[^a-z0-9áéíóúñü ]", "", (t or "").lower()).strip()


def parecido(t, existentes):
    n = norm(t)
    return any(difflib.SequenceMatcher(None, n, norm(e)).ratio() > 0.78 for e in existentes)


# ------------------------------------------------------------------ uso del banco
def _used_ids():
    try:
        return {x["id"] for x in json.load(open(os.path.join(HERE, "used.json")))}
    except Exception:
        return set()


def estado():
    usados = _used_ids()
    piezas = tematicas.interaccion()
    out = {}
    for tipo, var in VARIANTE.items():
        ids = [p["id"] for p in piezas if p["infografia"]["variante"] == var]
        out[tipo] = (sum(i in usados for i in ids), len(ids))
    curs = json.load(open(F_CUR))["items"]
    out["curiosidades"] = (sum(c["id"] in usados for c in curs), len(curs))
    return out


# ------------------------------------------------------------------ agentes
def _gen(tipo, banco, n):
    import gemini
    ejemplos = {"tests": banco["tests"][:3], "vf": banco["vf"][:3], "encuestas": banco["encuestas"][:3],
                "atajos": banco["atajos"][:1], "curiosidades": banco["_cur"][:2]}[tipo]
    ya = {"tests": [q["pregunta"] for q in banco["tests"]], "vf": [q["afirmacion"] for q in banco["vf"]],
          "encuestas": [q["pregunta"] for q in banco["encuestas"]], "atajos": [a["titulo"] for a in banco["atajos"]],
          "curiosidades": [c["screen_hook"] for c in banco["_cur"]]}[tipo]
    formato = {
        "tests": '{"pregunta": str (máx. 80 caracteres), "opciones": [4 str, máx. 40 caracteres cada una], "correcta": 0-3, '
                 '"explicacion": str (máx. 110 caracteres, empieza por la respuesta), "fuente": "dominio/ruta de la fuente"}. '
                 'Reparte la respuesta correcta entre A, B, C y D. Distractores verosímiles pero claramente falsos.',
        "vf": '{"afirmacion": str (máx. 90 caracteres), "verdadero": bool, "explicacion": "Verdadero. ..." o "Falso. ..." '
              '(máx. 110 caracteres), "fuente": str}. Mitad verdaderas y mitad falsas; las falsas, creíbles.',
        "encuestas": '{"pregunta": str (máx. 70 caracteres), "opciones": [4 str, máx. 28 caracteres]}. Sin respuesta '
                     'correcta: sobre cómo trabaja su estudio (horas, encargos, clientes, software, equipo, plazos, '
                     'honorarios, desconexión). Que den ganas de contestar con una letra.',
        "atajos": '{"titulo": str (máx. 45 caracteres), "programa": "autocad" o "revit", "items": [4 x [icono, comando, '
                  'descripción]] con icono en plan/doc/shield, comando corto (máx. 12 caracteres; en AutoCAD el comando '
                  'en inglés y el alias en la descripción: ["plan", "OFFSET", "O · desfase"]), descripción máx. 30 '
                  'caracteres, "voz": [6 frases: el título, una por comando («Offset: desfase.»), y «Guárdalo para tu '
                  'próximo plano.» o «Guárdalo para tu próximo modelo.»], "fuente": str}. Solo comandos y alias POR '
                  'DEFECTO de la versión en inglés.',
        "curiosidades": '{"id": slug, "screen_hook": str (máx. 38 caracteres), "hook_line": pregunta hablada (máx. 110 '
                        'caracteres), "beats": [3 frases de máx. 110 caracteres, cada una con un dato comprobable], '
                        '"fuente": "Nombre · dominio/ruta", "render": [3 descripciones de un render ORIGINAL de '
                        'arquitectura, elegante, que NO reproduzca ningún edificio real reconocible]}. Sobre premios, '
                        'arquitectos, estudios, escuelas, tratados y el oficio (no sobre un edificio concreto que el render '
                        'no puede enseñar).',
    }[tipo]
    out = gemini.ask(f"""Eres el editor de contenido de una cuenta de Instagram y TikTok para {PUBLICO}.
Escribe {n + 4} piezas NUEVAS de tipo «{tipo}» para que comenten, guarden y compartan. Cultura de arquitectura,
arquitectos y obras (también de España), construcción en general, BIM y software. Datos muy conocidos y comprobables en
una fuente seria (Wikipedia, web oficial del premio, del museo o del fabricante del software).
PROHIBIDO: normativa (BOE, CTE, decretos, documentos básicos), cifras que no puedas comprobar, temas polémicos, y
cualquier mención a UDA. Español de España, frases cortas, nada de tecnicismos innecesarios.
No repitas ni parafrasees estas que ya tenemos: {json.dumps(ya, ensure_ascii=False)}
Formato de cada pieza: {formato}
Ejemplos de nuestro estilo: {json.dumps(ejemplos, ensure_ascii=False)}
Devuelve JSON: {{"piezas": [...]}}""", 0.8)
    return out.get("piezas") or []


def _grounded(prompt):
    """Gemini con búsqueda en Google (para comprobar datos). Devuelve el JSON del texto de la respuesta."""
    import gemini
    body = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.1}}
    last = None
    for model in dict.fromkeys(gemini.VERIFY_MODELS + sorted([m for m in gemini.available() if "pro" in m
                                                              and gemini._text_only(m)], key=gemini._rank)[:2]
                               + gemini.TEXT_MODELS):
        try:
            j = gemini.post(model, body)
            txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0))
        except Exception as e:
            last = e
    raise last or RuntimeError("verificador sin modelo")


def _verifica(tipo, p):
    if tipo == "encuestas":
        return True, "encuesta: sin datos que comprobar"
    try:
        r = _grounded(f"""Eres un verificador de datos MUY estricto para una cuenta de arquitectura. Busca en Google y
comprueba esta pieza de tipo «{tipo}»:
{json.dumps(p, ensure_ascii=False)}
Reglas: "ok" solo si TODO lo que afirma es cierto según fuentes serias que hayas encontrado; en un test, la respuesta
marcada es correcta y es la ÚNICA correcta (ninguna otra opción podría defenderse) y la pregunta no es ambigua; en
verdadero o falso, el veredicto es el correcto; en atajos, cada comando o alias es el que trae el programa por defecto
y hace lo que dice; en curiosidades, cada frase es exacta (fechas, nombres, cifras). Ante la menor duda: "dudosa".
Devuelve SOLO JSON: {{"veredicto": "ok" | "dudosa" | "error", "motivo": str, "fuente": "url que lo confirma"}}""")
    except Exception as e:
        try:                                                   # sin búsqueda: verificador cuidadoso normal
            import gemini
            r = gemini.ask(f"""Verificador MUY estricto de datos de arquitectura. Pieza «{tipo}»:
{json.dumps(p, ensure_ascii=False)}
"ok" solo si estás completamente seguro de que todo es cierto y, si es un test, la respuesta es la única correcta.
Ante la menor duda, "dudosa". JSON: {{"veredicto": "ok"|"dudosa"|"error", "motivo": str}}""", 0.1, careful=True)
        except Exception as e2:
            return False, f"verificador no disponible: {e2}"
    return r.get("veredicto") == "ok", r.get("motivo", "")


# ------------------------------------------------------------------ controles automáticos
def _forma(tipo, p, banco):
    try:
        if tipo == "tests":
            ops = p["opciones"]
            assert len(ops) == 4 and len({norm(o) for o in ops}) == 4 and 0 <= int(p["correcta"]) <= 3
            assert len(p["pregunta"]) <= 90 and all(len(o) <= 48 for o in ops) and len(p["explicacion"]) <= 130
            assert not parecido(p["pregunta"], [q["pregunta"] for q in banco["tests"]])
            texto = p["pregunta"] + " ".join(ops) + p["explicacion"]
        elif tipo == "vf":
            assert isinstance(p["verdadero"], bool) and len(p["afirmacion"]) <= 100 and len(p["explicacion"]) <= 130
            assert p["explicacion"].startswith("Verdadero." if p["verdadero"] else "Falso.")
            assert not parecido(p["afirmacion"], [q["afirmacion"] for q in banco["vf"]])
            texto = p["afirmacion"] + p["explicacion"]
        elif tipo == "encuestas":
            ops = p["opciones"]
            assert len(ops) == 4 and len({norm(o) for o in ops}) == 4 and len(p["pregunta"]) <= 80
            assert all(len(o) <= 32 for o in ops)
            assert not parecido(p["pregunta"], [q["pregunta"] for q in banco["encuestas"]])
            texto = p["pregunta"] + " ".join(ops)
        elif tipo == "atajos":
            assert p["programa"] in ("autocad", "revit") and len(p["items"]) == 4 and len(p["voz"]) == 6
            assert all(len(i) == 3 and i[0] in ("plan", "doc", "shield") and len(i[1]) <= 14 and len(i[2]) <= 34
                       for i in p["items"])
            assert p["voz"][-1] in ("Guárdalo para tu próximo plano.", "Guárdalo para tu próximo modelo.")
            assert not parecido(p["titulo"], [a["titulo"] for a in banco["atajos"]])
            texto = p["titulo"] + json.dumps(p["items"], ensure_ascii=False)
        else:
            assert len(p["beats"]) == 3 and len(p["render"]) == 3 and len(p["screen_hook"]) <= 40
            assert all(len(b) <= 120 for b in p["beats"]) and len(p["hook_line"]) <= 120
            assert not parecido(p["screen_hook"], [c["screen_hook"] for c in banco["_cur"]])
            assert p["id"] not in {c["id"] for c in banco["_cur"]}
            texto = " ".join(p["beats"]) + p["hook_line"]
        assert not PROHIBIDO.search(texto)
        return True
    except Exception:
        return False


def _cabe(tipo, p):
    """Renderiza la escena de verdad y comprueba que cabe en la zona segura (como el resto del banco)."""
    if tipo == "curiosidades":
        return True
    import infoviz, themes
    T = themes.get("negro")
    tmp = {"tests": [], "vf": [], "encuestas": [], "atajos": [], **{tipo: [p]}}
    orig = json.load(open(F_INT))
    try:
        json.dump({**orig, **tmp}, open(F_INT, "w"), ensure_ascii=False)
        piezas = tematicas.interaccion()
    finally:
        json.dump(orig, open(F_INT, "w"), ensure_ascii=False, indent=1)
    for pz in piezas:
        ig = pz["infografia"]
        for sc in ig["orden"]:
            sg = {"starts": [0, 0.2, 0.4, 0.6, 0.8, 1.0][:len(ig["voz"][sc])], "a": 0, "b": 10}
            bb = infoviz.render(T, sc, ig["datos"][sc], 9.0, sg).getchannel("A").getbbox()
            if bb and (bb[3] > 1480 or bb[1] < 395):
                return False
    return True


# ------------------------------------------------------------------ ampliar
def ampliar(tipo, banco):
    n = CUANTOS[tipo]
    nuevas, motivos = [], []
    for ronda in range(2):                                    # si muchas no pasan, una segunda tanda
        if len(nuevas) >= n:
            break
        for p in _gen(tipo, banco, n - len(nuevas)):
            if len(nuevas) >= n:
                break
            clave = "_cur" if tipo == "curiosidades" else tipo
            if not _forma(tipo, p, {**banco, clave: banco[clave] + nuevas}):      # tampoco duplicados entre las nuevas
                motivos.append("forma"); continue
            ok, why = _verifica(tipo, p)
            if not ok:
                motivos.append(f"verificación: {why[:80]}"); continue
            if not _cabe(tipo, p):
                motivos.append("no cabe en pantalla"); continue
            p = dict(p, origen="ia-verificada", fecha=str(datetime.date.today()))
            if tipo == "curiosidades":
                p["badge"] = "CURIOSIDADES DE ARQUITECTURA"
                p["puente"] = random.choice(sorted({c["puente"] for c in banco["_cur"]}))   # puente ya aprobado
            nuevas.append(p)
    return nuevas, motivos


def main():
    args = sys.argv[1:]
    est = estado()
    for t, (u, n) in est.items():
        print(f"{t}: {u}/{n} usados ({u / max(1, n):.0%})", flush=True)
    if "--estado" in args:
        return
    forzar = args[args.index("--forzar") + 1] if "--forzar" in args else None
    toca = [t for t, (u, n) in est.items() if n and u / n >= UMBRAL] + ([forzar] if forzar else [])
    if not toca:
        print("banco: ningún tipo llega al 80 %; no hace falta ampliar", flush=True)
        return
    if not os.environ.get("GEMINI_API_KEY"):
        print("banco: hace falta ampliar", toca, "pero no hay GEMINI_API_KEY", flush=True)
        return
    banco = json.load(open(F_INT)); cur = json.load(open(F_CUR))
    banco["_cur"] = cur["items"]
    for t in dict.fromkeys(toca):
        try:
            nuevas, motivos = ampliar(t, banco)
        except Exception as e:
            print(f"banco: {t}: no se pudo ampliar: {str(e)[:200]}", flush=True); continue
        if t == "curiosidades":
            cur["items"] += nuevas; banco["_cur"] = cur["items"]
            json.dump(cur, open(F_CUR, "w"), ensure_ascii=False, indent=1)
        else:
            banco[t] += nuevas
            json.dump({k: v for k, v in banco.items() if k != "_cur"}, open(F_INT, "w"), ensure_ascii=False, indent=1)
        print(f"banco: {t}: +{len(nuevas)} piezas verificadas (descartadas: {len(motivos)}"
              + (f"; p. ej. {motivos[:3]}" if motivos else "") + ")", flush=True)


if __name__ == "__main__":
    main()
