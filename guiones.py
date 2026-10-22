"""Genera GUIONES.md: el guion de cada tipo de reel, de dónde sale cada dato y lo que se ve y se oye en cada escena.

    python guiones.py

Fuente única de los reels:
  · casos.py               -> infografías (precios calculados con la Tabla de presupuestos 2026 + textos de la web de UDA)
  · fuentes/curiosidades.json -> renders + curiosidades (cada dato con su fuente)
  · writer.CTAS            -> cierres hablados
"""
import json, os
import casos, writer

HERE = os.path.dirname(os.path.abspath(__file__))
TIT = {"towers": "Cuánto cuesta delegar (3 edificios dorados)", "versus": "Contratar o delegar", "cargas": "Y no es solo dinero",
       "delegable": "Qué delegas y qué sigue siendo tuyo", "timeline": "Así funciona", "quote": "Testimonio (web de UDA)",
       "stack": "Tu estudio hoy", "donut": "Tiempo"}


def main():
    out = ["# Guiones de los reels de UDA", "",
           "Todo lo que dicen y muestran los reels sale de aquí. La voz dice exactamente el texto de cada escena.", "",
           "## Calendario", "", "| Día | 8:00 | 12:00 | 15:00 | 18:00 |", "|---|---|---|---|---|"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for d, row in enumerate(casos.SEMANA):
        mid = "Renders + curiosidad" if d in (1, 4) else row[1]
        out.append(f"| {dias[d]} | {row[0]} | {mid} | {row[2]} | Carrusel |")
    out += ["", "## Infografías (ejemplo: vivienda unifamiliar de 150 m²)", "",
            "Precios: fórmulas de la Tabla de presupuestos 2026 (comprobadas con sus ejemplos publicados). "
            "Contratar: 40.000–47.000 €/año (apartado 01 de la tabla). Ventajas y proceso: uniondearquitectos.com.", ""]
    ej = {p["infografia"]["variante"]: p for p in casos.generate() if p["tipologia"] == "unifamiliar" and p["m2"] == 150}
    for var, p in ej.items():
        G = p["infografia"]
        out += [f"### {G['badge']} · tipo «{var}»", "", f"- **Gancho:** {G['screen_hook']} — voz: «{G['hook_line']}»"]
        for sc in G["orden"]:
            out.append(f"- **{TIT.get(sc, sc)}:** " + " / ".join(f"«{x}»" for x in G["voz"][sc]))
        out += [f"- **Cierre:** «{writer.CTAS[0]}»", ""]
    cur = json.load(open(os.path.join(HERE, "fuentes", "curiosidades.json")))["items"]
    out += ["## Renders + curiosidades (martes y viernes a las 12:00)", ""]
    for c in cur:
        out += [f"### {c['screen_hook']}", f"- **Gancho:** «{c['hook_line']}»"] + [f"- «{b}»" for b in c["beats"]] + \
               [f"- **Puente:** «{c['puente']}»", f"- **Fuente:** {c['fuente']}", ""]
    open(os.path.join(HERE, "GUIONES.md"), "w").write("\n".join(out) + "\n")
    print("GUIONES.md actualizado")


if __name__ == "__main__":
    main()
