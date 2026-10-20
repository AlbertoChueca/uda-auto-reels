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
PRESUPUESTO = "Presupuesto cerrado en 24–72 horas"                                   # "Solicita tu presupuesto..."
CTA_WEB = f"Solicita tu presupuesto en {WEB}"
CTA_CAPTION = ("¿Vas justo de equipo? En UDA hacemos tus Proyectos Básicos y de Ejecución, en CAD o en Revit, con precio "
               "cerrado y tu firma al final. Presupuesto cerrado en 24–72 horas en uniondearquitectos.com (link en la bio).")


def handle_plain():
    return HANDLE.lstrip("@")
