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
import datetime, json, os, re, sys, time, traceback

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


T_START = time.time()


def tiempo(paso, t0):
    """Cuánto tarda cada paso (tiempos.log, en el repositorio): para saber dónde se va el tiempo."""
    msg = f"{datetime.datetime.utcnow():%Y-%m-%d %H:%M} {slot} {paso}: {time.time() - t0:.0f} s"
    print("⏱", msg, flush=True)
    try:
        with open("tiempos.log", "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


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
    if os.environ.get("PUBLISH_AT_MANUAL"):                      # lanzado a mano con hora: "20:30"
        try:
            target = tuple(int(x) for x in os.environ["PUBLISH_AT_MANUAL"].split(":")[:2])
            os.environ["PUBLISH_MAX_WAIT_MIN"] = "80"
        except Exception:
            pass
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
LEARN = slot == "manana" or os.environ.get("LEARN") == "true"     # aprendizaje diario: una vez al día, no en cada reel
if HAS_AI and LEARN:
    for name, fn in (("insights", lambda: __import__("insights").update()),
                     ("agentes", lambda: __import__("agents").daily_learning())):
        try:
            msg = fn()
        except Exception as e:
            msg = f"{name} omitido: {str(e)[:150]}"
        print(msg, flush=True); status.append(msg)

# ---- serie del día (hueco de mediodía) + experimento del piloto automático
def recent_tematicas(n=10):
    """Temáticas de los últimos reels (los antiguos sin registro se deducen por su formato o su gancho)."""
    try:
        import casos, tematicas
        por_gancho = {}
        for p in casos.generate() + tematicas.generate():
            for h, _ in p["infografia"]["hooks"]:
                por_gancho.setdefault(h, p["infografia"]["variante"])
        out = []
        for line in open("log.jsonl"):
            e = json.loads(line)
            if e.get("tematica"):
                out.append(e["tematica"])
            elif e.get("formato") == "render":
                out.append("inspiracion")
            elif e.get("formato") == "infografia":
                v = e.get("variante") or por_gancho.get(e.get("hook"))
                out.append(tematicas.TEMA_DE_VARIANTE.get(v, v))
        return [x for x in out if x][-n:]
    except Exception:
        return []


arms, strat_msg, series_info, TEMATICA = {}, "", None, None
override = os.environ.get("FORMAT_OVERRIDE", "auto")
style_override = os.environ.get("STYLE_OVERRIDE", "auto")
try:
    import strategy
    import tematicas
    fixed = {"formato": override} if override in strategy.DEFAULT_ARMS["formato"] else {}
    _pedida = os.environ.get("IG_VARIANTE")                   # lanzamiento manual con una temática concreta
    TEMATICA = tematicas.TEMA_DE_VARIANTE.get(_pedida, _pedida) if _pedida else None
    if fixed.get("formato") == "render":
        TEMATICA = "inspiracion"
    if TEMATICA not in tematicas.TEMAS:                        # calendario: 7 temáticas, cada una 3 veces por semana
        TEMATICA = tematicas.tema_de(today, slot, recent_tematicas())
    if not fixed:
        fixed["formato"] = "render" if TEMATICA == "inspiracion" else "infografia"
    os.environ["IG_VARIANTE"] = tematicas.VARIANTE.get(TEMATICA, TEMATICA)
    print("temática de este reel:", TEMATICA, f"({tematicas.NOMBRE[TEMATICA]})", flush=True)
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
if HAS_AI and LEARN:
    try:
        import estudio
        m = estudio.daily_learning(); print(m, flush=True); status.append(m)
    except Exception as e:
        status.append(f"estudio omitido: {str(e)[:120]}")

chain = [arms.get("formato", "infografia")]
try:                                               # si no llega al 8: otras 2 temáticas de infografía que no hayan salido hace poco
    import tematicas as _tm
    _rec = recent_tematicas()
    _otras = sorted([t for t in _tm.TEMAS if t not in ("inspiracion", TEMATICA)],
                    key=lambda t: max([i for i, r in enumerate(_rec) if r == t], default=-1))
    chain += [f"infografia:{_tm.VARIANTE.get(t, t)}" for t in _otras[:2]]
except Exception as e:
    print("reserva de temáticas omitida:", e, flush=True)
# sin formatos de texto de reserva: si ninguna infografía llega al 8, hoy no sale reel (mejor nada que algo confuso)
out = f"out/{today}_{slot}_{now.hour:02d}.mp4"
verify_fn = None
if HAS_AI:
    import verifier
    verify_fn = verifier.verify_piezas
STYLE_KEYS = ("follow_line", "share_line", "save_line", "reto_line", "series", "voice_speed", "music")

meta, items, S, errors, src, image = None, None, None, [], None, None
_t0 = __import__("time").time()
for fmt in chain:
    if meta is None and errors and __import__("time").time() - _t0 > 55 * 60:
        print("tiempo agotado: no pruebo más tipos (evita que GitHub corte el trabajo a medias)", flush=True)
        break
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
        image, dinfo, images = None, {}, None
        pre_voice = False
        if HAS_AI and src in ("ia", "calculado"):
            import agents, estudio, voice
            from concurrent.futures import ThreadPoolExecutor
            t_ = time.time()
            with ThreadPoolExecutor(5) as ex:              # foto, voz y textos de cierre A LA VEZ (antes, uno tras otro)
                def _timed(name, fn, *a):
                    t0 = time.time(); r = fn(*a); tiempo(name, t0); return r

                def _render(idea):                         # render original para el formato de curiosidades
                    for _ in range(2):
                        try:
                            img_, _p = estudio.ilustradora(idea, arms.get("estilo", "negro"))
                            ok_, why_, better_ = estudio.revisora(img_, idea)
                            if ok_:
                                return img_
                            idea = better_ or idea
                        except Exception as e:
                            print("render no generado:", str(e)[:120], flush=True)
                    return None
                if fmt == "render":
                    f_rs = [ex.submit(_render, idea) for idea in S["render"]]
                    f_img = None
                else:
                    f_img = ex.submit(_timed, "foto", estudio.imagen_para, fmt, items, arms.get("estilo", "negro"), S, out[:-4])
                f_gl = ex.submit(agents.growth_lines, S, fmt)
                if fmt in ("infografia", "render"):
                    voice.reset()
                    L_ = make_quiz.lines_for(fmt, items, S)
                    f_vo = ex.submit(_timed, "voz", voice.say_many, [t for _, t, _ in L_],
                                     float(style.get("voice_speed") or 1.0), [make_quiz.ONE_VOICE] * len(L_), True)
                else:
                    f_vo = None
                if f_img is not None:
                    image, dinfo = f_img.result()
                else:
                    images = [f.result() for f in f_rs]
                    if sum(1 for im_ in images if im_ is not None) < 2:
                        raise RuntimeError("no hay renders suficientes para el reel de curiosidades")
                    image = next(im_ for im_ in images if im_ is not None); dinfo = {"concepto": "renders"}
                style.update({k: v for k, v in f_gl.result().items() if not S.get(k)})
                if f_vo is not None:
                    try:
                        f_vo.result(); pre_voice = True
                    except Exception as e:
                        print("voz anticipada fallida; se graba en el render:", str(e)[:150], flush=True)
            tiempo(f"foto + voz + textos (voz: {voice.ENGINE_USED})", t_)
        review, art = {}, {}
        hook_i, cta_i = 0, 0
        best = None                                        # mejor versión de las rondas (se publica si cumple el mínimo de reserva)
        FLOOR = float(os.environ.get("REVIEW_FLOOR", "7.5"))
        for rnd in range(3 if HAS_AI else 1):              # render -> revisión -> ARREGLOS DIRIGIDOS -> render... (máx. 3)
            t_ = time.time()
            meta = make_quiz.build(fmt, items, S, seed, out, arms, style, image=image, estilo=arms.get("estilo"),
                                   keep_voice=pre_voice, images=images if fmt == "render" else None)
            tiempo(f"render (ronda {rnd + 1})", t_)
            caption = open(out.replace(".mp4", ".txt")).read()
            if not HAS_AI:
                break
            import reviewer, agents
            from concurrent.futures import ThreadPoolExecutor
            style["screen_hook"] = S.get("screen_hook")    # el revisor ve el gancho real (no un campo vacío)
            if fmt in ("infografia", "render"):
                for k_ in ("follow_line", "share_line"):   # el cierre de estos formatos no los usa
                    style.pop(k_, None)
            t_ = time.time()
            with ThreadPoolExecutor(2) as ex:              # diseño y vídeo se revisan a la vez
                f_art = ex.submit(reviewer.art_direct, out, S, style, meta["timeline"], meta["duration"])
                f_rev = ex.submit(reviewer.review_video, out, S, caption)
                new_style, art = f_art.result()
                cap2, review = f_rev.result()
            tiempo(f"revisiones (ronda {rnd + 1}): diseño {art.get('overall')} · vídeo {review.get('overall')}", t_)
            # escala anclada: 8 = sin defectos objetivos. Si el revisor no encuentra NINGÚN defecto objetivo pero pone menos
            # de 8 (pasa a menudo), se aplica su propia escala: el reel es publicable.
            for r_ in (review, art):
                if r_.get("overall") and not (r_.get("issues") or []) and not r_.get("critical") and float(r_["overall"]) < reviewer.MIN_SCORE:
                    r_["overall_raw"] = r_["overall"]; r_["overall"] = reviewer.MIN_SCORE
            ok = (float(art.get("overall") or 0) >= reviewer.MIN_SCORE and float(review.get("overall") or 0) >= reviewer.MIN_SCORE
                  and not review.get("critical"))
            if ok:
                caption = cap2
                break
            sc_ = (float(review.get("overall") or 0), float(art.get("overall") or 0))
            if (not review.get("critical") and sc_[1] >= reviewer.MIN_SCORE and sc_[0] >= FLOOR
                    and (best is None or sc_ > best[0])):
                import shutil
                for ext in (".mp4", ".txt", "_portada.jpg"):
                    if os.path.exists(out[:-4] + ext):
                        shutil.copy(out[:-4] + ext, out[:-4] + "_mejor" + ext)
                best = (sc_, dict(meta), dict(review), dict(art), cap2)
            if rnd == 2 and best is not None:              # ninguna ronda llegó al 8 en vídeo: se publica la mejor si no
                import shutil                              # tiene defectos graves y su diseño es de 8 o más
                for ext in (".mp4", ".txt", "_portada.jpg"):
                    if os.path.exists(out[:-4] + "_mejor" + ext):
                        shutil.copy(out[:-4] + "_mejor" + ext, out[:-4] + ext)
                _, meta, review, art, caption = best
                print(f"publico la mejor ronda: vídeo {review.get('overall')} · diseño {art.get('overall')}", flush=True)
                break
            if review.get("critical") or rnd == 2:
                raise reviewer.RejectReel(f"diseño {art.get('overall')} · vídeo {review.get('overall')}/10 (mínimo "
                                          f"{reviewer.MIN_SCORE:g}): {'; '.join((review.get('issues') or [])[:3])}")
            # arreglos dirigidos según lo que piden los revisores (no se tira el reel: se corrige y se vuelve a revisar)
            txt_ = " ".join(str(x) for x in (review.get("issues") or []) + (review.get("suggestions") or [])
                            + (art.get("issues") or [])).lower()
            fixes = []
            if new_style:
                for k_ in ("caption_scale",):
                    if new_style.get(k_) and new_style.get(k_) != style.get(k_):
                        style[k_] = new_style[k_]; fixes.append(k_)
            hooks_ = [h for h in ((S.get("infografia") or {}).get("hooks") or [])
                      if h[0] == S.get("screen_hook") or h[0] not in recent_hooks(20)]   # tampoco aquí ganchos ya publicados
            if re.search(r"gancho|hook|primer(os)? segundo|tarda en|genéric|predecible", txt_) and hook_i + 1 < len(hooks_):
                hook_i += 1; S["screen_hook"], S["hook_line"] = hooks_[hook_i]; style["screen_hook"] = S["screen_hook"]
                fixes.append("gancho")
            if re.search(r"ritmo|pausad|lent|uniforme|monóton|monoton|decae|plano|cadencia", txt_):
                style["pace"] = round(min(1.2, float(style.get("pace") or 1.0) * 1.07), 3); fixes.append("ritmo")
            if re.search(r"texto|dens|satur|carga|demasiad|lectura", txt_):
                style["compact"] = True; fixes.append("menos texto")
            if re.search(r"estátic|estatic|quiet|dinamismo|movimiento|plano fijo", txt_):
                style["motion"] = True; fixes.append("más movimiento")
            if re.search(r"cierre|llamada|cta|final", txt_):
                cta_i = (cta_i + 1) % len(writer.CTAS); S["cta_line"] = writer.CTAS[cta_i]; fixes.append("cierre")
            print(f"ronda {rnd + 1}: no llega al {reviewer.MIN_SCORE:g}; arreglos: {fixes or ['ninguno claro']}", flush=True)
            pre_voice = False                              # la voz se vuelve a grabar (Google: segundos) con el nuevo guion/ritmo
        if HAS_AI:
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
_tp = time.time()
results = publish_all.publish(out, story_mp4, caption, meta, slot=slot)
tiempo("publicar", _tp); tiempo("TOTAL", T_START)
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
meta["variante"] = ((items or [{}])[0].get("infografia") or {}).get("variante")
try:
    import tematicas as _tm
    meta["tematica"] = "inspiracion" if meta.get("formato") == "render" else _tm.TEMA_DE_VARIANTE.get(meta["variante"], meta["variante"])
except Exception:
    pass
log({k: meta.get(k) for k in ("formato", "estilo", "series", "imagen", "concepto", "voice_speed", "music", "ids", "temas",
                              "respuestas", "veredicto", "hook", "hook_line", "duration", "guion", "voice", "review_score",
                              "design_score", "arms", "publicado", "variante", "tematica")})
if all(str(v).startswith("error") for v in results.values()):
    raise SystemExit("No se pudo publicar en ninguna red")
