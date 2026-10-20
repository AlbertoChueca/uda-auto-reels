"""Publica un reel a la vez en todas las redes de UDA vía Zernio (cada destino es independiente: un fallo nunca bloquea
a los demás).

  Instagram   Reel (portada = fotograma del gancho) + Story propia de 12 s que anuncia el reel
  TikTok      el mismo vídeo + la story al buzón como borrador (opcional)
  LinkedIn    el reel, solo en el hueco elegido con la variable LINKEDIN y nunca más de una publicación al día

Hueco "manana" (8:00): el reel va a TikTok y, en Instagram, el reel completo como story (sin post en el feed, para no
quitar alcance a los de las 14:30 y las 21:30).
Interruptores (Settings > Secrets and variables > Actions > Variables): IG_STORY, TIKTOK, TIKTOK_STORY_BORRADOR:
"true", "false" o el hueco en el que actúan ("manana" / "mediodia" / "noche"). LINKEDIN: "carrusel" (por defecto: el
carrusel diario va a LinkedIn), "manana" / "mediodia" / "noche" (ese reel va a LinkedIn) o "false".
"""
import os, threading
from concurrent.futures import ThreadPoolExecutor

SLOT = [""]


def on(name, default="true"):
    """"true"/"false", o el nombre de un hueco ("mediodia"/"noche") para activarlo solo en ese hueco."""
    v = os.environ.get(name, default).lower()
    return v == "true" or (v == SLOT[0] and v != "")


def publish(reel, story, caption, meta, slot=""):
    """Devuelve {destino: id de la publicación en Zernio o 'error: ...'}."""
    SLOT[0] = slot
    if not os.environ.get("ZERNIO_API_KEY") and not os.environ.get("IG_TOKEN"):
        return {"zernio": "error: faltan los secretos ZERNIO_API_KEY e IG_TOKEN"}
    import publish_zernio as Z
    urls, lock, jobs, res = {}, threading.Lock(), {}, {}

    def url(path):                       # cada archivo se sube una sola vez (aunque lo pidan dos destinos a la vez)
        with lock:
            if path not in urls:
                urls[path] = Z.upload(path)
            return urls[path]
    light = Z.ig_safe(reel)
    morning = slot == "manana"
    src = light if (morning or not story) else story
    if os.environ.get("IG_TOKEN"):                    # Instagram directo por la API de Meta (gratis), como en TCAE
        import publish_ig as IG

        def ig_reel():
            m = IG.publish_reel(light, caption, thumb_ms=meta.get("thumb_ms"))
            meta["permalink"] = m.get("permalink")
            return f"ig:{m['id']}"
        if not morning:
            jobs["instagram_reel"] = ig_reel
        if on("IG_STORY") or morning:
            jobs["instagram_story"] = lambda: f"ig:{IG.publish_story(Z.story_safe(src)).get('id')}"
    else:                                             # o por Zernio, si la cuenta está conectada allí
        if not morning:
            jobs["instagram_reel"] = lambda: Z.instagram_reel(url(light), caption, meta.get("thumb_ms"))
        if on("IG_STORY") or morning:
            jobs["instagram_story"] = lambda: Z.instagram_story(url(Z.story_safe(src)))
    if on("TIKTOK"):
        jobs["tiktok_video"] = lambda: Z.tiktok_video(url(light), caption, meta.get("thumb_ms"))
    if on("TIKTOK_STORY_BORRADOR") and story and not morning:
        jobs["tiktok_story_borrador"] = lambda: Z.tiktok_draft(url(story), caption.split("\n", 1)[0])
    if os.environ.get("LINKEDIN", "carrusel").lower() == slot and slot:
        if Z.linkedin_used_today():
            print("LinkedIn: hoy ya hay una publicación; no se publica otra", flush=True)
        else:
            jobs["linkedin_video"] = lambda: Z.linkedin_video(url(light), caption)
    with ThreadPoolExecutor(max(1, len(jobs))) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        for k, f in futs.items():
            try:
                res[k] = str(f.result(timeout=1500))
            except Exception as e:
                res[k] = f"error: {str(e)[:200]}"
                print(f"publicación {k} fallida:", str(e)[:300], flush=True)
    return res
