"""Copia a TikTok un reel ya publicado (reutiliza el vídeo que se subió para LinkedIn o Instagram vía Zernio).

    python copiar_a_tiktok.py            # el último reel de hoy que no esté en TikTok
    python copiar_a_tiktok.py <postId>   # el reel de esa publicación de Zernio (LinkedIn)
Anota el resultado en log.jsonl.
"""
import datetime, json, os, sys

import requests

import publish_zernio as Z

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "log.jsonl")


def main():
    filas = [json.loads(l) for l in open(LOG)]
    hoy = str(datetime.date.today())
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    k = None
    for i in range(len(filas) - 1, -1, -1):
        e = filas[i]; pub = e.get("publicado") or {}
        if pid and pid in map(str, pub.values()) or (not pid and e.get("date") == hoy and "tiktok_video" not in pub
                                                         and str(pub.get("linkedin_video", "error")).find("error") < 0):
            k = i; break
    if k is None:
        raise SystemExit("No hay reel que copiar")
    e = filas[k]; li = str(e["publicado"]["linkedin_video"])
    r = requests.get(f"{Z.API}/posts/{li}", headers=Z._h(), timeout=60); r.raise_for_status()
    post = r.json().get("post") or r.json()
    video = next(m["url"] for m in post.get("mediaItems", []) if m.get("type") == "video")
    caption = post.get("content") or e.get("hook") or ""
    ai = e.get("estilo") != "portfolio" and e.get("formato") in ("visual", "render")
    print("copio a TikTok:", e.get("hook"), video[:80], flush=True)
    res = Z.tiktok_video(video, caption, 2500, ai=ai)
    e.setdefault("publicado", {})["tiktok_video"] = res
    open(LOG, "w").write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in filas))
    print("TikTok:", res)


if __name__ == "__main__":
    main()
