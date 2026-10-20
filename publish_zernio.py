"""Instagram, TikTok y LinkedIn a través de Zernio (https://docs.zernio.com). Sin YouTube.

Env: ZERNIO_API_KEY. Seguridad: solo se publica en cuentas cuyo usuario o nombre coincide con ZERNIO_MATCH (por defecto
"uniondearquitectos"), así, aunque en el mismo Zernio estén conectadas otras cuentas (p. ej. @apruebatcae), nunca se
publica en la equivocada. Para fijarlas a mano: ZERNIO_IG_ACCOUNT / ZERNIO_TT_ACCOUNT / ZERNIO_LI_ACCOUNT (ids).

- instagram_reel()      reel con portada en el fotograma del gancho (thumbOffset)
- instagram_story()     story de vídeo (máx. 60 s: se recorta a 59 s)
- instagram_carousel()  carrusel de imágenes (máx. 10)
- tiktok_video()        el reel en TikTok
- tiktok_photos()       carrusel de fotos en TikTok (modo foto)
- tiktok_draft()        la story al buzón de TikTok como borrador (la API de TikTok no publica Stories)
- linkedin_document()   carrusel como documento PDF (el formato de carrusel de LinkedIn)
- linkedin_video()      el reel en LinkedIn
- analytics()           métricas de una publicación (GET /analytics?postId=...)
Cada función es independiente: si una falla, las demás siguen.
"""
import datetime, json, os, re, subprocess, time, unicodedata
import requests

API = "https://zernio.com/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
_ACC = {}
PLATFORMS = {"instagram": "ZERNIO_IG_ACCOUNT", "tiktok": "ZERNIO_TT_ACCOUNT", "linkedin": "ZERNIO_LI_ACCOUNT"}
WEB_URL = "https://uniondearquitectos.com"


def _h():
    return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}"}


