"""Productor/revisor: mejora el gancho del guion, revisa el vídeo terminado y actúa como director de arte.

  1. improve_script(): reescribe SOLO lo que no es dato (texto grande, primera frase, primera línea de la descripción,
     invitación a comentar y cierre) para que enganche más, usando lo que mejor ha funcionado (performance.json).
     Los textos con datos (explicación, trampa, truco, mito, puntos) no los toca: esos los aprueba el verificador.
  2. art_direct(): mira fotogramas reales (gancho, pregunta, revelado, explicación, cierre) y ajusta tokens de diseño seguros.
  3. review_video(): ve el reel terminado (copia pequeña), lo puntúa, pule la primera línea de la descripción y lo rechaza
     solo si está claramente roto (entonces se vuelve a generar).
Todo queda en review_log.jsonl. Cualquier error del revisor se ignora: el reel sigue con la versión original.
"""
import base64, datetime, io, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW_LOG = os.path.join(HERE, "review_log.jsonl")
PERF = os.path.join(HERE, "performance.json")
MIN_SCORE = float(os.environ.get("REVIEW_MIN_SCORE", "8"))       # nivel premium: por debajo de 8 no se publica

PRODUCER = """Eres productora sénior de vídeos cortos profesionales (Reels, TikTok, LinkedIn) para UDA · Unión de Arquitectos,
un estudio online que hace de departamento técnico externo para arquitectos autónomos y despachos de España (Proyectos
Básicos y de Ejecución, CAD o Revit, precio cerrado, la firma es del despacho). Público: despachos y arquitectos autónomos de España que proyectan bloques de viviendas, promociones, conjuntos residenciales y edificios de envergadura (equipamientos, naves, rehabilitaciones de edificios completos):
expertos, exigentes y con poco tiempo. El nivel tiene que ser PREMIUM: un 8 o más en tu escala es el mínimo para publicar. Objetivos, por orden: rigor (nada falso), claridad inmediata, que los 2 primeros segundos
frenen el scroll, que comenten, GUARDEN el reel para su próximo proyecto, lo envíen a un socio y visiten
uniondearquitectos.com. Tono de colega a colega, profesional, directo y con gancho; estética editorial y sobria; sin
promesas ni estadísticas inventadas."""


class RejectReel(RuntimeError):
    """El reel terminado está claramente roto; hay que generarlo de nuevo."""


