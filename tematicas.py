"""Temáticas de los reels de UDA y su calendario semanal (3 reels al día, 21 a la semana): 80 % interacción, 20 % UDA.

TikTok e Instagram enseñan más lo que la gente comenta, guarda y comparte. Por eso 17 de los 21 reels semanales son
contenido para el arquitecto autónomo o el fundador de un despacho, aunque no hable de UDA:

    test         Test de arquitecto: pregunta con 4 opciones, cuenta atrás «Comenta tu respuesta» y solución   (6/semana)
    vf           ¿Verdadero o falso?: afirmación, «comenta», solución con explicación                          (3/semana)
    encuesta     Encuesta sin respuesta correcta («¿Cuántos proyectos llevas a la vez?»): pura conversación   (3/semana)
    atajos       Guárdalo: 4 comandos de AutoCAD o atajos de Revit                                          (2/semana)
    inspiracion  Renders de arquitectura + curiosidades comprobadas (formato «render»)                        (3/semana)

y 4 son de UDA (20 %), rotando entre: coste, contratar, partidas, actuaciones, revit y proceso.

Datos: fuentes/interaccion.json y fuentes/curiosidades.json (comprobados en su fuente, sin normativa), la Tabla de
presupuestos de UDA, assets/uda/hechos.md y testimonios literales de la web. Calendario y guiones: GUIONES.md.
"""
import hashlib, json, os

import casos

HERE = os.path.dirname(os.path.abspath(__file__))
INTERACCION = ["test", "vf", "encuesta", "atajos", "inspiracion"]
UDA = ["coste", "contratar", "partidas", "actuaciones", "revit", "proceso"]
VISUAL = ["portfolio", "antes_despues", "tips", "proceso_visual", "galeria", "obra"]   # visual.py (100 % del calendario)
TEMAS = INTERACCION + UDA + VISUAL
NOMBRE = {"test": "Test de arquitecto", "vf": "¿Verdadero o falso?", "encuesta": "Encuesta", "atajos": "Guárdalo: atajos",
          "inspiracion": "Renders y curiosidades",
          "coste": "UDA · Cuánto cuesta delegar", "contratar": "UDA · Contratar o delegar",
          "partidas": "UDA · Qué incluye cada partida", "actuaciones": "UDA · Encargos con precio cerrado",
          "revit": "UDA · CAD o Revit", "proceso": "UDA · Cómo trabajamos", "uda": "UDA (rota entre sus 6 temas)",
          "galeria": "Galería: «Interiores que pondría en mi casa»", "tips": "Tips visuales",
          "antes_despues": "Antes y después de una reforma", "proceso_visual": "Del boceto al render",
          "obra": "De la zanja a la llave", "portfolio": "Proyecto real de UDA (portafolio)"}
VARIANTE = {"coste": "caso", "contratar": "contratar", "proceso": "proceso"}       # nombre interno en casos.py
TEMA_DE_VARIANTE = {v: k for k, v in VARIANTE.items()}
SLOTS = {"manana": 0, "mediodia": 1, "tarde": 2}
# MENOS Y MEJOR: 2 reels al día (12:00 y 15:00; la mañana, apagada) y solo los formatos que funcionan.
# Proyecto real de UDA 4 veces por semana; antes/después 3, tips 3, boceto→render 2, galería de interiores 2.
PLAN = [[None, "portfolio", "antes_despues"], [None, "tips", "proceso_visual"], [None, "portfolio", "galeria"],
        [None, "antes_despues", "tips"], [None, "portfolio", "proceso_visual"], [None, "galeria", "antes_despues"],
        [None, "portfolio", "tips"]]
ROTACION = [t for t in VISUAL if t != "obra"]


def _ultimo(t, rec):
    return max([i for i, r in enumerate(rec) if r == t], default=-1)


def plan(fecha, slot):
    return PLAN[fecha.weekday()][SLOTS.get(slot, 0)]


