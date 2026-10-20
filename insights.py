"""Resultados reales de cada publicación -> performance.json (con ellos aprenden el piloto automático, los agentes y el
revisor). Se leen de Zernio (GET /analytics?postId=...) para Instagram, TikTok y LinkedIn: no hace falta token de Meta.

Cada reel (o carrusel) es una fila: se suman las métricas de todas sus publicaciones (reel de Instagram, TikTok,
LinkedIn; las stories y los borradores no cuentan). Se actualiza desde las 12 h hasta los 120 días de vida.
"""
import datetime, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PERF = os.path.join(HERE, "performance.json")
SKIP = ("story", "borrador")
MAP = {"views": "views", "impressions": "impressions", "reach": "reach", "likes": "likes", "comments": "comments",
       "shares": "shares", "saves": "saved", "saved": "saved", "clicks": "clicks", "follows": "follows",
       "profile_views": "profile_visits", "profileViews": "profile_visits", "website_clicks": "clicks"}
WATCH = ("ig_reels_avg_watch_time", "igReelsAvgWatchTime", "avgWatchTime", "averageWatchTime")


def _entries():
    out = []
    try:
        for line in open(os.path.join(HERE, "log.jsonl")):
            e = json.loads(line)
            if e.get("publicado"):
                out.append((f"{e['date']}_{e.get('slot')}", e))
    except Exception:
        pass
    try:
        for e in json.load(open(os.path.join(HERE, "carruseles.json"))):
            if e.get("destinos"):
                out.append((f"{e['fecha']}_carrusel", {"date": e["fecha"], "slot": "carrusel", "formato": "carrusel",
                                                       "hook": e.get("titulo"), "temas": [e.get("tema")],
                                                       "publicado": e["destinos"]}))
    except Exception:
        pass
    return out


def update(days=120):
    if not os.environ.get("ZERNIO_API_KEY") and not os.environ.get("IG_TOKEN"):
        return "insights: sin ZERNIO_API_KEY ni IG_TOKEN"
    import publish_zernio as Z
    perf = json.load(open(PERF)) if os.path.exists(PERF) else {}
    today = datetime.date.today(); n_ok = n_wait = n_err = 0
    for key, e in _entries():
        try:
            age = (today - datetime.date.fromisoformat(e["date"])).days
        except Exception:
            continue
        if age > days or age < 1 and datetime.datetime.utcnow().hour < 20:
            continue
        tot, per = {}, {}
        for dest, pid in (e.get("publicado") or {}).items():
            if any(s in dest for s in SKIP) or str(pid).startswith("error") or pid in ("ok", "None", None):
                continue
            if str(pid).startswith("ig:"):                # publicado directo en Instagram: métricas de la API de Meta
                try:
                    import publish_ig as IG
                    m = IG.media_insights(str(pid)[3:])
                    m["saves"] = m.pop("saved", None)
                    a = {"analytics": {k: v for k, v in m.items() if v is not None}}
                except Exception as err:
                    n_err += 1; print("insights IG:", str(err)[:120], flush=True); continue
            else:
                try:
                    a = Z.analytics(pid)
                except Exception as err:
                    n_err += 1; print("insights:", dest, str(err)[:120], flush=True); continue
            if not a:
                n_wait += 1; continue
            m = dict(a.get("analytics") or {})
            for pa in a.get("platformAnalytics") or []:
                for k in WATCH:
                    if (pa.get("analytics") or {}).get(k) is not None:
                        m["ig_reels_avg_watch_time"] = pa["analytics"][k]
            for k in WATCH:
                if m.get(k) is not None:
                    m["ig_reels_avg_watch_time"] = m[k]
            per[dest] = {MAP.get(k, k): v for k, v in m.items() if isinstance(v, (int, float))}
            for k, v in m.items():
                if k in MAP and isinstance(v, (int, float)):
                    tot[MAP[k]] = tot.get(MAP[k], 0) + v
            if per[dest].get("ig_reels_avg_watch_time"):
                tot["ig_reels_avg_watch_time"] = per[dest]["ig_reels_avg_watch_time"]
        if not per:
            continue
        n_ok += 1
        base = {k: e.get(k) for k in ("slot", "formato", "estilo", "series", "imagen", "voice_speed", "music", "temas",
                                      "hook", "guion", "review_score", "arms")}
        perf[key] = {**base, "date": e["date"], **tot, "por_red": per}
    json.dump(perf, open(PERF, "w"), ensure_ascii=False, indent=0)
    return f"insights: {n_ok} publicaciones con datos de Zernio ({n_wait} aún sin datos, {n_err} errores)"


def recent_comments(days=14):
    """Comentarios recientes (anónimos). Zernio no los da en esta versión: el agente de comunidad trabaja sin ellos."""
    return []


if __name__ == "__main__":
    print(update())