def _log(kind, data):
    try:
        with open(REVIEW_LOG, "a") as f:
            f.write(json.dumps({"date": str(datetime.date.today()), "kind": kind, **data}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _ask(parts, temperature=0.6):
    import gemini
    return gemini.ask(parts, temperature)


def _jpeg_b64(im, size=512):
    im = im.copy(); im.thumbnail((size, size))
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=80)
    return base64.b64encode(b.getvalue()).decode()


def learnings():
    try:
        perf = json.load(open(PERF))
    except Exception:
        perf = {}
    import strategy
    pb = strategy.playbook_text()
    rows = [r for r in perf.values() if r.get("views")]
    if len(rows) < 4:
        return pb
    rows.sort(key=lambda r: strategy.reward(r) or 0, reverse=True)

    def line(r):
        return (f'- "{r.get("hook")}" ({r.get("formato")}, {r.get("temas")}): {r["views"]} views, {r.get("saved")} guardados, '
                f'{r.get("shares")} compartidos, {r.get("comments")} comentarios, visionado medio {r.get("ig_reels_avg_watch_time", "?")} ms')
    return (f"RESULTADOS REALES ({len(rows)} reels):\nMejores:\n" + "\n".join(map(line, rows[:3])) + "\nPeores:\n"
            + "\n".join(map(line, rows[-3:])) + "\nRepite lo que tienen en común los mejores; evita lo de los peores."
            + (("\n\n" + pb) if pb else ""))


# ------------------------------------------------------------------ 1. guion (solo partes que no son dato)
def improve_script(S, fmt, items, arms=None):
    try:
        import agents
        P = items[0]
        res = _ask([{"text": f"""{PRODUCER}

{agents._brief('gancho')}

{learnings()}
Experimento de hoy: estilo de gancho = {(arms or {}).get('hook_style', 'libre')} (mantenlo).
Formato: {fmt}. {__import__('estudio')._desc(items)}
Borrador (JSON): {json.dumps({k: S.get(k) for k in ('screen_hook', 'hook_line', 'caption_hook', 'comment_prompt', 'cta_line')}, ensure_ascii=False)}

Puntúa 1-10 el gancho (2 primeros segundos), la claridad y la invitación a comentar/guardar. Después mejora SOLO estos
campos, sin añadir ningún dato nuevo del temario: screen_hook (2-6 palabras, sin emojis), hook_line (5-14 palabras,
hablado, no repite el screen_hook), caption_hook (máx. 12 palabras, máx. 1 emoji), comment_prompt (máx. 12 palabras),
cta_line (10-22 palabras, debe nombrar uniondearquitectos.com y solo hechos ciertos de UDA: delegar el proyecto,
presupuesto cerrado en 24–72 horas, tu firma al final). Español de España, de colega a colega, sin promesas.
Devuelve JSON: {{"overall": number, "changes": [str], "screen_hook": str, "hook_line": str, "caption_hook": str,
"comment_prompt": str, "cta_line": str}}"""}], 0.7)
        import writer
        new = dict(S)
        for k, lo, hi in (("screen_hook", 2, 6), ("hook_line", 4, 16), ("caption_hook", 3, 14), ("comment_prompt", 3, 14),
                          ("cta_line", 8, 24)):
            v = writer._w(res.get(k), lo, hi)
            if v and not re.search(r"\d+ ?%", v):
                new[k] = v
        new["screen_hook"] = re.sub(r"[^\w\s¿?¡!,.:'-]", "", new["screen_hook"]).strip()
        if "uniondearquitectos" not in new["cta_line"].lower().replace(" ", ""):
            new["cta_line"] = S["cta_line"]
        _log("script", {"formato": fmt, "overall": res.get("overall"), "changes": res.get("changes"),
                        "before": S.get("screen_hook"), "after": new.get("screen_hook")})
        print(f"revisor: guion {res.get('overall')}/10 -> gancho {new['screen_hook']!r}", flush=True)
        return new
    except Exception as e:
        print("revisor: revisión de guion omitida:", str(e)[:200], flush=True)
        return S


# ------------------------------------------------------------------ 2. director de arte
ART_DIRECTOR = """Eres DIRECTORA DE ARTE y JEFA DE TEXTOS de un canal educativo de primer nivel. Revisas fotogramas reales de
un reel vertical antes de publicarlo. Realidad del móvil: la interfaz de Instagram/TikTok tapa ~250 px arriba, ~420 px
abajo (descripción, usuario, música) y una columna de botones a la derecha; lo importante ahí se pierde."""


def _frames(path, times):
    from PIL import Image
    out = []
    for t in times:
        f = path.replace(".mp4", f"_f{t:.1f}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, t):.2f}", "-i", path, "-frames:v", "1", f], check=False)
        if os.path.exists(f):
            out.append((t, Image.open(f).convert("RGB"))); os.remove(f)
    return out


def art_direct(path, S, style, timeline, total):
    """Devuelve (nuevo_estilo o None, informe). Solo puede tocar tokens seguros: nunca rompe el reel."""
    try:
        times = []
        for i, (k, a) in enumerate(timeline):
            b = timeline[i + 1][1] if i + 1 < len(timeline) else total
            if k in ("hook", "question", "statement", "reveal", "explain", "points", "cta"):
                times.append(a + (b - a) * 0.7)
        fr = _frames(path, times[:8])
        import agents
        parts = [{"text": f"""{ART_DIRECTOR}
{agents._brief('diseno')}

Fotogramas (en orden) del reel de hoy. Gancho: "{S.get('screen_hook')}". Tokens actuales:
{json.dumps({k: style.get(k) for k in ('screen_hook', 'caption_scale', 'follow_line', 'share_line')}, ensure_ascii=False)}

Puntúa 1-10: gancho en pantalla, calidad de los textos (cortos, claros, tono profesional), tipografía y legibilidad en el móvil,
todo dentro de la zona segura, acabado profesional, claridad de la pregunta y de la respuesta correcta, fuerza de la
tarjeta final (seguir + compartir + web), probabilidad de que lo guarden.
Propón mejoras SOLO con estos tokens (omite los que no cambies):
- screen_hook: 2-6 palabras, sin emojis, sin datos nuevos (se muestra grande al principio)
- caption_scale: 0.85-1.2 (tamaño de subtítulos)
- follow_line: máx. 6 palabras (tarjeta final, invita a seguir)
- share_line: máx. 7 palabras (tarjeta final, invita a enviarlo a un socio o compañero de despacho)
Devuelve JSON: {{"overall": number, "scores": {{...}}, "issues": [str], "changes": {{token: valor}}, "why": [str]}}"""}]
        for t, im in fr:
            parts.append({"text": f"fotograma en {t:.1f}s"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(im, 540)}})
        res = _ask(parts, 0.4)
    except Exception as e:
        print("director de arte omitido:", str(e)[:200], flush=True)
        return None, {}
    ch = res.get("changes") or {}
    new = dict(style)

    def words(v, n):
        v = re.sub(r"[^\w\s¿?¡!,.:'-]", "", str(v or "")).strip()
        return v if 1 <= len(v.split()) <= n else None
    if words(ch.get("screen_hook"), 6) and not re.search(r"\d", ch["screen_hook"]): new["screen_hook"] = words(ch["screen_hook"], 6)
    if words(ch.get("follow_line"), 6): new["follow_line"] = words(ch["follow_line"], 6)
    if words(ch.get("share_line"), 7): new["share_line"] = words(ch["share_line"], 7)
    try:
        if ch.get("caption_scale") is not None:
            new["caption_scale"] = round(min(1.2, max(0.85, float(ch["caption_scale"]))), 2)
    except Exception:
        pass
    overall = float(res.get("overall") or 0)
    _log("design", {"hook": S.get("screen_hook"), "overall": overall, "scores": res.get("scores"), "issues": res.get("issues"),
                    "changes": {k: v for k, v in new.items() if style.get(k) != v}, "why": res.get("why")})
    print(f"director de arte: {overall}/10" + (f" - {'; '.join((res.get('issues') or [])[:3])}" if res.get("issues") else ""), flush=True)
    # volver a renderizar cuesta varios minutos de GitHub: solo si el diseño flojea de verdad
    if new == style or overall >= float(os.environ.get("ART_RERENDER_BELOW", "8")):
        return None, {"overall": overall}
    return new, {"overall": overall}