def tema_de(fecha, slot, recientes=()):
    """La del calendario; si acaba de salir (lanzamientos manuales) o es manual, la visual que lleva más tiempo sin salir."""
    rec = [r for r in recientes if r]
    p = plan(fecha, slot) if slot in SLOTS else None
    if p == "uda":
        return min(UDA, key=lambda t: (_ultimo(t, rec), UDA.index(t)))
    if p and (not rec or p != rec[-1]):
        return p
    return min([t for t in ROTACION if not rec or t != rec[-1]], key=lambda t: (_ultimo(t, rec), ROTACION.index(t)))


def reserva(tema, recientes=(), n=2):
    """Si un reel no llega al 8: otros del mismo grupo (visual, interacción o UDA), los menos recientes."""
    rec = [r for r in recientes if r]
    grupo = VISUAL if tema in VISUAL else UDA if tema in UDA else [t for t in INTERACCION if t != "inspiracion"]
    otras = [t for t in grupo if t not in (tema, "inspiracion")]
    return sorted(otras, key=lambda t: _ultimo(t, rec))[:n]


def semana(lunes):
    import datetime
    return [[plan(lunes + datetime.timedelta(d), s) for s in SLOTS] for d in range(7)]


# ------------------------------------------------------------------ piezas comunes
NO_TUYO = ["El diseño", "La firma y el visado", "La dirección de obra"]
NO_TUYO_VOZ = "Sigue siendo tuyo: el diseño, la firma y el visado, y la dirección de obra."
_base = casos.infografia(casos.caso("unifamiliar", 150), "proceso", 0)
TIMELINE = _base["datos"]["timeline"]; TIMELINE_VOZ = _base["voz"]["timeline"]
QUOTE = {"texto": "Se me hacía duro contratar a alguien para 3 meses y tener que despedirle. UDA me ayuda mucho en el día a día.",
         "autor": "Estudio que colabora con UDA", "titulo": "Un estudio que ya delega"}


def _eur(x):
    return casos.eur(x)


def _pieza(tema, clave, k, badge, hooks, escenas, caption, grupo, pid_key=None):
    """Pieza de infografía con el mismo formato que las de casos.py (la usan el guionista, el montaje y la descripción)."""
    datos = {sc: d for sc, (d, v) in escenas.items()}
    voz = {sc: v for sc, (d, v) in escenas.items()}
    orden = list(escenas)
    j = k % len(hooks); hooks = hooks[j:] + hooks[:j]
    pid = hashlib.sha1(f"{tema}|{clave}|{k}|{pid_key or '/'.join(orden)}".encode()).hexdigest()[:10]
    ig = {"variante": tema, "badge": badge, "screen_hook": hooks[0][0], "hook_line": hooks[0][1], "hooks": hooks,
          "orden": orden, "datos": datos, "voz": voz, "caption": caption}
    torres = next((d for sc, d in datos.items() if sc.startswith("towers")), None)
    return {"id": pid, "tipo": "caso", "tema": "uda_casos", "bloque": "servicios", "norma": "uda_tabla", "calculado": True,
            "fuente_ok": True, "grupo": f"{tema}:{grupo}", "referencia": f"{casos.TABLA} · uniondearquitectos.com",
            "screen_hook": hooks[0][0], "escena": hooks[0][1], "titulo": (torres or {}).get("titulo", NOMBRE[tema]),
            "barras": (torres or {}).get("barras", []), "conclusion": (torres or {}).get("conclusion", ""),
            "puntos_titulo": "", "puntos": [], "infografia": ig}


def _rotar(opciones, k, n=3):
    """n escenas de la lista, empezando en k (cada pieza de un mismo grupo, con su propia combinación)."""
    return [opciones[(k + i) % len(opciones)] for i in range(min(n, len(opciones)))]


