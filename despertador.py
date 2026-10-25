"""Despertador de UDA: lanza cada reel y el carrusel a su hora sin depender de los programados de GitHub (que llegan
con horas de retraso o no llegan).

Cómo funciona: este trabajo espera dentro de GitHub (un runner puede esperar hasta 6 h) hasta 70 min antes del siguiente
hueco sin publicar (8:00, 12:00 y 15:00 los reels; 18:00 el carrusel; hora de España) y entonces lanza ese workflow
con su hueco. Cuando ese reel o carrusel termina, vuelve a lanzar el despertador para el siguiente. Si el siguiente
hueco está a más de 5 h 30 min, espera ese rato y se relanza a sí mismo. Los lanzamientos manuales (workflow_dispatch)
sí son fiables en GitHub, a diferencia de los programados.

    python despertador.py           # espera y lanza (en GitHub)
    python despertador.py --plan    # solo dice qué haría
"""
import datetime, os, subprocess, sys, time
from zoneinfo import ZoneInfo

import elegir_hueco as E

TZ = ZoneInfo("Europe/Madrid")
OBJETIVOS = [("daily-reels.yml", "manana", 8, 0), ("daily-reels.yml", "mediodia", 12, 0),
             ("daily-reels.yml", "tarde", 15, 0), ("carrusel.yml", "carrusel", 18, 0)]
ANTES = datetime.timedelta(minutes=70)          # el reel se genera antes y espera a la hora exacta
MAX_ESPERA = datetime.timedelta(hours=5, minutes=30)


def proximo(now):
    """(workflow, hueco, hora) del siguiente hueco aún sin publicar."""
    for d in range(3):
        dia = (now + datetime.timedelta(days=d)).date()
        for wf, slot, h, m in OBJETIVOS:
            t = datetime.datetime(dia.year, dia.month, dia.day, h, m, tzinfo=TZ)
            hh, mm = E.HASTA[slot]
            fin = t.replace(hour=hh, minute=mm)
            if now <= fin and not E.publicado(slot, str(dia)):
                return wf, slot, t
    return None


def _git_pull():
    subprocess.run(["git", "pull", "-q", "--rebase"], capture_output=True)


def lanzar(wf, inputs):
    args = ["gh", "workflow", "run", wf, "--ref", "main"] + sum((["-f", f"{k}={v}"] for k, v in inputs.items()), [])
    r = subprocess.run(args, capture_output=True, text=True)
    print("lanzado:", wf, inputs, r.returncode, r.stderr.strip()[:200], flush=True)
    return r.returncode == 0


def main():
    now = datetime.datetime.now(TZ)
    p = proximo(now)
    if not p:
        print("nada pendiente"); return
    wf, slot, t = p
    cuando = t - ANTES
    print(f"siguiente: {slot} a las {t:%d/%m %H:%M} (lanzo a las {cuando:%H:%M})", flush=True)
    if "--plan" in sys.argv:
        return
    espera = (cuando - now).total_seconds()
    if espera > MAX_ESPERA.total_seconds():
        time.sleep(MAX_ESPERA.total_seconds())
        lanzar("despertador.yml", {}); return             # sigue esperando en un trabajo nuevo
    if espera > 0:
        time.sleep(espera)
    _git_pull()                                          # ¿lo ha publicado otro mientras esperaba?
    if E.publicado(slot, str(t.date())):
        print("ya publicado; paso al siguiente"); lanzar("despertador.yml", {}); return
    if wf == "carrusel.yml":
        lanzar(wf, {"dry_run": "false"})
    else:
        lanzar(wf, {"hueco": slot, "dry_run": "false"})


if __name__ == "__main__":
    main()