# ------------------------------------------------------------------ 3. vídeo terminado
def review_video(path, S, caption):
    small = path.replace(".mp4", "_review.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "scale=360:640", "-r", "12",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "48k", small], check=True)
        data = base64.b64encode(open(small, "rb").read()).decode()
        first, rest = (caption.split("\n", 1) + [""])[:2]
        res = _ask([{"text": f"""{PRODUCER}
Mira este reel terminado (3 claves, comparativa a dos columnas, dato de proyecto, mito o caso de despacho; cierre con la marca).
Debe sentirse PREMIUM y elegante, para fundadores de despachos: ni repaso de examen ni anuncio de teletienda. Gancho: {S.get('screen_hook')!r}.
Primera línea actual de la descripción: {first!r}

Puntúa 1-10: gancho en 1,5 s, claridad, ritmo (ni lento ni atropellado), voz masculina natural en español de España, con energía (no plana), que diga lo
mismo que el texto, palabras sueltas que sobren o siseo/ruido, subtítulos y resaltado sincronizados, la respuesta correcta
se ve clara, explicación útil, cierre claro, probabilidad de comentar/guardar/compartir.
"critical" = true SOLO si el reel está claramente roto (mudo, congelado/negro, ilegible, voz equivocada o ininteligible,
la respuesta resaltada no coincide con la que dice la voz). Después escribe una PRIMERA línea de descripción mejor (máx. 12
palabras, máx. 1 emoji, sin datos nuevos) y una invitación a comentar (máx. 12 palabras).
Devuelve JSON: {{"overall": number, "scores": {{...}}, "critical": bool, "issues": [str], "suggestions": [str],
"caption_first_line": str, "comment_prompt": str}}"""},
                    {"inline_data": {"mime_type": "video/mp4", "data": data}}], 0.4)
    except Exception as e:
        print("revisor: revisión de vídeo omitida:", str(e)[:200], flush=True)
        return caption, {}
    finally:
        if os.path.exists(small): os.remove(small)
    overall = float(res.get("overall") or 0)
    _log("video", {"hook": S.get("screen_hook"), "overall": overall, "scores": res.get("scores"), "critical": res.get("critical"),
                   "issues": res.get("issues"), "suggestions": res.get("suggestions")})
    print(f"revisor: reel {overall}/10" + (f" - {'; '.join(res.get('issues', [])[:3])}" if res.get("issues") else ""), flush=True)
    if res.get("critical") or overall < MIN_SCORE:
        raise RejectReel(f"el revisor rechaza el reel ({overall}/10, mínimo {MIN_SCORE:g}): {'; '.join(res.get('issues', [])[:3])}")
    new_first = (res.get("caption_first_line") or "").strip()
    prompt = (res.get("comment_prompt") or "").strip()
    cap = caption
    if 3 <= len(new_first.split()) <= 14 and "#" not in new_first and not re.search(r"\d+ ?%", new_first):
        cap = new_first + "\n" + rest
    if prompt and 3 <= len(prompt.split()) <= 14 and "#" not in prompt and S.get("comment_prompt") in cap:
        cap = cap.replace(S["comment_prompt"], prompt, 1)
    return cap, {"overall": overall, "issues": res.get("issues"), "suggestions": res.get("suggestions")}