# ------------------------------------------------------------------ 3 · partidas (tabla, apartados 03, 06 y 09)
PARTIDAS = [  # (clave, fase, nombre, artículo + nombre, documentos incluidos (apartado 09))
    ("planimetria", "pb", "Planimetría", "los planos del Proyecto Básico",
     ["Situación y emplazamiento", "Plantas, alzados y secciones", "Acabados, superficies y cotas", "En Revit, modelo LOD 200"]),
    ("construccion", "pe", "Construcción", "la construcción del Proyecto de Ejecución",
     ["Sección constructiva", "Detalles a escala 1:20", "Acabados y superficies", "Carpinterías"]),
    ("instalaciones", "pe", "Instalaciones", "las instalaciones",
     ["Fontanería y saneamiento", "Electricidad y telecomunicaciones", "Climatización y ventilación", "Gas natural"]),
    ("estructuras", "pe", "Estructuras", "las estructuras",
     ["Cálculo con CYPE", "Planos de estructura", "Compatibilización con instalaciones"]),
    ("memoria", "pe", "Memoria", "la memoria del Proyecto de Ejecución",
     ["Memoria constructiva y estructural", "Justificación normativa completa", "Certificado energético justificativo"]),
    ("mediciones", "pe", "Mediciones", "las mediciones y anejos",
     ["Mediciones y presupuesto", "Pliego de condiciones", "Estudio de seguridad y salud", "Gestión de residuos"]),
]
TIPOS3 = [("unifamiliar", 150, "Vivienda 150 m²", "Vivienda de 150 metros"),
          ("industrial", 1500, "Nave 1.500 m²", "Nave de 1.500 metros"),
          ("equipamiento", 2000, "Equipam. 2.000 m²", "Equipamiento de 2.000 metros")]


def partidas():
    out = []
    for clave, f, nom, art, docs in PARTIDAS:
        vals = [casos.fase(t, f, m2, [clave]) for t, m2, _, _ in TIPOS3]       # con «Gestión y análisis», siempre incluida
        torres = {"titulo": f"{nom}: lo que cuesta delegarla", "conclusion": "Gestión y revisiones incluidas",
                  "barras": [{"etiqueta": lab, "valor": v, "texto": _eur(v)} for (_, _, lab, _), v in zip(TIPOS3, vals)]}
        torres_voz = [f"{vz}: {_eur(v)}." for (_, _, _, vz), v in zip(TIPOS3, vals)] + ["Gestión y revisiones incluidas."]
        deleg = {"titulo": f"Qué incluye {nom.lower()}", "si": docs, "no": NO_TUYO}
        deleg_voz = [f"{nom} incluye: " + ", ".join(d[0].lower() + d[1:] for d in docs[:-1]) + f" y {docs[-1][0].lower() + docs[-1][1:]}.",
                     NO_TUYO_VOZ]
        extra = [("timeline", (TIMELINE, TIMELINE_VOZ)), ("cargas_garantias", (casos.GARANTIAS, casos.GARANTIAS_VOZ)),
                 ("quote", (QUOTE, [QUOTE["texto"]]))]
        hooks = [(f"¿Cuánto cuesta delegar {nom.lower()}?", f"¿Cuánto cuesta delegar {art}? Te lo enseño con números."),
                 (f"{nom}: desde {_eur(min(vals))}", f"{nom} de una vivienda de 150 metros: {_eur(vals[0])}, gestión incluida."),
                 (f"Delega solo {nom.lower()}", f"No tienes que delegarlo todo. Puedes delegar solo {art}.")]
        cap = (f"{nom}: lo que cuesta delegarla (precios de referencia, gestión incluida):\n\n"
               + "\n".join(f"▪️ {lab}: {_eur(v)}" for (_, _, lab, _), v in zip(TIPOS3, vals))
               + f"\n\nIncluye:\n" + "\n".join(f"✔️ {d}" for d in docs)
               + "\n\nTú sigues firmando: el diseño, el visado y la dirección de obra son tuyos." + "\n\n📌 Guárdalo para cuando lo necesites.")
        for k in range(3):
            esc = dict([("delegable", (deleg, deleg_voz)), ("towers", (torres, torres_voz))][::1 if k % 2 == 0 else -1])
            esc.update([extra[k]])
            out.append(_pieza("partidas", clave, k, "QUÉ INCLUYE CADA PARTIDA", hooks, esc, cap, clave))
    return out


