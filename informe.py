"""Informe de resultados por tipo de reel (informe_redes.md): qué formato trae más vistas, retiene más y genera más
guardados, compartidos, comentarios y seguidores, con los datos reales de performance.json. Se actualiza solo.
"""
import collections, datetime, json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))


def filas():
    perf = json.load(open(os.path.join(HERE, "performance.json")))
    log = [json.loads(l) for l in open(os.path.join(HERE, "log.jsonl"))]
    tem = {(e["date"], e["slot"], e.get("hook")): (e.get("tematica") or e.get("formato"), e.get("estructura"), e.get("duration")) for e in log}
    out = []
    for k, r in perf.items():
        t, est, dur = tem.get((r.get("date"), r.get("slot"), r.get("hook")), (r.get("formato"), None, None))
        pr = r.get("por_red") or {}
        tt = pr.get("tiktok_video") or {}; ig = pr.get("instagram_reel") or {}; li = pr.get("linkedin_video") or pr.get("linkedin_documento") or {}
        d = tt.get("videoDurationSeconds") or dur or 0
        w = (tt.get("igReelsAvgWatchTime") or 0) / 1000
        out.append({"fecha": r.get("date"), "tema": t or "?", "estructura": est, "hook": r.get("hook") or "",
                    "tt": tt.get("views") or 0, "ig": ig.get("views") or ig.get("reach") or 0, "li": li.get("impressions") or 0,
                    "visto": w, "pct": 100 * w / d if d else 0, "likes": r.get("likes") or 0, "com": r.get("comments") or 0,
                    "sh": r.get("shares") or 0, "sav": r.get("saved") or 0, "fol": r.get("follows") or 0})
    return out


def main():
    R = [r for r in filas() if r["tema"] != "?"]
    hoy = datetime.date.today()
    rec = [r for r in R if r["fecha"] and (hoy - datetime.date.fromisoformat(r["fecha"])).days <= 30]
    by = collections.defaultdict(list)
    for r in rec:
        by[r["tema"]].append(r)
    md = [f"# Resultados por tipo de reel (últimos 30 días · {hoy})", "",
          "| Tipo | Reels | Vistas TikTok (mediana) | Vistas IG (mediana) | Segundos vistos | % visto | Likes | Comentarios | Compartidos | Guardados | Seguidores |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, l in sorted(by.items(), key=lambda x: -st.median([r["tt"] for r in x[1]])):
        s = lambda f: sum(r[f] for r in l)
        m = lambda f: st.median([r[f] for r in l])
        md.append(f"| {t} | {len(l)} | {m('tt'):.0f} | {m('ig'):.0f} | {st.mean([r['visto'] for r in l]):.1f} | {st.mean([r['pct'] for r in l]):.0f} % "
                  f"| {s('likes')} | {s('com')} | {s('sh')} | {s('sav')} | {s('fol')} |")
    md += ["", "## Los 8 mejores (vistas en TikTok)", ""]
    for r in sorted(rec, key=lambda r: -r["tt"])[:8]:
        md.append(f"- {r['fecha']} · **{r['tema']}**{' · ' + r['estructura'] if r['estructura'] else ''} · {r['tt']} vistas · {r['visto']:.1f} s vistos · «{r['hook']}»")
    tot = {f: sum(r[f] for r in rec) for f in ("tt", "ig", "likes", "com", "sh", "sav", "fol")}
    md += ["", f"**Total 30 días:** {tot['tt']} vistas en TikTok · {tot['ig']} en Instagram · {tot['likes']} likes · {tot['com']} comentarios · "
           f"{tot['sh']} compartidos · {tot['sav']} guardados · {tot['fol']} seguidores nuevos", "",
           "_Cómo leerlo: «segundos vistos» es lo que más pesa para que TikTok enseñe un vídeo a más gente; los compartidos y guardados, lo siguiente._"]
    open(os.path.join(HERE, "informe_redes.md"), "w").write("\n".join(md) + "\n")
    print("informe: informe_redes.md actualizado con", len(rec), "reels")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("informe omitido:", str(e)[:200])
