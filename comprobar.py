"""Chequeo de salud (workflow "Comprobar conexiones", cada lunes y a mano): ¿está todo listo para publicar?

Revisa Zernio (cuentas de UDA en Instagram, TikTok y LinkedIn), Gemini, el banco de piezas (publicables por bloque,
días de reserva), las fuentes (BOE, documentos y web de UDA) y cómo fueron las publicaciones de la última semana
(incluido que LinkedIn no pase de una al día). Escribe estado.md y, si algo crítico falla, termina con error para que
GitHub te avise por correo.
"""
import datetime, json, os, sys

import questions as QB

rows, critical = [], []


def ok(name, good, detail, crit=False):
    rows.append(f"| {'✅' if good else ('❌' if crit else '⚠️')} {name} | {detail} |")
    if not good and crit:
        critical.append(name)


# ---- Zernio (Instagram, TikTok, LinkedIn)
if os.environ.get("ZERNIO_API_KEY"):
    try:
        import publish_zernio as Z
        acc, seen = Z.accounts(verbose=True)
        for p, label in (("instagram", "Instagram"), ("tiktok", "TikTok"), ("linkedin", "LinkedIn")):
            if p == "instagram" and os.environ.get("IG_TOKEN"):
                continue                                   # Instagram va directo por la API de Meta (abajo)
            other = ", ".join(seen.get(p, [])) or "ninguna"
            ok(f"{label} (Zernio)", p in acc, "conectada (@uniondearquitectos)" if p in acc else
               f"no hay cuenta de UDA (conectadas en Zernio: {other}); conéctala o fija {Z.PLATFORMS[p]}", p == "instagram")
    except Exception as e:
        ok("Zernio", False, f"error: {str(e)[:150]}", True)
else:
    ok("Zernio", False, "falta el secreto ZERNIO_API_KEY: no se publica nada", True)

# ---- Instagram directo (API de Meta, gratis)
if os.environ.get("IG_TOKEN"):
    try:
        from publish_ig import whoami
        me = whoami(os.environ["IG_TOKEN"])
        ok("Instagram (API de Meta)", True, f"@{me['username']} · publica directo, sin Zernio")
    except Exception as e:
        ok("Instagram (API de Meta)", False, f"token no válido: {str(e)[:160]}", True)

# ---- Gemini
if os.environ.get("GEMINI_API_KEY"):
    try:
        import gemini
        av = gemini.available()
        tts = [m for m in av if "tts" in m]; img = [m for m in av if "image" in m]
        gemini.ask('Devuelve JSON {"ok": true}', 0)
        ok("Gemini texto", True, f"{len(av)} modelos disponibles")
        ok("Gemini voz", bool(tts), ", ".join(tts[:3]) or "sin modelos TTS: se usará la voz de respaldo")
        try:
            import voice
            a = voice._google_line("Hola, somos Unión de Arquitectos.", os.environ["GEMINI_API_KEY"])
            ok("Voz de España (Google Cloud TTS)", True, f"{voice.GOOGLE_TTS_VOICE} · {len(a) / voice.SR:.1f} s de audio")
        except Exception as e:
            ok("Voz de España (Google Cloud TTS)", False, "no disponible: activa la «Cloud Text-to-Speech API» en el proyecto de "
               f"Google Cloud de tu clave (se usa Gemini mientras tanto) · {str(e)[:200]}")
        ok("Gemini imagen", bool(img), ", ".join(img[:3]) or "sin modelos de imagen: reels sin ilustración")
    except Exception as e:
        ok("Gemini", False, f"error: {str(e)[:150]}", True)
else:
    ok("Gemini", False, "falta GEMINI_API_KEY (sin ella no se verifica nada y no se publica)", True)

# ---- banco
pub, pend = QB.stock()
total = sum(pub.values())
ok("Banco verificado", total >= 40, f"{total} piezas publicables sin usar ({', '.join(f'{k} {n}' for k, n in pub.items())}) · "
   f"{sum(pend.values())} pendientes de verificar · ~{total // 4} días de reserva"
   + ("" if total >= 40 else " · lanza 'Generar banco'"), total < 6)