# ------------------------------------------------------------------ 4 · actuaciones con precio cerrado (apartado 08)
PAQUETE = {"titulo": "Qué incluye el paquete", "no": ["La firma", "La tramitación", "La dirección de obra"],
           "si": ["Estado actual y reformado", "Justificación normativa", "Memoria", "Mediciones y presupuesto"]}
PAQUETE_VOZ = ["El paquete incluye: estado actual y reformado, justificación normativa, memoria, y mediciones y presupuesto.",
               "Sigue siendo tuyo: la firma, la tramitación y la dirección de obra."]
MARGEN = {"titulo": "Encargos pequeños, sin perder horas", "pasos": [
    ("doc", "Nos pasas el encargo", "con el listado de documentos"),
    ("euro", "Precio cerrado", "por paquete, desde el principio"),
    ("plan", "Te lo documentamos", "estado actual, reformado y memoria"),
    ("shield", "Tú presupuestas y firmas", "y nuestro precio te deja margen")]}
MARGEN_VOZ = ["Nos pasas el encargo.", "Precio cerrado, por paquete.", "Te lo documentamos entero.",
              "Tú presupuestas y firmas, y nuestro precio te deja margen."]
ACTUACIONES = [
    ("locales", "Locales · precios desde", "Hasta 150 m²", "Precios hasta 150 metros cuadrados.",
     [("Licencia sin obra", 750, "750 €", "Licencia de actividad sin obra: desde 750 €."),
      ("Local inocuo", 1400, "1.400 €", "Adecuación de local para actividad inocua: desde 1.400 €."),
      ("Local clasificado", 2800, "2.800 €", "Para actividad clasificada: desde 2.800 €.")],
     [("¿Te piden una licencia de actividad?", "¿Un cliente te pide la licencia de un local? Mira lo que cuesta delegarla."),
      ("Locales: desde 750 €", "Licencias y adecuaciones de locales, con precio cerrado desde 750 euros."),
      ("Un local, documentado entero", "Un local para abrir un negocio: te lo documentamos entero, con precio cerrado.")]),
    ("edificios", "Edificios existentes · desde", "Documentación completa", "Con la documentación completa.",
     [("Cubierta", 1200, "1.200 €", "Rehabilitación de cubierta: desde 1.200 €."),
      ("Accesibilidad", 1400, "1.400 €", "Mejora de accesibilidad: 1.400 €."),
      ("Fachada", 1500, "1.500 €", "Rehabilitación de fachada: desde 1.500 €."),
      ("Ascensor, 5 paradas", 2150, "2.150 €", "Ascensor de cinco paradas en un edificio existente: 2.150 €.")],
     [("¿Un ascensor en un edificio existente?", "¿Te encargan un ascensor en un edificio existente? Precio cerrado, por paquete."),
      ("Fachadas y cubiertas, precio cerrado", "Fachadas, cubiertas, accesibilidad y ascensores. Con precio cerrado."),
      ("Rehabilitar sin parar el estudio", "Una rehabilitación no tiene por qué parar tu estudio. Mira lo que cuesta delegarla.")]),
    ("vivienda", "Encargos de vivienda · desde", "Tú presupuestas y firmas", "Tú presupuestas y firmas.",
     [("Legalización", 750, "750 €", "Legalización o estado actual: desde 750 €."),
      ("Demolición", 800, "800 €", "Demolición: desde 800 €."),
      ("Piscina", 950, "950 €", "Piscina privada exterior: 950 €."),
      ("Cambio de uso", 2400, "2.400 €", "Cambio de uso a vivienda: desde 2.400 €.")],
     [("Legalizar una vivienda: desde 750 €", "Legalizaciones, piscinas, cambios de uso. Encargos pequeños, precio cerrado."),
      ("Una piscina: 950 €", "Una piscina privada, documentada entera: 950 euros, precio cerrado."),
      ("¿Un cambio de uso a vivienda?", "¿Te piden pasar un local a vivienda? Esto cuesta delegarlo.")]),
    ("reforma", "Precios de referencia", "Precio definitivo, cerrado en 24 h", "El precio definitivo, cerrado en 24 horas.",
     [("Reforma 80 m²", 1950, "1.950 €", "Reforma integral de 80 metros, sin estructuras: 1.950 €."),
      ("Vivienda 150 m²", 2955, "2.955 €", "Vivienda nueva de 150 metros, básico y ejecución: 2.955 €.")],
     [("Reforma de 80 m²: 1.950 €", "Una reforma integral de 80 metros, documentada entera: 1.950 euros."),
      ("¿Reforma o vivienda nueva?", "¿Reforma o vivienda nueva? Esto cuesta delegar cada una."),
      ("Una reforma, sin parar tu estudio", "Te entra una reforma integral y vas a tope. Esto cuesta delegarla.")]),
]


