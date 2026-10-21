"""Un hueco de publicación de UDA · Unión de Arquitectos.

    python run_daily.py <manana|mediodia|tarde|manual> [--dry-run]

Huecos (hora de España): manana 8:00 · mediodia 12:00 (serie del día) · tarde 15:00. El carrusel va a las 18:00.

Cada ejecución:
 1. lee los resultados reales (Zernio: Instagram, TikTok, LinkedIn) y los agentes reescriben sus cuadernos (1 vez al día);
 2. el piloto automático elige el experimento (formato, estilo visual, estilo de gancho, bloque, tiempo para pensar);
    a las 14:30 manda la serie fija del día;
 3. elige pieza(s) del banco SIN repetir y solo verificadas (verificando al momento las que hagan falta);
 4. guionista -> revisor de gancho -> estudio creativo -> verificador del guion -> render -> director de arte ->
    control de calidad del vídeo -> descripción final;
 5. publica vía Zernio: reel en Instagram (+ story de 12 s), TikTok y, si toca, LinkedIn (máx. 1 al día).
Si un formato no puede salir (sin piezas verificadas, guion rechazado, Gemini caído...), prueba el siguiente formato
de la cadena, así que siempre sale algo correcto o no sale nada (nunca algo sin verificar).
"""
import datetime, json, os, sys, traceback

import questions as QB

slot = sys.argv[1] if len(sys.argv) > 1 else "manual"
dry = "--dry-run" in sys.argv or os.environ.get("DRY_RUN") == "true"
now = datetime.datetime.utcnow()
today = now.date()
seed = today.toordinal() * 24 + now.hour
os.makedirs("out", exist_ok=True)
HAS_AI = bool(os.environ.get("GEMINI_API_KEY"))


def log(entry):
    with open("log.jsonl", "a") as f:
        f.write(json.dumps({"date": str(today), "slot": slot, **entry}, ensure_ascii=False) + "\n")


def recent_hooks(n=14):
    out = []
    try:
        for line in open("log.jsonl"):
            h = json.loads(line).get("hook")
            if h: out.append(h)
    except Exception:
        pass
    return out[-n:]


def already_published():
    """Evita publicar dos veces el mismo hueco (p. ej. si alguien relanza el workflow)."""
    try:
        for line in open("log.jsonl"):
            e = json.loads(line)
            if e.get("date") == str(today) and e.get("slot") == slot and any(
                    not str(v).startswith("error") for v in (e.get("publicado") or {}).values()):
                return True
    except Exception:
        pass
    return False


def wait_until_slot():
    """El workflow arranca ~30 min antes; si el reel está listo antes de la hora, espera (máx. PUBLISH_MAX_WAIT_MIN)."""
    target = {"manana": (8, 0), "mediodia": (12, 0), "tarde": (15, 0)}.get(slot)
    if not target:
        return
    try:
        from zoneinfo import ZoneInfo
        import time
        now_l = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
        goal = now_l.replace(hour=target[0], minute=target[1], second=0, microsecond=0)
        secs = (goal - now_l).total_seconds()
        if 0 < secs <= float(os.environ.get("PUBLISH_MAX_WAIT_MIN") or "0") * 60:
            print(f"esperando {secs / 60:.1f} min para publicar a las {target[0]}:{target[1]:02d}", flush=True)
            time.sleep(secs)
    except Exception:
        pass


if slot in ("manana", "mediodia", "tarde") and not dry and already_published() and os.environ.get("FORCE") != "true":
    raise SystemExit(f"El hueco {slot} de hoy ya está publicado; no se repite")

