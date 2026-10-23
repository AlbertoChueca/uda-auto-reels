"""Casos de despacho con cifras CALCULADAS (contenido principal de UDA).

    «Tienes tres encargos a la vez y te entra una unifamiliar de 180 m². ¿La aceptas?»
    -> cuánto cuesta delegar solo una parte del Proyecto de Ejecución, el P. Ejecución entero o el Básico + Ejecución,
       frente a lo que cuesta un arquitecto en plantilla, y qué ganas al delegar (según la web de UDA).

Nada se inventa: cada importe sale de las fórmulas de la Tabla de Referencia de Presupuestos 2026 (parte fija +
m² × precio por m², por partida y fase, con «Gestión y análisis» siempre incluida) y el módulo comprueba al cargarse
que reproduce los ejemplos publicados en la propia tabla (viviendas de 90, 150 y 250 m², nave de 3.000 m²,
equipamiento de 2.000 m²). Si alguno no cuadra, no se genera ningún caso.

El coste de un arquitecto en plantilla (40.000–47.000 €/año) es el que da la propia tabla (apartado 01); las
ventajas al delegar salen literalmente de uniondearquitectos.com y de la tabla.
"""
import hashlib, math

# ------------------------------------------------------------------ tarifas (Tabla 2026, apartados 03 y 06)
# partida: (fijo, €/m²) por fase
TARIFAS = {
    "unifamiliar": {"pb": {"gestion": (200, .50), "planimetria": (220, 1.50), "memoria": (80, .35), "mediciones": (50, .45)},
                    "pe": {"gestion": (200, .50), "construccion": (250, .70), "instalaciones": (170, 1.50),
                           "estructuras": (350, 1.10), "memoria": (150, .70), "mediciones": (70, .80)}},
    "industrial": {"pb": {"gestion": (450, .10), "planimetria": (600, .30), "memoria": (350, .12), "mediciones": (200, .08)},
                   "pe": {"gestion": (450, .10), "construccion": (700, .15), "instalaciones": (450, .25),
                          "estructuras": (550, .20), "memoria": (380, .13), "mediciones": (270, .12)}},
    "equipamiento": {"pb": {"gestion": (700, .10), "planimetria": (1500, .40), "memoria": (400, .15), "mediciones": (400, .15)},
                     "pe": {"gestion": (700, .10), "construccion": (1700, .20), "instalaciones": (1000, .40),
                            "estructuras": (1100, .25), "memoria": (500, .08), "mediciones": (500, .07)}},
}
PLAZO_PE = {"unifamiliar": "20–35 días", "industrial": "30–55 días", "equipamiento": "30–55 días"}   # apartado 10
PLANTILLA_ANO = (40000, 47000)                     # apartado 01: arquitecto en plantilla, €/año, haya proyectos o no
TABLA = "Tabla de presupuestos de UDA (precios de referencia)"


def fase(tipo, f, m2, partidas=None):
    t = TARIFAS[tipo][f]
    ps = ["gestion"] + [p for p in (partidas or t) if p != "gestion"]
    return round(sum(t[p][0] + t[p][1] * m2 for p in ps))


def eur(x):
    return f"{x:,.0f} €".replace(",", ".")


def _selftest():
    ok = (fase("unifamiliar", "pb", 90), fase("unifamiliar", "pe", 90)) == (802, 1667) \
        and (fase("unifamiliar", "pb", 150), fase("unifamiliar", "pe", 150)) == (970, 1985) \
        and (fase("unifamiliar", "pb", 250), fase("unifamiliar", "pe", 250)) == (1250, 2515) \
        and fase("industrial", "pb", 3000) + fase("industrial", "pe", 3000) == 9050 \
        and fase("industrial", "pb", 500) + fase("industrial", "pe", 500) == 5175 \
        and fase("equipamiento", "pb", 2000) + fase("equipamiento", "pe", 2000) == 12300
    return ok


# ------------------------------------------------------------------ escenas y ventajas
# (con artículo, corto con artículo, demostrativo corto, pronombre)
G = {"unifamiliar": ("una vivienda unifamiliar", "una unifamiliar", "esta unifamiliar", "la"),
     "industrial": ("una nave industrial", "una nave", "esta nave", "la"),
     "equipamiento": ("un equipamiento", "un equipamiento", "este equipamiento", "lo")}