def actuaciones():
    out = []
    for clave, tit, conc, conc_voz, barras, hooks in ACTUACIONES:
        torres = {"titulo": tit, "conclusion": conc,
                  "barras": [{"etiqueta": e, "valor": v, "texto": t} for e, v, t, _ in barras]}
        torres_voz = [vz for *_, vz in barras] + [conc_voz]
        cap = (f"{tit} (precios de referencia de UDA, precio cerrado por paquete):\n\n"
               + "\n".join(f"▪️ {e}: {t}" for e, _, t, _ in barras)
               + "\n\nIncluye estado actual y reformado, justificación normativa, memoria, mediciones y presupuesto. "
                 "Tú presupuestas, firmas y tramitas; nuestro precio te deja margen." + "\n\n📌 Guárdalo para cuando lo necesites.")
        extra = [("timeline", (MARGEN, MARGEN_VOZ)), ("cargas_garantias", (casos.GARANTIAS, casos.GARANTIAS_VOZ)),
                 ("timeline_pagos", (casos.PAGOS, casos.PAGOS_VOZ))]
        for k in range(3):
            esc = dict([("towers", (torres, torres_voz)), ("delegable", (PAQUETE, PAQUETE_VOZ))][::1 if k % 2 == 0 else -1])
            esc.update([extra[k]])
            out.append(_pieza("actuaciones", clave, k, "ENCARGOS CON PRECIO CERRADO", hooks, esc, cap, clave))
    return out


