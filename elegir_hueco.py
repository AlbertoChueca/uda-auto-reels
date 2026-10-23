"""¿Qué toca publicar ahora? (lo usan los workflows programados, que GitHub lanza cada hora y a veces con horas de retraso)

    python elegir_hueco.py reels      -> manana | mediodia | tarde | skip
    python elegir_hueco.py carrusel   -> carrusel | skip

Un hueco toca si aún no se ha publicado hoy y la hora actual de España está entre 75 min antes de su hora (da tiempo a
generarlo y esperar a la hora exacta) y el inicio del siguiente hueco (la tarde, hasta las 23:00): GitHub llega a
retrasar los trabajos programados varias horas; así el reel sale tarde, pero sale.
"""
import datetime, json, os, sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
HUECOS = {"reels": [("manana", 8, 0), ("mediodia", 12, 0), ("tarde", 15, 0)], "carrusel": [("carrusel", 18, 0)]}


def publicado(slot, hoy):
    try:
        if slot == "carrusel":
            return any(e.get("fecha") == hoy and e.get("publicado") for e in json.load(open(os.path.join(HERE, "carruseles.json"))))
        for line in open(os.path.join(HERE, "log.jsonl")):
            e = json.loads(line)
            if e.get("date") == hoy and e.get("slot") == slot and any(
                    not str(v).startswith("error") for v in (e.get("publicado") or {}).values()):
                return True
    except Exception:
        pass
    return False


HASTA = {"manana": (10, 45), "mediodia": (13, 45), "tarde": (23, 0), "carrusel": (23, 0)}   # GitHub se retrasa horas


def elegir(tipo, now=None):
    """El hueco toca desde 75 min antes de su hora hasta que empieza el siguiente (la tarde y el carrusel, hasta las
    23:00): aunque GitHub lance el trabajo con varias horas de retraso, el reel sale ese día."""
    now = now or datetime.datetime.now(ZoneInfo("Europe/Madrid"))
    hoy = str(now.date())
    for slot, h, m in HUECOS[tipo]:
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        hh, mm = HASTA[slot]
        fin = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if t - datetime.timedelta(minutes=75) <= now <= fin and not publicado(slot, hoy):
            return slot
    return "skip"


if __name__ == "__main__":
    print(elegir(sys.argv[1] if len(sys.argv) > 1 else "reels"))
