"""Genera GUIONES.md: el guion de cada tipo de reel, de dónde sale cada dato y lo que se ve y se oye en cada escena.

    python guiones.py

Fuente única de los reels:
  · tematicas.py           -> las 7 temáticas y su calendario semanal (3 reels al día; cada temática 3 veces por semana)
  · casos.py               -> temáticas coste, contratar y proceso (precios calculados con la Tabla de presupuestos)
  · fuentes/curiosidades.json -> renders + curiosidades (cada dato con su fuente)
  · writer.CTAS            -> cierres hablados
"""
import json, os
import casos, tematicas, writer

HERE = os.path.dirname(os.path.abspath(__file__))
TIT = {"towers": "Cuánto cuesta delegar (3 edificios dorados)", "versus": "Contratar o delegar", "cargas": "Y no es solo dinero",
       "delegable": "Qué delegas y qué sigue siendo tuyo", "timeline": "Así funciona", "quote": "Testimonio (web de UDA)",
       "stack": "Tu estudio hoy", "donut": "Tiempo", "pregunta": "Pregunta (cuenta atrás: comenta)",
       "respuesta": "Solución"}


def main():
    out = ["# Guiones de los reels de UDA", "",
           "Todo lo que dicen y muestran los reels sale de aquí. La voz dice exactamente el texto de cada escena.", "",
           "## Calendario semanal", "",
           "21 reels a la semana: 17 de interacción (tests, verdadero o falso, encuestas, atajos y curiosidades, para que "
           "la gente comente y guarde) y 4 de UDA (20 %), que rotan entre sus 6 temas. Nunca dos reels seguidos del mismo "
           "tipo. Todos se publican en Instagram, TikTok y LinkedIn.", "",
           "| Día | 8:00 | 12:00 | 15:00 | 18:00 |", "|---|---|---|---|---|"]
    import datetime
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for d, row in enumerate(tematicas.semana(datetime.date(2026, 10, 26))):
        out.append(f"| {dias[d]} | " + " | ".join(tematicas.NOMBRE[t] for t in row) + " | Carrusel |")
    todas = casos.generate() + tematicas.generate()
    out += ["", "## Los tipos de reel", "",
            "Precios: fórmulas de la Tabla de presupuestos de UDA (comprobadas con sus ejemplos publicados). Contratar: "
            "40.000–47.000 €/año (apartado 01). Ventajas, proceso y testimonios: uniondearquitectos.com.", ""]
    for t in tematicas.TEMAS:
        if t == "inspiracion":
            continue
        var = tematicas.VARIANTE.get(t, t)
        ps = [p for p in todas if p["infografia"]["variante"] == var]
        out += [f"### {tematicas.NOMBRE[t]} · {len(ps)} reels distintos", ""]
        vistos = set()
        for p in ps:
            G = p["infografia"]; key = (p.get("grupo", "").split(":")[-1] if t in ("partidas", "actuaciones") else "") + "/".join(G["orden"])
            if key in vistos or len(vistos) >= (6 if t in ("partidas", "actuaciones") else 3):
                continue
            vistos.add(key)
            out += [f"**Ejemplo {len(vistos)}** — gancho: {G['screen_hook']} · voz: «{G['hook_line']}»"]
            for sc in G["orden"]:
                out.append(f"- **{TIT.get(sc.split('_')[0], sc)}:** " + " / ".join(f"«{x}»" for x in G["voz"][sc]))
            out.append("")
        out += [f"- **Cierre:** «{writer.CTAS[0]}»", ""]
    cur = json.load(open(os.path.join(HERE, "fuentes", "curiosidades.json")))["items"]
    out += [f"### {tematicas.NOMBRE['inspiracion']} · {len(cur)} curiosidades comprobadas", ""]
    for c in cur:
        out += [f"### {c['screen_hook']}", f"- **Gancho:** «{c['hook_line']}»"] + [f"- «{b}»" for b in c["beats"]] + \
               [f"- **Puente:** «{c['puente']}»", f"- **Fuente:** {c['fuente']}", ""]
    open(os.path.join(HERE, "GUIONES.md"), "w").write("\n".join(out) + "\n")
    print("GUIONES.md actualizado")


if __name__ == "__main__":
    main()