NOMBRE = {"unifamiliar": "vivienda unifamiliar", "industrial": "nave industrial", "equipamiento": "equipamiento"}
ESCENAS = [
    ("¿Aceptas {c} de {m} m²?", "Tienes tres encargos a la vez y te entra {n} de {m} m². ¿{P} aceptas?"),
    ("{C} de {m} m² más", "Tu equipo va a tope y un cliente te pide {n} de {m} m². ¿Dices que no?"),
    ("{m} m² y el equipo a tope", "Se te juntan las entregas y llega {n} de {m} m². ¿Contratas a alguien o delegas?"),
    ("¿Contratar o delegar {d}?", "Te encargan {n} de {m} m² y no quieres ampliar plantilla. Haz números."),
]
# (texto en pantalla, cita literal de la fuente)
VENTAJAS = [
    ("Sin nóminas en los meses sin proyectos", "Meses sin trabajo y despidos | Nóminas igualmente, y después indemnización y papeleo. | Coste cero. Sin permanencia."),
    ("Sin seguros sociales, vacaciones, bajas ni licencias", "eliminas el pago de seguros sociales, vacaciones, bajas y licencias de software"),
    ("Presupuesto cerrado y plazos fijados antes de empezar", "Te enviamos un presupuesto cerrado con fechas de entrega inamovibles."),
    ("Marca blanca: tu cliente nunca lo sabe", "Tu cliente final nunca sabrá que has externalizado la producción técnica con nosotros."),
    ("Pagas el 60 % al iniciar y el 40 % al entregar", "Solicitamos un abono inicial del 60%"),
    ("Tú firmas: todo el trabajo es 100 % tuyo", "Recibirás los editables, PDFs y todo lo utilizado en el pedido. Es 100% tuyo."),
    ("Equipo con experiencia desde el primer día", "Equipo con experiencia, adaptado a ti desde el primer día."),
]
PARCIAL = {"unifamiliar": (("estructuras", "instalaciones"), "Delegar solo estructuras e instalaciones"),
           "industrial": (("estructuras", "instalaciones"), "Delegar solo estructuras e instalaciones"),
           "equipamiento": (("estructuras", "instalaciones"), "Delegar solo estructuras e instalaciones")}
CASOS = [("unifamiliar", m) for m in (100, 120, 140, 150, 160, 180, 200, 220, 240, 250, 280, 300)] + \
        [("industrial", m) for m in (600, 800, 1200, 1500, 2000, 3000)] + [("equipamiento", m) for m in (800, 1200, 1500, 2000)]


def _meses(total):
    """Meses de un arquitecto en plantilla que cuestan, como mínimo, más que el total (cota prudente: 40.000 €/año)."""
    return max(1, math.ceil(total / (PLANTILLA_ANO[0] / 12)))