# ------------------------------------------------------------------ 5 · CAD o Revit (apartado 07)
REVIT_ESC = {
    "versus": ({"titulo": "Proyecto completo · vivienda 150 m²", "a_tit": "En CAD", "a_num": "2.955 €",
                "a_txt": "Básico y Ejecución", "b_tit": "En Revit", "b_num": "2.955 €", "b_txt": "el mismo precio"},
               ["En CAD: 2.955 €, básico y ejecución.", "En Revit: 2.955 €. El mismo precio."]),
    "cargas": ({"titulo": "En Revit cambia el reparto", "uda": "Completo: mismo precio", "tachar": False, "items": [
        ("plan", "Modelado +130%", "la base de todo el proyecto"),
        ("doc", "Mediciones −60%", "salen de las familias"),
        ("doc", "Memoria −25%", "cuadros y superficies del modelo"),
        ("shield", "Estructuras −20%", "el cálculo en CYPE, igual")]},
               ["En Revit cambia el reparto.", "Modelado: más 130 %.", "Mediciones: menos 60 %.", "Memoria: menos 25 %.",
                "Estructuras: menos 20 %.", "Proyecto completo: el mismo precio."]),
    "towers": ({"titulo": "Opcional en Revit · ejemplos", "conclusion": "Instalaciones en 3D, LOD 300–350",
                "barras": [{"etiqueta": "Plan BIM vivienda", "valor": 415, "texto": "415 €"},
                           {"etiqueta": "Plan BIM 32 viviendas", "valor": 900, "texto": "900 €"},
                           {"etiqueta": "3D vivienda 150 m²", "valor": 1950, "texto": "1.950 €"},
                           {"etiqueta": "3D 32 viviendas", "valor": 6500, "texto": "6.500 €"}]},
               ["Plan de Ejecución BIM de una vivienda: 415 €.", "De un bloque de 32 viviendas: 900 €.",
                "Instalaciones en 3D de una vivienda de 150 metros: 1.950 €.", "Del bloque de 32 viviendas: 6.500 €.",
                "Instalaciones en 3D, LOD 300 a 350."]),
    "delegable": ({"titulo": "Qué recibes en Revit", "no": NO_TUYO,
                   "si": ["Modelo LOD 300", "Familias con códigos de partida", "Mediciones a Presto (BC3)",
                          "IFC durante el trabajo y RVT al final"]},
                  ["Recibes el modelo LOD 300, las familias con códigos de partida, las mediciones a Presto, "
                   "y el IFC durante el trabajo y el RVT al final.", NO_TUYO_VOZ]),
}
REVIT_ORDEN = [["versus", "cargas", "delegable"], ["cargas", "towers", "versus"], ["delegable", "versus", "towers"],
               ["towers", "delegable", "cargas"]]
REVIT_HOOKS = [("CAD o Revit: mismo precio", "¿CAD o Revit? Si delegas el proyecto completo, pagas lo mismo."),
               ("Revit sin contratar a nadie", "¿Quieres el proyecto en Revit y no tienes a nadie que lo modele?"),
               ("El modelo es el proyecto", "En Revit, el modelo es el proyecto. Y las mediciones salen solas."),
               ("¿Tu estudio se pasa a Revit?", "¿Tu estudio quiere pasarse a Revit sin parar los proyectos?")]
REVIT_CAP = ("CAD o Revit: si nos encargas el proyecto completo, pagas lo mismo (vivienda de 150 m², Básico + Ejecución: "
             "2.955 €).\n\nEn Revit el modelo es el proyecto: el modelado vale más y el resto menos.\n▪️ Modelado: +130 %\n"
             "▪️ Mediciones: −60 %\n▪️ Memoria: −25 %\n▪️ Estructuras: −20 %\n\nRecibes el modelo LOD 300 con sus familias, "
             "IFC durante el trabajo y RVT con el pago final." + "\n\n📌 Guárdalo para cuando lo necesites.")


