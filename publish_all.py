"""Publica un reel a la vez en todas las redes de UDA vía Zernio (cada destino es independiente: un fallo nunca bloquea
a los demás).

  Instagram   Reel (portada = fotograma del gancho) + Story propia de 12 s que anuncia el reel
  TikTok      el mismo vídeo + la story al buzón como borrador (opcional)
  LinkedIn    todos los reels y el carrusel (variable LINKEDIN = "todos", por defecto); con "carrusel" o un hueco
            ("manana", "mediodia", "tarde") solo eso y nunca más de una publicación al día

Huecos: 8:00, 12:00 y 15:00 (los tres reels completos en Instagram y TikTok); el carrusel va a las 18:00.
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
    morning = False                                    # los tres reels del día van completos a todas las redes
    src = light if (morning or not story) else story
    if os.environ.get("IG_TOKEN"):                    # Instagram directo por la API de Meta (gratis), como en TCAE
        import publish_ig as IG

        def ig_reel():
            cu = None
            if meta.get("cover"):
                try:
                    cu = url(meta["cover"])
                except Exception as e:
                    print("portada sin subir:", str(e)[:150], flush=True)
            try:
                m = IG.publish_reel(light, caption, thumb_ms=meta.get("thumb_ms"), cover_url=cu)
            except Exception as e:
                if not cu:
                    raise
                print("Instagram no acepta la portada; uso el fotograma del gancho:", str(e)[:150], flush=True)
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
        def tt_video():
            cu = None
            if meta.get("cover"):
                try:
                    cu = url(meta["cover"])
                except Exception as e:
                    print("portada de TikTok sin subir:", str(e)[:150], flush=True)
            return Z.tiktok_video(url(light), caption, meta.get("thumb_ms"), cover_url=cu,
                                  ai=meta.get("formato") in ("visual", "render"))       # imágenes de IA: aviso de TikTok
        jobs["tiktok_video"] = tt_video
    if on("TIKTOK_STORY_BORRADOR") and story and not morning:
        jobs["tiktok_story_borrador"] = lambda: Z.tiktok_draft(url(story), caption.split("\n", 1)[0])
    lk = os.environ.get("LINKEDIN", "todos").lower()
    if lk in ("todos", "true"):                       # todos los reels también en LinkedIn (como vídeo nativo)
        jobs["linkedin_video"] = lambda: Z.linkedin_video(url(light), caption)
    elif lk == slot and slot:
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
