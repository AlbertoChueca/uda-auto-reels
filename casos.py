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
EXTRAS = ("delegable", "quote", "timeline", "donut")


def infografia(p, k):
    """Guion de la infografía animada (escenas de infoviz.py) a partir de un caso calculado."""
    b = p["barras"]; tipo = p["tipologia"]
    corto = {"unifamiliar": "Unifamiliar", "industrial": "Nave", "equipamiento": "Equipamiento"}[tipo]
    torres = [dict(b[0], etiqueta="Estructuras e instalaciones"), dict(b[1], etiqueta="P. Ejecución completo"),
              dict(b[2], etiqueta="Básico + Ejecución")]
    extra = EXTRAS[k % len(EXTRAS)]
    ig = {"nuevo": f"{corto} · {p['m2']:,} m²".replace(",", "."),
          "torres": {"titulo": f"{corto} de {p['m2']:,} m² · cuánto cuesta delegar".replace(",", "."), "barras": torres, "conclusion": "Tú eliges cuánto delegas"},
          "torres_voz": [f"Solo estructuras e instalaciones: {b[0]['texto']}.", f"El proyecto de ejecución completo: {b[1]['texto']}.",
                         f"Básico y ejecución: {b[2]['texto']}."],
          # contratar = el coste anual de la tabla (40.000–47.000 €/año, haya proyectos o no): delegar SIEMPRE sale muy por debajo
          "versus": {"titulo": "Contratar o delegar", "a_tit": "Un arquitecto en plantilla", "a_num": "40.000–47.000 €",
                     "a_txt": "al año, haya proyectos o no", "b_tit": "Delegar este proyecto", "b_num": b[2]["texto"],
                     "b_txt": "Básico + Ejecución, una sola vez"},
          "versus_voz": ["Un empleado: de 40.000 a 47.000 € al año, haya proyectos o no.",
                         f"Delegar este proyecto: {b[2]['texto']}, una sola vez."],
          # lo que no sale en la nómina (tabla, apartado 01, y testimonio de la web)
          "cargas": {"titulo": "Y no es solo dinero", "items": [
              ("doc", "Hay que formarle", "meses enseñándole tus plantillas"),
              ("calendar", "Bajas y vacaciones", "siempre llegan antes de una entrega"),
              ("euro", "Nómina sin trabajo", "le pagas aunque no haya proyectos"),
              ("team", "Despedir duele", "también emocionalmente")],
              "uda": "Con UDA, nada de eso"},
          "cargas_voz": ["Y no es solo dinero.", "Hay que formarle.", "Puede coger una baja.",
                         "Le pagas aunque no haya trabajo.", "Y despedir duele.", "Con UDA, nada de eso."],
          "extra": extra,
          # qué se puede delegar y qué no (Tabla, apartado 09: qué incluye cada partida / no incluye)
          "delegable": {"titulo": "Qué delegas y qué sigue siendo tuyo",
                        "si": ["Planos en CAD o Revit", "Estructuras con CYPE", "Instalaciones", "Memorias", "Mediciones y presupuesto"],
                        "no": ["El diseño", "La firma y el visado", "La dirección de obra"]},
          "delegable_voz": ["Delegas planos, estructuras, instalaciones, memorias y mediciones.",
                            "Lo tuyo: el diseño, la firma y la obra."]}
    if extra == "delegable":
        ig["extra_voz"] = list(ig["delegable_voz"])
    elif extra == "donut":
        ig["donut"] = {"pct": 67, "prefijo": "hasta un", "texto": "más de tiempo para actividades de valor",
                       "titulo": "Lo que ganan los estudios que externalizan", "fuente": "uniondearquitectos.com"}
        ig["extra_voz"] = ["Los estudios que externalizan ganan hasta un 67 % más de tiempo para actividades de valor."]
    elif extra == "timeline":
        ig["timeline"] = {"titulo": "Así funciona", "pasos": [
            ("calendar", "Reunión", "nos cuentas qué necesitas"),
            ("euro", "Presupuesto cerrado", "en 24 horas: puedes repercutirlo a tu cliente"),
            ("plan", "Entrega por fases", f"P. Ejecución en {PLAZO_PE[tipo]}"),
            ("shield", "Tú firmas", "el trabajo es 100 % tuyo")]}
        ig["extra_voz"] = ["Una reunión.", "Presupuesto cerrado en 24 horas.",
                           f"Proyecto de ejecución en {PLAZO_PE[tipo].replace('–', ' a ')}.", "Y tú firmas."]
    else:
        t = TESTIMONIOS[1 + k % 2]                         # los que encajan con una voz masculina
        ig["quote"] = {"texto": t, "autor": "Estudio que colabora con UDA", "titulo": "Lo que dicen los estudios"}
        ig["extra_voz"] = ["Lo dice un estudio que ya delega."]
    return ig


def generate():
    if not _selftest():
        print("casos: las fórmulas no reproducen los ejemplos de la tabla; no se generan casos", flush=True)
        return []
    out = []
    for i, (t, m) in enumerate(CASOS):
        for v in range(3):                                  # 3 versiones: otra escena y otra infografía final
            p = caso(t, m, i + v)
            p["infografia"] = infografia(p, i + v)
            out.append(p)
    return out


if __name__ == "__main__":
    import json
    print("autocomprobación:", _selftest())
    for p in generate()[:3] + generate()[-2:]:
        print(json.dumps({k: p[k] for k in ("screen_hook", "escena", "titulo", "barras", "conclusion", "puntos")},
                         ensure_ascii=False, indent=1))
