"""Datos de la marca en un solo sitio (UDA · Unión de Arquitectos).

Los colores y la tipografía están en fx.py (medidos en los documentos de UDA). Aquí, los textos fijos de marca: todos
salen literalmente de la Tabla de Referencia de Presupuestos y del Listado de Documentos a Delegar
(fuentes/uda_tabla_presupuestos.txt y fuentes/uda_listado_documentos.txt), así que nunca afirman nada inventado.
"""
import os

WEB = os.environ.get("APP_WEB", "uniondearquitectos.com")
HANDLE = os.environ.get("IG_HANDLE", "@uniondearquitectos")
NOMBRE = "UDA · Unión de Arquitectos"
CLAIM = "Tu equipo técnico de arquitectura, sin plantilla."                           # cabecera de la tabla
SUBCLAIM = "Proyectos Básicos y de Ejecución para despachos · 100 % online · Precio cerrado · Tu firma al final"
PRESUPUESTO = "Presupuesto cerrado en 24 horas"                                      # web: "presupuesto cerrado en 24 horas"
CTA = "Agenda una reunión para conocernos y crecer juntos"
VENTAJAS_CIERRE = ("Presupuesto cerrado en 24 h", "Repercútelo a tu cliente", "Factura más")
CTA_WEB = f"Solicita tu presupuesto en {WEB}"
CTA_CAPTION = ("¿Vas justo de equipo? En UDA seremos tu equipo técnico de confianza: Proyectos Básicos y de Ejecución con "
               "presupuesto cerrado en 24 horas, que puedes repercutir a tu cliente, y tu firma al final. Aumenta la "
               "facturación de tu estudio sin ampliar plantilla.\n\n👉 Agenda una reunión para conocernos y crecer juntos en "
               "uniondearquitectos.com (link en la bio).")


def handle_plain():
    return HANDLE.lstrip("@")