def revit():
    out = []
    for k in range(8):                                    # 4 combinaciones de escenas × 2 ganchos distintos cada una
        orden = REVIT_ORDEN[k % 4]
        out.append(_pieza("revit", f"r{k}", (k + k // 4) % 4, "CAD O REVIT", REVIT_HOOKS,
                          {sc: REVIT_ESC[sc] for sc in orden}, REVIT_CAP, f"r{k % 4}"))
    return out


# ------------------------------------------------------------------ interacción (fuentes/interaccion.json)
LETRAS = "ABCD"
CTA_INTERACCION = "Síguenos para más. Y si tu estudio va a tope, agenda una reunión para conocernos y crecer juntos."


def _voz(t):
    return t.replace("ø", "o").replace(" · ", ": ")


def _quiz(tema, clave, k, badge, titulo, pregunta, opciones, correcta, explicacion, hooks, caption, voz_ops,
          cta="Comenta tu respuesta", pill="Guárdalo para repasar", sol_voz=None, letras=LETRAS, revelar=True, nota=None):
    """revelar=False (tests y verdadero o falso): el reel acaba en la pregunta y la solución la publica el bot de
    comunidad en los comentarios 12-24 h después (comunidad.py). Así la gente comenta para participar y vuelve."""
    preg = {"titulo": titulo, "pregunta": pregunta, "opciones": opciones, "letras": letras, "cta": cta, "segundos": 3,
            "pausa": 2.5, "nota": nota}
    preg_voz = [_voz(pregunta)] + voz_ops + [cta + "." + (" Mañana te damos la solución." if not revelar else "")]
    resp = {"titulo": "La respuesta" if correcta >= 0 else "Tu respuesta", "pregunta": pregunta, "opciones": opciones,
            "letras": letras, "correcta": correcta, "explicacion": explicacion, "pill": pill}
    resp_voz = [sol_voz, _voz(explicacion), pill + "."]
    escenas = {"pregunta": (preg, preg_voz)}
    if revelar:
        escenas["respuesta"] = (resp, resp_voz)
    p = _pieza(tema, clave, k, badge, hooks, escenas, caption, clave, pid_key="pregunta/respuesta")   # id estable
    p["infografia"]["cta"] = CTA_INTERACCION
    p["solucion"] = {"tipo": tema, "pregunta": pregunta, "opciones": opciones, "letras": letras, "correcta": correcta,
                     "explicacion": explicacion}                  # para el bot de comunidad
    return p


def interaccion():
    B = json.load(open(os.path.join(HERE, "fuentes", "interaccion.json")))
    out = []
    H_TEST = [("¿La sabes sin buscarla?", "Una pregunta de arquitectura. ¿La sabes sin buscarla?"),
              ("Pásaselo a tu equipo", "Pásaselo a tu equipo y comparad respuestas."),
              ("¿Aciertas a la primera?", "A ver si aciertas a la primera. Pásaselo a tu equipo y comparad.")]
    for i, q in enumerate(B["tests"]):
        ops, c = q["opciones"], q["correcta"]
        cap = (f"{q['pregunta']}\n\n" + "\n".join(f"{LETRAS[j]}) {o}" for j, o in enumerate(ops))
               + "\n\n👇 Comenta tu respuesta (A, B, C o D). Mañana publicamos la solución en comentarios.\n"
                 "🔁 Pásaselo a tu equipo y comparad.")
        out.append(_quiz("test", f"t{i}", i, "TEST DE ARQUITECTO", "Test de arquitecto", q["pregunta"], ops, c,
                         q["explicacion"], H_TEST, cap, [f"Opción {LETRAS[j]}: {_voz(o)}." for j, o in enumerate(ops)],
                         sol_voz=f"La correcta es la opción {LETRAS[c]}.", revelar=False,
                         nota="La solución, mañana en comentarios"))
        out[-1]["referencia"] = q["fuente"]
    H_VF = [("Esta parece fácil", "Esta parece fácil. ¿Verdadero o falso?"),
            ("Contesta sin buscarlo", "Verdadero o falso. Contesta sin buscarlo."),
            ("¿Te la sabes?", "¿Te la sabes? Comenta tu respuesta.")]
    for i, q in enumerate(B["vf"]):
        c = 0 if q["verdadero"] else 1
        ex = q["explicacion"].split(". ", 1)[1] if q["explicacion"].startswith(("Verdadero.", "Falso.")) else q["explicacion"]
        cap = (f"¿Verdadero o falso?\n\n{q['afirmacion']}\n\n👇 Comenta V o F. Mañana publicamos la solución en "
               "comentarios.\n🔁 Pásaselo a tu equipo y comparad.")
        out.append(_quiz("vf", f"v{i}", i, "¿VERDADERO O FALSO?", "¿Verdadero o falso?", q["afirmacion"],
                         ["Verdadero", "Falso"], c, ex, H_VF, cap, ["¿Verdadero?", "¿O falso?"],
                         cta="Comenta V o F", sol_voz=("Verdadero." if c == 0 else "Falso."), letras="VF", revelar=False,
                         nota="La solución, mañana en comentarios"))
        out[-1]["referencia"] = q["fuente"]
    H_EN = [("Contesta con una letra", "Una pregunta rápida para arquitectos. Contesta con una letra."),
            ("Queremos saberlo", "Queremos saber cómo trabajas. Contesta en comentarios."),
            ("¿Y tú qué contestas?", "Una pregunta para los que llevan un estudio. ¿Tú qué contestas?")]
    for i, q in enumerate(B["encuestas"]):
        ops = q["opciones"]
        cap = (f"{q['pregunta']}\n\n" + "\n".join(f"{LETRAS[j]}) {o}" for j, o in enumerate(ops))
               + "\n\n👇 Contesta en comentarios con la letra. Mañana te contamos qué ha votado la mayoría.\n"
                 "🔁 Compártelo con otro arquitecto.")
        out.append(_quiz("encuesta", f"e{i}", i, "ENCUESTA PARA ARQUITECTOS", "Encuesta", q["pregunta"], ops, -1,
                         "No hay respuesta buena o mala: cuéntanos la tuya.", H_EN, cap,
                         [f"Opción {LETRAS[j]}: {_voz(o)}." for j, o in enumerate(ops)], cta="Contesta en comentarios",
                         pill="Te leemos en comentarios", sol_voz="Aquí no hay respuesta correcta."))
    for i, a in enumerate(B["atajos"]):
        prog = "AutoCAD" if a["programa"] == "autocad" else "Revit"
        pill = a["voz"][-1].rstrip(".")
        datos = {"titulo": a["titulo"], "items": [tuple(x) for x in a["items"]], "uda": pill, "tachar": False}
        hooks = [(f"Guárdalo si usas {prog}", f"Si trabajas con {prog}, guárdate esto."),
                 (f"{prog}: ¿los usas todos?", f"Atajos de {prog}. ¿Cuántos usas ya? Cuéntalo en comentarios."),
                 (f"Menos clics en {prog}", f"Menos clics y más tiempo para proyectar. Atajos de {prog}.")]
        cap = (a["titulo"] + ("" if a["programa"] == "revit" else " (versión en inglés)") + ":\n\n"
               + "\n".join(f"▪️ {t}: {d}" for _, t, d in a["items"])
               + "\n\n📌 Guárdalo para tenerlo a mano.\n👇 ¿Cuál añadirías tú?")
        p = _pieza("atajos", f"a{i}", i, "GUÁRDALO", hooks, {"cargas_atajos": (datos, list(a["voz"]))}, cap, f"a{i}")
        p["infografia"]["cta"] = CTA_INTERACCION
        out.append(p)
    return out


def _check(p):
    """Cada escena tiene tantas frases como golpes en pantalla (si no, la voz y el texto no cuadran)."""
    ig = p["infografia"]
    for sc in ig["orden"]:
        d, v, base = ig["datos"][sc], ig["voz"][sc], sc.split("_")[0]
        need = {"towers": len(d.get("barras", [])) + 1, "cargas": 6, "pregunta": 2 + len(d.get("opciones", [])), "respuesta": 3, "timeline": len(d.get("pasos", [])), "delegable": 2,
                "versus": 2, "donut": 1, "quote": 1, "stack": 1}[base]
        assert len(v) == need, (p["id"], sc, len(v), need)
    return p


def generate():
    """Piezas de las temáticas que no salen de casos.py (las de casos.py se añaden en questions.load)."""
    return [_check(p) for p in partidas() + actuaciones() + revit() + interaccion()]


if __name__ == "__main__":
    import collections, datetime
    ps = generate() + [_check(p) for p in casos.generate()]
    print(collections.Counter(p["infografia"]["variante"] for p in ps))
    hoy = datetime.date.today(); lunes = hoy - datetime.timedelta(hoy.weekday())
    for d, fila in zip("LMXJVSD", semana(lunes)):
        print(d, fila)
    rec = []
    for d in range(28):
        for s_ in SLOTS:
            rec.append(tema_de(lunes + datetime.timedelta(d), s_, rec))
    print("4 semanas:", collections.Counter(rec), "| UDA:", sum(r in UDA for r in rec) / len(rec))