def caso(tipo, m2, k=0):
    pb, pe = fase(tipo, "pb", m2), fase(tipo, "pe", m2)
    parts, lab = PARCIAL[tipo]
    lab = "Solo estructuras e instalaciones"
    par = fase(tipo, "pe", m2, parts)
    total = pb + pe
    n = _meses(total)
    lo, hi = round(PLANTILLA_ANO[0] / 12 * n), round(PLANTILLA_ANO[1] / 12 * n)
    mes = "un mes" if n == 1 else f"{n} meses"
    barras = [{"etiqueta": lab, "valor": par, "texto": eur(par)},
              {"etiqueta": "Proyecto de Ejecución completo", "valor": pe, "texto": eur(pe)},
              {"etiqueta": "Básico y Ejecución", "valor": total, "texto": eur(total)},
              {"etiqueta": f"{mes[0].upper() + mes[1:]} de un empleado", "valor": hi,
               "texto": f"{eur(lo)[:-2]}–{eur(hi)}"}]
    sh, hl = ESCENAS[k % len(ESCENAS)]
    n_, c_, d_, pr = G[tipo]; nm = NOMBRE[tipo]
    mm = f"{m2:,}".replace(",", ".")
    fmt = dict(n=n_, c=c_, C=c_[0].upper() + c_[1:], d=d_, P=pr.capitalize(), m=mm)
    plazo = (f"Plazo orientativo del P. Ejecución: {PLAZO_PE[tipo]}", f"{PLAZO_PE[tipo]}")
    rng = int(hashlib.md5(f"{tipo}{m2}".encode()).hexdigest(), 16)
    v = [VENTAJAS[(rng + i * 3) % len(VENTAJAS)] for i in range(2)]
    v = list(dict.fromkeys(v))[:2] + [plazo]
    pid = hashlib.sha1(f"caso|{tipo}|{m2}|{k}".encode()).hexdigest()[:10]
    return {
        "id": pid, "tipo": "caso", "tema": "uda_casos", "bloque": "servicios", "norma": "uda_tabla",
        "calculado": True, "fuente_ok": True, "tipologia": tipo, "m2": m2,
        "referencia": f"{TABLA} · uniondearquitectos.com",
        "screen_hook": sh.format(**fmt),
        "escena": hl.format(**fmt),
        "titulo": f"Delegar {n_.split(' ', 1)[1]} de {m2:,} m²".replace(",", "."),
        "barras": barras,
        "conclusion": f"El proyecto completo, por menos de {mes} de un arquitecto en plantilla.",
        "puntos_titulo": "Y una vez delegado",
        "puntos": [x[0] for x in v],
        "citas": [f"{TABLA}: partidas fijo + €/m² (apartados 03 y 06)",
                  "UN ARQUITECTO EN PLANTILLA: 40.000–47.000 €/año."] + [x[1] for x in v],
    }


# Testimonios LITERALES de uniondearquitectos.com (los casos de éxito reales que tenemos; nada inventado)
TESTIMONIOS = [
    "Estaba agobiada con tanto trabajo y cumplieron tanto con la calidad como con la fecha de entrega que les propuse. "
    "Fue un acierto confiar en UDA. Lo recomiendo.",
    "Somos un despacho pequeño, como una familia. Se me hacía duro contratar a alguien para 3 meses y tener que "
    "despedirle. UDA me ayuda mucho en el día a día y estoy contento con ellos.",
    "Varias veces se me juntan varios proyectos de golpe y esos días duermo poco y mal. Desde que trabajo con UDA eso "
    "cambió y lo gestiono mejor y sin problemas.",
]


# Tipos de reel de infografía (rotan a lo largo de la semana; ninguno es una tabla)
#   nombre: (etiqueta, gancho en pantalla, gancho hablado, escenas)
VARIANTES = {
    "caso": ("CUÁNTO CUESTA DELEGAR", None, None, ["towers", "versus", "cargas"]),
    "contratar": ("CONTRATAR O DELEGAR", "¿Contratar o delegar?",
                  "¿Contratas a alguien o delegas el proyecto? Haz números.", ["versus", "cargas", "delegable"]),
    "delegable": ("QUÉ PUEDES DELEGAR", "¿Qué puedes delegar?",
                  "¿Qué parte de un proyecto puedes delegar sin perder el control?", ["delegable", "towers", "timeline"]),
    "tiempo": ("MÁS TIEMPO PARA TU ESTUDIO", "¿Te faltan horas?",
               "¿Te faltan horas para proyectar y atender a tus clientes?", ["stack", "delegable", "towers"]),
    "proceso": ("CÓMO TRABAJAMOS", "Así se delega un proyecto", "Así se delega un proyecto, paso a paso.",
                ["timeline", "delegable", "versus"]),
    "testimonio": ("LO QUE DICEN LOS ESTUDIOS", "Lo que cambia al delegar",
                   "Esto es lo que cambia cuando un estudio delega.", ["quote", "cargas", "versus"]),
}
# orden semanal: (lunes..domingo) x (8:00, 12:00, 15:00) -> nunca dos días iguales
SEMANA = [["caso", "tiempo", "contratar"], ["delegable", "caso", "testimonio"], ["contratar", "proceso", "caso"],
          ["tiempo", "caso", "delegable"], ["caso", "testimonio", "proceso"], ["contratar", "caso", "tiempo"],
          ["testimonio", "delegable", "caso"]]