for b in ("negocio", "contratar", "servicios", "proyecto"):
    ok(f"Piezas de {b}", pub[b] >= 3, f"{pub[b]} publicables" + ("" if pub[b] >= 3 else " · lanza 'Generar banco'"))
try:
    cfg = json.load(open("fuentes/fuentes.json"))["normas"]
    have = [k for k, n in cfg.items() if os.path.exists(os.path.join("fuentes", n["archivo"]))]
    falt = [n.get("corto", n["titulo"]) for k, n in cfg.items() if k not in have]
    ok("Fuentes", len(have) >= len(cfg) - 3, f"{len(have)}/{len(cfg)}" + (f" · faltan: {'; '.join(falt[:6])} (lanza 'Descargar fuentes')" if falt else ""))
except Exception as e:
    ok("Fuentes", False, str(e)[:100])

# ---- última semana
week = str(datetime.date.today() - datetime.timedelta(days=7))
stats, li_days = {}, {}


def count(day, pub_):
    for k, r in (pub_ or {}).items():
        good = not str(r).startswith("error")
        stats.setdefault(k, [0, 0])[0 if good else 1] += 1
        if k.startswith("linkedin") and good:
            li_days[day] = li_days.get(day, 0) + 1


try:
    for line in open("log.jsonl"):
        e = json.loads(line)
        if e.get("date", "") >= week:
            count(e["date"], e.get("publicado"))
except Exception:
    pass
try:
    for e in json.load(open("carruseles.json")):
        if e.get("fecha", "") >= week:
            count(e["fecha"], e.get("destinos"))
except Exception:
    pass
ok("Publicaciones (7 días)", bool(stats) and all(b == 0 for _, b in stats.values()),
   " · ".join(f"{k}: {a} ok / {b} fallos" for k, (a, b) in stats.items()) or "aún no hay publicaciones")
ok("LinkedIn (máx. 1 al día)", all(n <= 1 for n in li_days.values()),
   f"{sum(li_days.values())} publicaciones en {len(li_days)} días" if li_days else "sin publicaciones esta semana")

# ---- estado REAL en TikTok y LinkedIn de las últimas publicaciones (Zernio: creado ≠ publicado)
det = []
if os.environ.get("ZERNIO_API_KEY"):
    import requests, publish_zernio as Z
    ids = []
    try:
        for line in open("log.jsonl"):
            e = json.loads(line)
            for k, v in (e.get("publicado") or {}).items():
                if not str(v).startswith(("ig:", "error")) and v not in ("ok", None):
                    ids.append((e.get("date"), k, v))
    except Exception:
        pass
    try:
        for e in json.load(open("carruseles.json")):
            for k, v in (e.get("destinos") or {}).items():
                if not str(v).startswith(("ig:", "error")) and v not in ("ok", None):
                    ids.append((e.get("fecha"), "carrusel_" + k, v))
    except Exception:
        pass
    for d, k, pid in ids[-12:]:
        try:
            r = requests.get(f"{Z.API}/posts/{pid}", headers=Z._h(), timeout=60)
            j = r.json(); p = j.get("post") or j
            pl = [(x.get("platform"), x.get("status"), (x.get("errorMessage") or x.get("error") or "")[:160],
                   x.get("platformPostUrl") or "") for x in p.get("platforms") or []]
            det.append(f"| {d} · {k} | {p.get('status')} · " + " · ".join(f"{a}: {b} {c} {u}".strip() for a, b, c, u in pl) + " |")
        except Exception as e:
            det.append(f"| {d} · {k} | no se pudo consultar: {str(e)[:100]} |")
if det:
    rows.append("| **Publicaciones en Zernio (estado real)** | |")
    rows.extend(det)

txt = f"# Estado ({datetime.date.today()})\n\n| comprobación | detalle |\n|---|---|\n" + "\n".join(rows) + "\n"
open("estado.md", "w").write(txt); print(txt)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(txt)
if critical:
    sys.exit("Problemas críticos: " + ", ".join(critical))