def _check(r, what):
    if r.status_code >= 400:
        raise RuntimeError(f"Zernio {what} error {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def _names(a):
    keys = ("username", "handle", "displayName", "name", "platformUsername", "accountName", "profileName", "pageName")
    out = [a.get(k) for k in keys if a.get(k)]
    for k in ("metadata", "profile", "platformData"):
        if isinstance(a.get(k), dict):
            out += [a[k].get(x) for x in keys if a[k].get(x)]
    return [str(x) for x in out]


def accounts(verbose=False):
    """{plataforma: id} solo de las cuentas de UDA (coinciden con ZERNIO_MATCH)."""
    if _ACC:
        return _ACC
    ids = {p: os.environ.get(env) for p, env in PLATFORMS.items()}
    match = _norm(os.environ.get("ZERNIO_MATCH") or os.environ.get("IG_HANDLE", "uniondearquitectos"))
    seen = {}
    if not all(ids.values()):
        data = _check(requests.get(f"{API}/accounts", headers=_h(), timeout=60), "accounts")
        items = data.get("accounts", data if isinstance(data, list) else data.get("data", []))
        for a in items:
            p = (a.get("platform") or "").lower()
            if p not in ids:
                continue
            names = _names(a)
            seen.setdefault(p, []).append(names[0] if names else "?")
            if not ids[p] and any(match in _norm(n) for n in names):
                ids[p] = a.get("_id") or a.get("id")
    _ACC.update({k: v for k, v in ids.items() if v})
    print("Zernio cuentas de UDA:", {k: bool(ids.get(k)) for k in PLATFORMS}, "· conectadas:", seen, flush=True)
    if verbose:
        return _ACC, seen
    return _ACC


def _acc(platform):
    acc = accounts().get(platform)
    if not acc:
        raise RuntimeError(f"no hay cuenta de {platform} de UDA conectada en Zernio (debe llamarse como "
                           f"'{os.environ.get('ZERNIO_MATCH', 'uniondearquitectos')}' o fija su id en {PLATFORMS[platform]})")
    return acc


def upload(path):
    """Sube un archivo a Zernio y devuelve su URL pública."""
    ct = {"mp4": "video/mp4", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
          "pdf": "application/pdf"}[path.rsplit(".", 1)[-1].lower()]
    for attempt in range(3):
        try:
            pre = _check(requests.post(f"{API}/media/presign", headers=_h(), json={
                "filename": os.path.basename(path), "contentType": ct, "size": os.path.getsize(path)}, timeout=60), "presign")
            with open(path, "rb") as f:
                up = requests.put(pre["uploadUrl"], data=f, headers={"Content-Type": ct}, timeout=600)
            if up.status_code >= 400:
                raise RuntimeError(f"Zernio subida {up.status_code}: {up.text[:300]}")
            return pre["publicUrl"]
        except Exception as e:
            if attempt == 2:
                raise
            print("Zernio subida, reintento:", str(e)[:150], flush=True); time.sleep(10 * (attempt + 1))


def _post(body, what):
    for attempt in range(3):
        try:
            res = _check(requests.post(f"{API}/posts", headers=_h(), json=body, timeout=180), what)
            pid = (res.get("post") or res).get("_id") if isinstance(res, dict) else None
            print(f"Zernio {what}: creado {pid}", flush=True)
            return pid or "ok"
        except RuntimeError as e:
            if " 4" in str(e)[:25] and " 429" not in str(e)[:25]:      # error de datos: no sirve reintentar
                raise
            if attempt == 2:
                raise
            time.sleep(15 * (attempt + 1))


# ------------------------------------------------------------------ vídeo apto para todas las redes
def ig_safe(video_path):
    """Los reels ya salen ligeros (720x1280, ~2,5 Mbps, AAC 48 kHz, faststart). Si algo pesa más de 40 MB, se recodifica."""
    if os.path.getsize(video_path) <= 40e6:
        return video_path
    out = video_path.replace(".mp4", "_ig.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_path, "-vf", "scale=720:1280",
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "25", "-preset", "veryfast",
                    "-crf", "23", "-maxrate", "2500k", "-bufsize", "5000k", "-g", "50",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", "-use_editlist", "0", out], check=True)
    return out


def story_safe(path, limit=59.0):
    """Las Stories de Instagram admiten 60 s como máximo: lo más largo se corta a 59 s con un fundido."""
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout.strip() or 0)
    if d <= limit:
        return path
    out = path.replace(".mp4", "_59s.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-t", str(limit),
                    "-vf", f"fade=t=out:st={limit - 0.8}:d=0.8", "-af", f"afade=t=out:st={limit - 0.8}:d=0.8",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
                    "-use_editlist", "0", out], check=True)
    return out


# ------------------------------------------------------------------ textos por red
def _tt_text(caption):
    """En TikTok el enlace de la bio no es clicable hasta tener seguidores suficientes: se nombra la web tal cual."""
    return (caption.replace(" (link en la bio)", "").replace("(link en la bio)", "")
            .replace("link en la bio", "uniondearquitectos.com"))[:2150]


def li_text(caption):
    """LinkedIn: enlace real a la web, sin "link en la bio" y con 3 hashtags como mucho."""
    t = caption.replace("uniondearquitectos.com (link en la bio)", WEB_URL).replace(" (link en la bio)", "")
    t = t.replace("(link en la bio)", "").replace("link en la bio", WEB_URL)
    tags = re.findall(r"#\w+", t)
    for tag in tags[3:]:
        t = t.replace(" " + tag, "").replace(tag, "")
    return t.strip()[:2950]


# ------------------------------------------------------------------ Instagram
def instagram_reel(video_url, caption, thumb_ms=1200):
    return _post({"content": caption[:2200], "mediaItems": [{"type": "video", "url": video_url}], "publishNow": True,
                  "platforms": [{"platform": "instagram", "accountId": _acc("instagram"),
                                 "platformSpecificData": {"shareToFeed": True, "thumbOffset": int(thumb_ms or 1000)}}]},
                 "instagram reel")


def instagram_story(video_url):
    return _post({"content": "", "mediaItems": [{"type": "video", "url": video_url}], "publishNow": True,
                  "platforms": [{"platform": "instagram", "accountId": _acc("instagram"),
                                 "platformSpecificData": {"contentType": "story"}}]}, "instagram story")