status = []
if not HAS_AI:                                     # sin Gemini no hay verificador: nunca se publica nada sin verificar
    msg = ("Falta el secreto GEMINI_API_KEY (Settings → Secrets and variables → Actions → Secrets, nombre exacto "
           "GEMINI_API_KEY). Sin él no se puede verificar ninguna pieza y no se publica nada.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(f"## ❌ {msg}\n")
    if not (os.environ.get("QUIZ_MOCK") == "1" and QB.verif()):
        raise SystemExit(msg)
if HAS_AI:
    for name, fn in (("insights", lambda: __import__("insights").update()),
                     ("agentes", lambda: __import__("agents").daily_learning())):
        try:
            msg = fn()
        except Exception as e:
            msg = f"{name} omitido: {str(e)[:150]}"
        print(msg, flush=True); status.append(msg)

# ---- serie del día (hueco de mediodía) + experimento del piloto automático
arms, strat_msg, series_info = {}, "", None
override = os.environ.get("FORMAT_OVERRIDE", "auto")
style_override = os.environ.get("STYLE_OVERRIDE", "auto")
try:
    import strategy
    fixed = {"formato": override} if override in strategy.DEFAULT_ARMS["formato"] else {}
    if not fixed:                                             # contenido principal: infografías de cuánto cuesta delegar
        fixed["formato"] = "infografia"
    if not os.environ.get("IG_VARIANTE"):                     # tipo de reel según el día y la hora (nunca todos iguales)
        import casos
        os.environ["IG_VARIANTE"] = casos.variante_de(today, slot)
    print("tipo de reel de hoy:", os.environ["IG_VARIANTE"], flush=True)
    if slot == "mediodia" and not fixed:
        import estudio
        series_info = estudio.series_today(today)
        fixed["formato"] = series_info["series_fmt"]          # cita fija del día: la gente sabe qué toca
    elif slot in ("manana", "tarde") and not fixed:
        fixed["formato"] = "caso_coste"                       # contenido principal: cuánto cuesta delegar tu proyecto
    if style_override in strategy.DEFAULT_ARMS["estilo"]:
        fixed["estilo"] = style_override
    arms = strategy.choose(seed=f"{now:%Y-%m-%d-%H}-{slot}", fixed=fixed)
    if HAS_AI and slot == "mediodia":
        strat_msg = strategy.weekly_strategist()
    strategy.write_report()
    print("experimento:", {k: strategy.short(v) for k, v in arms.items()}, "|", strat_msg, flush=True)
except Exception as e:
    strat_msg = f"estrategia omitida: {str(e)[:150]}"; print(strat_msg, flush=True)
if HAS_AI:
    try:
        import estudio
        m = estudio.daily_learning(); print(m, flush=True); status.append(m)
    except Exception as e:
        status.append(f"estudio omitido: {str(e)[:120]}")

chain = list(dict.fromkeys([arms.get("formato", "infografia"), "infografia"]))
if chain[0] == "infografia":                       # si una infografía no pasa el 8, se prueban otros tipos de infografía
    import casos as _c
    _v0 = os.environ.get("IG_VARIANTE")
    chain += [f"infografia:{v}" for v in _c.VARIANTES if v != _v0][:2]
chain += ["mito_realidad", "dato"]
out = f"out/{today}_{slot}_{now.hour:02d}.mp4"
verify_fn = None
if HAS_AI:
    import verifier
    verify_fn = verifier.verify_piezas
STYLE_KEYS = ("follow_line", "share_line", "save_line", "reto_line", "series", "voice_speed", "music")

meta, items, S, errors, src, image = None, None, None, [], None, None
for fmt in chain:
    if fmt.startswith("infografia:"):
        os.environ["IG_VARIANTE"] = fmt.split(":", 1)[1]; fmt = "infografia"
        print("pruebo otro tipo de infografía:", os.environ["IG_VARIANTE"], flush=True)
    try:
        if fmt == "repaso_express":
            items = QB.pick_fichas(seed=f"{seed}-{fmt}", verify=verify_fn)
        else:
            n = 3 if fmt == "simulacro_3" else 1
            ps = QB.pick(fmt, arms.get("bloque"), seed=f"{seed}-{fmt}", n=n, verify=verify_fn)
            items = [QB.prepare(p, seed) for p in ps]
        si = series_info if (series_info and fmt == series_info["series_fmt"]) else None
        import writer
        S, fmt, src = writer.script_for(fmt, items, arms, avoid=recent_hooks(), verify=HAS_AI, series_info=si)
        import make_quiz
        style = dict(make_quiz.DEFAULT_STYLE)
        style.update({k: S[k] for k in STYLE_KEYS if S.get(k)})
        image, dinfo = None, {}
        if HAS_AI and src in ("ia", "calculado"):
            import agents, estudio
            style.update({k: v for k, v in agents.growth_lines(S, fmt).items() if not S.get(k)})
            image, dinfo = estudio.imagen_para(fmt, items, arms.get("estilo", "negro"), S, out[:-4])
        meta = make_quiz.build(fmt, items, S, seed, out, arms, style, image=image, estilo=arms.get("estilo"))
        caption = open(out.replace(".mp4", ".txt")).read()
        review, art = {}, {}
        if HAS_AI:
            import reviewer, agents
            new_style, art = reviewer.art_direct(out, S, style, meta["timeline"], meta["duration"])
            if new_style:
                print("director de arte: vuelvo a renderizar con", {k: v for k, v in new_style.items() if style.get(k) != v}, flush=True)
                style = new_style
                meta = make_quiz.build(fmt, items, S, seed, out, arms, style, keep_voice=True, image=image,
                                       estilo=arms.get("estilo"))                  # voz en caché: no se regraba
                caption = open(out.replace(".mp4", ".txt")).read()
                _, art = reviewer.art_direct(out, S, style, meta["timeline"], meta["duration"])   # nueva nota
            if art and float(art.get("overall") or 0) < reviewer.MIN_SCORE:
                raise reviewer.RejectReel(f"diseño {art.get('overall')}/10 (mínimo {reviewer.MIN_SCORE:g})")
            caption, review = reviewer.review_video(out, S, caption)              # RejectReel -> siguiente formato
            if not review.get("overall"):
                raise reviewer.RejectReel("el revisor de vídeo no ha podido puntuar el reel: sin nota no se publica")
            caption = agents.growth_caption(caption, S, review)
            open(out.replace(".mp4", ".txt"), "w").write(caption)
        meta.update(review_score=review.get("overall"), design_score=art.get("overall"), guion=src,
                    series=si and si["series_name"], imagen=image is not None, concepto=dinfo.get("concepto"),
                    voice_speed=style.get("voice_speed"), music=style.get("music"))
        arms["formato"] = fmt
        arms["estilo"] = meta["estilo"]
        break
    except Exception as e:
        meta = None
        errors.append(f"{fmt}: {str(e)[:300]}")
        print(f"[{fmt}] no ha podido salir, pruebo el siguiente formato:\n{traceback.format_exc()[-1500:]}", flush=True)
        try:                                       # se guarda en el repositorio: así se ve por qué no salió un formato
            with open("errores_reels.log", "a") as f_:
                f_.write(f"{now:%Y-%m-%d %H:%M} {slot} [{fmt}] {traceback.format_exc()[-1200:]}\n")
        except Exception:
            pass

story_mp4 = None
if meta:
    try:                                           # story de 12 s que anuncia el reel
        import story
        story_mp4 = story.build(meta["story_base"], out.replace(".mp4", "_story.mp4"), meta["formato"])
    except Exception as e:
        print("story no generada:", str(e)[:200], flush=True)

summary = os.environ.get("GITHUB_STEP_SUMMARY")
try:
    import voice as _v
    voice_used = _v.ENGINE_USED
except Exception:
    voice_used = None
if summary:
    with open(summary, "a") as f:
        if meta:
            f.write(f"## ✅ Reel listo: {meta['formato']} · estilo {meta['estilo']}" + (f" · {meta['series']}" if meta.get("series") else "")
                    + (" · con ilustración" if meta.get("imagen") else "") + "\n\n"
                    f"- Hueco: `{slot}` · voz: `{voice_used}` · guion: `{src}` · duración {meta['duration']} s\n"
                    f"- Gancho: **{meta['hook']}**\n- Tema(s): {', '.join(QB.tema_titulo(t) for t in meta['temas'])}"
                    + (f" · respuesta(s): {', '.join(meta['respuestas'])}" if meta.get("respuestas") else "") + "\n"
                    + (f"- Revisor: {meta.get('review_score')}/10 · Director de arte: {meta.get('design_score')}/10\n")
                    + (f"- Experimento: {', '.join(f'{k}={str(v).split(chr(58))[0]}' for k, v in arms.items())}\n" if arms else ""))
        else:
            f.write("## ❌ Hoy no sale reel (nada pasó la verificación)\n\n")
        f.write("".join(f"- {m}\n" for m in status + ([strat_msg] if strat_msg else []))
                + "".join(f"- Error: `{e}`\n" for e in errors))
if meta is None:
    raise SystemExit("Ningún formato pudo generar un reel verificado")

caption = open(out.replace(".mp4", ".txt")).read()
print(caption)
if dry:
    print("PRUEBA: no se publica")
    sys.exit(0)

import publish_all
wait_until_slot()                                  # publica a la hora exacta del hueco (8:00 / 12:00 / 15:00 en España)
results = publish_all.publish(out, story_mp4, caption, meta, slot=slot)
meta.update(publicado=results)
print("publicado:", json.dumps(results, ensure_ascii=False), flush=True)
if any(not str(v).startswith("error") for v in results.values()):
    QB.mark_used(items, meta["formato"])
if summary:
    with open(summary, "a") as f:
        f.write("\n### Publicación\n" + "".join(f"- {'✅' if not str(v).startswith('error') else '❌'} {k}: {v}\n"
                                                  for k, v in results.items()))
meta["voice"] = voice_used
meta["arms"] = arms
log({k: meta.get(k) for k in ("formato", "estilo", "series", "imagen", "concepto", "voice_speed", "music", "ids", "temas",
                              "respuestas", "veredicto", "hook", "hook_line", "duration", "guion", "voice", "review_score",
                              "design_score", "arms", "publicado")})
if all(str(v).startswith("error") for v in results.values()):
    raise SystemExit("No se pudo publicar en ninguna red")