# cada tipo tiene varias combinaciones de escenas: aunque el tipo se repita, el reel no se parece al anterior
ESCENAS_ALT = {
    "caso": [["towers", "delegable", "timeline"], ["stack", "towers", "cargas_garantias"], ["towers", "donut", "timeline_pagos"]],
    "contratar": [["versus", "cargas", "quote"], ["cargas", "versus", "donut"], ["versus", "cargas", "timeline"]],
    "proceso": [["timeline", "cargas_garantias", "quote"], ["timeline_pagos", "cargas_garantias", "towers"],
                ["timeline", "quote", "timeline_pagos"]],
}
EN_CASOS = tuple(ESCENAS_ALT)          # temáticas que salen de los casos calculados (las demás, en tematicas.py)
NO_REPETIR = 5          # un tipo de reel no vuelve a salir hasta que hayan salido otros 5 distintos


# lo que incluye siempre (tabla, apartados 09-10, y hechos.md) y cómo se paga (60 % / 40 % por fase)
GARANTIAS = {"titulo": "Lo que incluye siempre", "items": [
    ("shield", "1 revisión por fase", "2 en bloques de 30 viviendas o más"),
    ("calendar", "7 días de soporte", "después de cada entrega"),
    ("doc", "PDF y editables", "DWG en CAD, RVT en Revit"),
    ("team", "Marca blanca", "tu cliente nunca lo sabe")], "uda": "Y presupuesto cerrado", "tachar": False}
GARANTIAS_VOZ = ["Lo que incluye siempre.", "Una revisión por fase.", "Siete días de soporte.", "PDF y editables.",
                 "Marca blanca.", "Y presupuesto cerrado."]
PAGOS = {"titulo": "Así se paga", "pasos": [
    ("doc", "Listado de documentos", "solo pagas lo que delegas"),
    ("euro", "60 % al iniciar la fase", "nunca pagas todo de golpe"),
    ("euro", "40 % antes de la entrega", "cada fase, por separado"),
    ("shield", "Revisión incluida", "validas cada entrega")]}
PAGOS_VOZ = ["Marcas en el listado solo lo que delegas.", "El 60 % al iniciar la fase.", "El 40 % antes de la entrega.",
             "Y una revisión incluida en cada fase."]


def variante_de(fecha, slot, recientes=()):
    """Tipo de reel para este hueco: el del calendario si no ha salido en los últimos reels; si no, el que lleva más
    tiempo sin salir (así nunca salen dos reels del mismo tipo seguidos, tampoco en los lanzamientos manuales)."""
    rec = [r for r in recientes if r][-NO_REPETIR:]
    plan = SEMANA[fecha.weekday()][{"manana": 0, "mediodia": 1, "tarde": 2}.get(slot, 0)]
    if plan not in rec:
        return plan
    orden = list(VARIANTES)
    return min(orden, key=lambda v: (max([i for i, r in enumerate(rec) if r == v], default=-1), orden.index(v)))