def instagram_carousel(image_urls, caption):
    return _post({"content": caption[:2200], "mediaItems": [{"type": "image", "url": u} for u in image_urls[:10]],
                  "publishNow": True, "platforms": [{"platform": "instagram", "accountId": _acc("instagram")}]},
                 "instagram carrusel")


# ------------------------------------------------------------------ TikTok
def tiktok_video(video_url, caption, cover_ms=1200):
    return _post({"content": _tt_text(caption), "mediaItems": [{"type": "video", "url": video_url}], "publishNow": True,
                  "platforms": [{"platform": "tiktok", "accountId": _acc("tiktok")}],
                  "tiktokSettings": {"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True, "allow_duet": True,
                                     "allow_stitch": True, "content_preview_confirmed": True, "express_consent_given": True,
                                     "video_cover_timestamp_ms": int(cover_ms or 1000)}}, "tiktok vídeo")


def tiktok_photos(image_urls, title, description):
    return _post({"content": title[:90], "mediaItems": [{"type": "image", "url": u} for u in image_urls[:35]], "publishNow": True,
                  "platforms": [{"platform": "tiktok", "accountId": _acc("tiktok")}],
                  "tiktokSettings": {"media_type": "photo", "photo_cover_index": 0, "description": _tt_text(description)[:3900],
                                     "auto_add_music": True, "privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True,
                                     "content_preview_confirmed": True, "express_consent_given": True}}, "tiktok carrusel")


def tiktok_draft(video_url, caption):
    return _post({"content": _tt_text(caption)[:300], "mediaItems": [{"type": "video", "url": video_url}], "publishNow": True,
                  "platforms": [{"platform": "tiktok", "accountId": _acc("tiktok")}],
                  "tiktokSettings": {"draft": True, "privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True,
                                     "content_preview_confirmed": True, "express_consent_given": True}}, "tiktok borrador story")


# ------------------------------------------------------------------ LinkedIn (máximo una publicación al día)
def linkedin_used_today():
    """True si hoy ya se publicó algo en LinkedIn (reels en log.jsonl o carrusel en carruseles.json)."""
    today = str(datetime.date.today())
    try:
        for line in open(os.path.join(HERE, "log.jsonl")):
            e = json.loads(line)
            if e.get("date") == today and any(k.startswith("linkedin") and not str(v).startswith("error")
                                              for k, v in (e.get("publicado") or {}).items()):
                return True
    except Exception:
        pass
    try:
        for e in json.load(open(os.path.join(HERE, "carruseles.json"))):
            if e.get("fecha") == today and any(k.startswith("linkedin") and not str(v).startswith("error")
                                               for k, v in (e.get("destinos") or {}).items()):
                return True
    except Exception:
        pass
    return False


def _li(body_media, text, what, psd=None):
    entry = {"platform": "linkedin", "accountId": _acc("linkedin")}
    if psd:
        entry["platformSpecificData"] = psd
    org = os.environ.get("LINKEDIN_ORG_URN")                  # opcional: publicar como página de empresa concreta
    if org:
        entry.setdefault("platformSpecificData", {})["organizationUrn"] = org
    return _post({"content": li_text(text), "mediaItems": body_media, "publishNow": True, "platforms": [entry]}, what)


def linkedin_document(pdf_url, text, title):
    return _li([{"type": "document", "url": pdf_url, "title": title[:100]}], text, "linkedin documento",
               {"documentTitle": title[:100]})


def linkedin_video(video_url, text):
    return _li([{"type": "video", "url": video_url}], text, "linkedin vídeo")


# ------------------------------------------------------------------ analíticas
def analytics(post_id):
    """{"analytics": {...}, "platformAnalytics": [...]} de una publicación, o None si aún no hay datos."""
    r = requests.get(f"{API}/analytics", headers=_h(), params={"postId": post_id}, timeout=60)
    if r.status_code == 202:
        return None
    return _check(r, "analytics")
