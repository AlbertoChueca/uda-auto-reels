"""Las 7 temáticas de los reels de UDA y su calendario semanal (3 reels al día, 21 a la semana).

Cada temática sale exactamente 3 veces por semana, nunca dos veces el mismo día y nunca dos reels seguidos iguales:

    1 coste        Cuánto cuesta delegar tu proyecto           (casos.py: unifamiliar, nave, equipamiento, por m²)
    2 contratar    Contratar o delegar: lo que no sale en la nómina   (casos.py)
    3 partidas     Qué incluye cada partida que delegas y cuánto cuesta (planimetría, construcción, instalaciones...)
    4 actuaciones  Encargos pequeños con precio cerrado (locales, ascensor, fachada, legalización, piscina...)
    5 revit        CAD o Revit: mismo precio, modelo LOD 300, mediciones del modelo, instalaciones en 3D
    6 proceso      Cómo trabajamos: reunión, presupuesto en 24 h, pagos 60/40, revisiones, testimonios (casos.py)
    7 inspiracion  Renders de arquitectura + curiosidades comprobadas (fuentes/curiosidades.json, formato «render»)

Nada se inventa: precios de la Tabla de presupuestos de UDA (fuentes/uda_tabla_presupuestos.txt, apartados 03, 06, 07,
08 y 09), hechos de assets/uda/hechos.md y testimonios literales de la web. Dentro de cada temática hay varias piezas
(y cada una con su combinación de escenas y su gancho), así que una temática nunca repite el reel de la semana anterior.
Calendario completo y guiones: GUIONES.md (python guiones.py).
"""
import hashlib

import casos

TEMAS = ["coste", "contratar", "partidas", "actuaciones", "revit", "proceso", "inspiracion"]
NOMBRE = {"coste": "Cuánto cuesta delegar", "contratar": "Contratar o delegar", "partidas": "Qué incluye cada partida",
          "actuaciones": "Encargos pequeños, precio cerrado", "revit": "CAD o Revit", "proceso": "Cómo trabajamos",
          "inspiracion": "Renders y curiosidades"}
VARIANTE = {"coste": "caso", "contratar": "contratar", "proceso": "proceso"}       # nombre interno en casos.py
TEMA_DE_VARIANTE = {v: k for k, v in VARIANTE.items()}
SLOTS = {"manana": 0, "mediodia": 1, "tarde": 2}


def plan(fecha, slot):
    """Calendario fijo: (día de la semana × 3 + hueco) mod 7 -> cada temática 3 veces por semana, nunca seguidas."""
    return TEMAS[(fecha.weekday() * 3 + SLOTS.get(slot, 0)) % 7]


def tema_de(fecha, slot, recientes=()):
    """La del calendario, salvo que haya salido en los 2 últimos reels (p. ej. tras lanzamientos manuales): entonces la
    que lleva más tiempo sin salir."""
    rec = [r for r in recientes if r]
    p = plan(fecha, slot) if slot in SLOTS else None
    if p and p not in rec[-2:]:
        return p
    return min(TEMAS, key=lambda t: (max([i for i, r in enumerate(rec) if r == t], default=-1), TEMAS.index(t)))


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


def _pieza(tema, clave, k, badge, hooks, escenas, caption, grupo):
    """Pieza de infografía con el mismo formato que las de casos.py (la usan el guionista, el montaje y la descripción)."""
    datos = {sc: d for sc, (d, v) in escenas.items()}
    voz = {sc: v for sc, (d, v) in escenas.items()}
    orden = list(escenas)
    j = k % len(hooks); hooks = hooks[j:] + hooks[:j]
    pid = hashlib.sha1(f"{tema}|{clave}|{k}|{'/'.join(orden)}".encode()).hexdigest()[:10]
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
               + "\n\nTú sigues firmando: el diseño, el visado y la dirección de obra son tuyos.")
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
                 "Tú presupuestas, firmas y tramitas; nuestro precio te deja margen.")
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
             "IFC durante el trabajo y RVT con el pago final.")


def revit():
    out = []
    for k in range(8):                                    # 4 combinaciones de escenas × 2 ganchos distintos cada una
        orden = REVIT_ORDEN[k % 4]
        out.append(_pieza("revit", f"r{k}", (k + k // 4) % 4, "CAD O REVIT", REVIT_HOOKS,
                          {sc: REVIT_ESC[sc] for sc in orden}, REVIT_CAP, f"r{k % 4}"))
    return out


def _check(p):
    """Cada escena tiene tantas frases como golpes en pantalla (si no, la voz y el texto no cuadran)."""
    ig = p["infografia"]
    for sc in ig["orden"]:
        d, v, base = ig["datos"][sc], ig["voz"][sc], sc.split("_")[0]
        need = {"towers": len(d.get("barras", [])) + 1, "cargas": 6, "timeline": len(d.get("pasos", [])), "delegable": 2,
                "versus": 2, "donut": 1, "quote": 1, "stack": 1}[base]
        assert len(v) == need, (p["id"], sc, len(v), need)
    return p


def generate():
    """Piezas de las temáticas que no salen de casos.py (las de casos.py se añaden en questions.load)."""
    return [_check(p) for p in partidas() + actuaciones() + revit()]


if __name__ == "__main__":
    import collections, datetime
    ps = generate() + [_check(p) for p in casos.generate()]
    print(collections.Counter(p["infografia"]["variante"] for p in ps))
    hoy = datetime.date.today(); lunes = hoy - datetime.timedelta(hoy.weekday())
    for d, fila in zip("LMXJVSD", semana(lunes)):
        print(d, fila)