def infografia(p, var, k=0):
    """Guion de la infografía animada (escenas de infoviz.py) a partir de un caso calculado."""
    b = p["barras"]; tipo = p["tipologia"]
    corto = {"unifamiliar": "Unifamiliar", "industrial": "Nave", "equipamiento": "Equipamiento"}[tipo]
    mm = f"{p['m2']:,}".replace(",", ".")
    torres = [dict(b[0], etiqueta="Estructuras e instalaciones"), dict(b[1], etiqueta="P. Ejecución completo"),
              dict(b[2], etiqueta="Básico + Ejecución")]
    t = TESTIMONIOS[2] if k % 2 else TESTIMONIOS[1]
    t = {TESTIMONIOS[1]: "Se me hacía duro contratar a alguien para 3 meses y tener que despedirle. UDA me ayuda mucho en el día a día.",
         TESTIMONIOS[2]: "Varias veces se me juntan varios proyectos de golpe. Desde que trabajo con UDA eso cambió y lo gestiono mejor y sin problemas."}[t]   # extracto literal: más ágil                             # los que encajan con una voz masculina
    datos = {
        "stack": {"titulo": "Tu estudio hoy", "nuevo": f"{corto} · {mm} m²"},
        "towers": {"titulo": f"{corto} de {mm} m² · cuánto cuesta delegar", "barras": torres,
                   "conclusion": "Tú eliges cuánto delegas"},
        # contratar = coste anual de la tabla (40.000–47.000 €/año, haya proyectos o no): delegar SIEMPRE sale muy por debajo
        "versus": {"titulo": "Contratar o delegar", "a_tit": "Un arquitecto en plantilla", "a_num": "40.000–47.000 €",
                   "a_txt": "al año, haya proyectos o no", "b_tit": "Delegar en UDA", "b_num": b[2]["texto"],
                   "b_txt": "una sola vez, proyecto completo"},
        # lo que no sale en la nómina (tabla, apartado 01, y testimonio de la web)
        "cargas": {"titulo": "Y no es solo dinero", "items": [
            ("doc", "Hay que formarle", "meses enseñándole tus plantillas"),
            ("calendar", "Bajas y vacaciones", "siempre llegan antes de una entrega"),
            ("euro", "Nómina sin trabajo", "le pagas aunque no haya proyectos"),
            ("team", "Despedir duele", "también emocionalmente")], "uda": "Con UDA, nada de eso"},
        # qué se puede delegar y qué no (tabla, apartado 09)
        "delegable": {"titulo": "Qué delegas y qué sigue siendo tuyo",
                      "si": ["Planos en CAD o Revit", "Estructuras con CYPE", "Instalaciones", "Memorias y mediciones"],
                      "no": ["El diseño", "La firma y el visado", "La dirección de obra"]},
        "donut": {"pct": 67, "prefijo": "hasta un", "texto": "más de tiempo para actividades de valor",
                  "titulo": "Lo que ganan los estudios que externalizan", "fuente": "uniondearquitectos.com"},
        "timeline": {"titulo": "Así funciona", "pasos": [
            ("calendar", "Reunión", "nos cuentas qué necesitas"),
            ("euro", "Presupuesto cerrado", "en 24 h: puedes repercutirlo a tu cliente"),
            ("plan", "Entrega por fases", f"P. Ejecución en {PLAZO_PE[tipo]}"),
            ("shield", "Tú firmas", "el trabajo es 100 % tuyo")]},
        "quote": {"texto": t, "autor": "Estudio que colabora con UDA", "titulo": "Un estudio que ya delega"},
        "cargas_garantias": GARANTIAS,
        "timeline_pagos": PAGOS,
    }
    # la voz dice EXACTAMENTE lo que pone en pantalla (el revisor marca cualquier diferencia como defecto)
    voz = {
        "stack": ["Tu estudio hoy: tres encargos en marcha. Y entra uno nuevo."],
        "towers": [f"Estructuras e instalaciones: {b[0]['texto']}.", f"Proyecto de ejecución completo: {b[1]['texto']}.",
                   f"Básico más ejecución: {b[2]['texto']}.", "Tú eliges cuánto delegas."],
        "versus": ["Un arquitecto en plantilla: de 40.000 a 47.000 € al año, haya proyectos o no.",
                   f"Delegar en UDA: {b[2]['texto']}, una sola vez, proyecto completo."],
        "cargas": ["Y no es solo dinero.", "Hay que formarle.", "Bajas y vacaciones.",
                   "Nómina sin trabajo.", "Despedir duele.", "Con UDA, nada de eso."],
        "delegable": ["Lo delegas en UDA: planos en CAD o Revit, estructuras con CYPE, instalaciones, memorias y mediciones.",
                      "Sigue siendo tuyo: el diseño, la firma y el visado, y la dirección de obra."],
        "donut": ["Los estudios que externalizan ganan hasta un 67 % más de tiempo para actividades de valor."],
        "timeline": ["Reunión.", "Presupuesto cerrado, en 24 horas.", "Entrega por fases.", "Y tú firmas."],
        "quote": [t],                                     # la voz lee el testimonio: se lee a su ritmo, sin prisas
        "cargas_garantias": GARANTIAS_VOZ,
        "timeline_pagos": PAGOS_VOZ,
    }
    badge, sh, hl, orden = VARIANTES[var]
    orden = ESCENAS_ALT[var][k % len(ESCENAS_ALT[var])]
    n_ = G[tipo][0]; tot = b[2]["texto"]
    # ganchos: el primero es el más concreto (el dilema y la cifra desde el segundo cero); el bucle de mejora prueba
    # los siguientes si el revisor dice que el gancho es genérico o tarda en llegar
    cc = G[tipo][1]; Cc = cc[0].upper() + cc[1:]
    hooks = {
        "caso": [(f"{tot} o 40.000 € al año", f"Delegar {n_} de {mm} metros: {tot}. Contratar a alguien: 40.000 euros al año."),
                 (f"{Cc} de {mm} m²: {tot}", f"{Cc} de {mm} metros, proyecto completo: {tot}. Y sin ampliar plantilla."),
                 (p["screen_hook"], p["escena"])],
        "contratar": [("40.000 € al año o un proyecto", f"Un arquitecto en plantilla cuesta 40.000 euros al año. Delegar un proyecto completo, {tot}."),
                      ("Lo que no sale en la nómina", "Contratar no es solo un sueldo. Esto es lo que no ves."),
                      (f"¿Contratar por {cc}?", f"¿Vas a contratar a alguien por {cc} de {mm} metros? Haz números antes.")],
        "delegable": [("Tú diseñas. Nosotros, el resto", "Tú diseñas y firmas. Los planos, las estructuras y las instalaciones, los hacemos nosotros."),
                      ("Tu firma, nuestro equipo", "La firma es tuya. El trabajo que no te deja dormir, lo hacemos nosotros."),
                      (f"{Cc} de {mm} m²: ¿qué delegas?", f"Te entra {cc} de {mm} metros. ¿Qué parte puedes delegar sin perder el control?"),
                      (sh, hl)],
        "tiempo": [("3 encargos y entra otro", "Tienes tres encargos en marcha y entra otro. ¿Cómo lo sacas sin contratar?"),
                   ("¿Te faltan horas?", "¿Te faltan horas para proyectar y atender a tus clientes?"),
                   (f"{mm} m² más y sin tiempo", f"Tu equipo va a tope y entra {cc} de {mm} metros. ¿De dónde sacas las horas?")],
        "proceso": [("De la reunión a tu firma", "De la primera reunión a tu firma: así se delega un proyecto."),
                    ("Presupuesto cerrado en 24 h", "Nos cuentas el proyecto y en 24 horas tienes un presupuesto cerrado."),
                    (f"Así se delega {cc}", f"Así se delega {cc} de {mm} metros, paso a paso.")],
        "testimonio": [("«Esos días duermo poco y mal»", "Esto nos contó un estudio que tenía varios proyectos de golpe."),
                       ("Lo que cambia al delegar", "Esto es lo que cambia cuando un estudio delega."),
                       ("Un estudio que ya delega", "Te contamos lo que nos dijo un estudio que ya trabaja con nosotros.")],
    }[var]
    j = k % len(hooks)
    hooks = hooks[j:] + hooks[:j]                         # cada caso abre con un gancho distinto
    return {"variante": var, "badge": badge, "screen_hook": hooks[0][0], "hook_line": hooks[0][1], "hooks": hooks,
            "orden": orden, "datos": {k_: datos[k_] for k_ in orden}, "voz": {k_: voz[k_] for k_ in orden}}


def generate():
    if not _selftest():
        print("casos: las fórmulas no reproducen los ejemplos de la tabla; no se generan casos", flush=True)
        return []
    out = []
    for i, (t, m) in enumerate(CASOS):
        for v, var in enumerate(EN_CASOS):                  # cada caso, en sus temáticas
            p = caso(t, m, i + v)
            p["id"] = hashlib.sha1(f"{p['id']}|{var}".encode()).hexdigest()[:10]
            p["grupo"] = f"{t}:{m}"                           # no repetir el mismo edificio en reels cercanos
            p["infografia"] = infografia(p, var, i + v)
            p["screen_hook"], p["escena"] = p["infografia"]["screen_hook"], p["infografia"]["hook_line"]
            out.append(p)
    return out


if __name__ == "__main__":
    import json
    print("autocomprobación:", _selftest())
    for p in generate()[:3] + generate()[-2:]:
        print(json.dumps({k: p[k] for k in ("screen_hook", "escena", "titulo", "barras", "conclusion", "puntos")},
                         ensure_ascii=False, indent=1))
