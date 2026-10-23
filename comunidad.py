"""Bot de comunidad de UDA: contesta comentarios y publica la solución de los tests en Instagram, TikTok y LinkedIn.

Lo lanza cada hora el workflow «Comunidad» (.github/workflows/comunidad.yml).

  · Tests y verdadero o falso: el reel acaba en la pregunta. Entre 12 y 24 h después de publicarlo, el bot publica la
    SOLUCIÓN como comentario (en TikTok, además, la fija arriba). Hasta entonces, a quien contesta le responde
    «¡Anotado! Mañana publicamos la solución» (sin destriparla nunca). Después, le dice si ha acertado.
  · Encuestas: a las 12-24 h publica el recuento de votos (A, B, C, D) de los comentarios.
  · Resto de reels y carruseles: contesta los comentarios con un agente (Gemini) con la voz de UDA. No contesta spam,
    insultos ni comentarios sin contenido. Si preguntan por el servicio, invita a agendar una reunión.

Instagram va por la API de Instagram (IG_TOKEN), igual que la publicación; TikTok y LinkedIn por Zernio
(TikTok: cuenta conectada con la app de empresa; LinkedIn: página de empresa). Si una red no deja comentar, se apunta
en comunidad_estado.md y las demás siguen.

Estado: comunidad.json (comentarios ya contestados y soluciones ya publicadas) · resumen legible: comunidad_estado.md.
    python comunidad.py            # una pasada
    python comunidad.py --prueba   # no publica nada: enseña lo que haría
"""
import datetime, hashlib, json, os, random, re, sys, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(HERE, "comunidad.json")
RESUMEN = os.path.join(HERE, "comunidad_estado.md")
DIAS = int(os.environ.get("COMUNIDAD_DIAS", "7"))             # se atienden las publicaciones de los últimos 7 días
MAX_RESPUESTAS = int(os.environ.get("COMUNIDAD_MAX", "40"))   # por pasada (para no parecer un robot ni saturar las APIs)
PRUEBA = "--prueba" in sys.argv
SOLO_LETRA = re.compile(r"^\W*(?:(?:la|opci[oó]n|respuesta)\s+)?([abcd])\W*$", re.I)       # «B», «la b», «opción C!»
LETRA_EXPL = re.compile(r"\b(?:opci[oó]n|respuesta|la)\s+([abcd])\b", re.I)                # «creo que es la B»
LETRA_MAYUS = re.compile(r"(?<![\wÁÉÍÓÚÑáéíóúñ])([ABCD])(?![\wÁÉÍÓÚÑáéíóúñ])")                # «B, seguro»
VF_RX = re.compile(r"\b(verdadero|verdad|cierto)\b|\b(falso|mentira)\b", re.I)
VF_SOLO = re.compile(r"^\W*([vf])\W*$", re.I)
WEB = "uniondearquitectos.com"
NOW = datetime.datetime.now(datetime.timezone.utc)
LOG = []
NATIVOS = {}


def say(*a):
    msg = " ".join(str(x) for x in a)
    LOG.append(msg); print(msg, flush=True)


def load_state():
    try:
        s = json.load(open(ESTADO))
    except Exception:
        s = {}
    s.setdefault("contestados", []); s.setdefault("posts", {}); s.setdefault("errores", {})
    return s


# ------------------------------------------------------------------ publicaciones a atender
def publicaciones():
    """[(clave, red, post_id, pieza o None, info)] de los reels y carruseles de los últimos días."""
    import tematicas
    piezas = {p["id"]: p for p in tematicas.interaccion()}
    out, hoy = [], datetime.date.today()
    try:
        filas = [json.loads(l) for l in open(os.path.join(HERE, "log.jsonl"))]
    except Exception:
        filas = []
    for e in filas:
        try:
            if (hoy - datetime.date.fromisoformat(e["date"])).days > DIAS:
                continue
        except Exception:
            continue
        pz = next((piezas[i] for i in (e.get("ids") or []) if i in piezas), None)
        info = {"tematica": e.get("tematica"), "hook": e.get("hook"), "ts": e.get("ts"), "fecha": e["date"]}
        for k, v in (e.get("publicado") or {}).items():
            v = str(v)
            if v.startswith("error") or "story" in k or "borrador" in k:
                continue
            red = "instagram" if k.startswith("instagram") else "tiktok" if k.startswith("tiktok") else "linkedin"
            out.append((f"{red}:{v}", red, v, pz, info))
    try:
        for c in json.load(open(os.path.join(HERE, "carruseles.json"))):
            if not c.get("publicado") or (hoy - datetime.date.fromisoformat(c["fecha"])).days > DIAS:
                continue
            info = {"tematica": "carrusel", "hook": c.get("titulo"), "fecha": c["fecha"]}
            for k, v in (c.get("destinos") or {}).items():
                v = str(v)
                if v.startswith("error"):
                    continue
                red = "instagram" if k.startswith("instagram") else "tiktok" if k.startswith("tiktok") else "linkedin"
                out.append((f"{red}:{v}", red, v, None, info))
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ redes
class Instagram:
    """API de Instagram directa (la misma que publica). Ids «ig:123»."""
    def __init__(self):
        import publish_ig
        self.g, self.t = publish_ig.GRAPH, os.environ.get("IG_TOKEN")
        self.yo = os.environ.get("IG_HANDLE", "@uniondearquitectos").lstrip("@").lower()

    def ok(self):
        return bool(self.t)

    def comentarios(self, pid):
        mid = pid.split(":", 1)[1]
        r = requests.get(f"{self.g}/{mid}/comments", params={"fields": "id,text,username,timestamp,like_count",
                                                              "limit": 100, "access_token": self.t}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram comentarios {r.status_code}: {r.text[:300]}")
        return [{"id": c["id"], "texto": c.get("text", ""), "autor": c.get("username", ""),
                 "mio": (c.get("username", "").lower() == self.yo), "likes": c.get("like_count", 0)}
                for c in r.json().get("data", [])]

    def responder(self, pid, cid, msg):
        r = requests.post(f"{self.g}/{cid}/replies", data={"message": msg, "access_token": self.t}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram respuesta {r.status_code}: {r.text[:300]}")
        return r.json().get("id")

    def comentar(self, pid, msg):
        mid = pid.split(":", 1)[1]
        r = requests.post(f"{self.g}/{mid}/comments", data={"message": msg, "access_token": self.t}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram comentario {r.status_code}: {r.text[:300]}")
        return r.json().get("id")

    def fijar(self, pid, cid):
        return None                                    # la API de Instagram no permite fijar comentarios


class Zernio:
    """TikTok y LinkedIn (y Instagram si se publicó por Zernio) con la bandeja de comentarios de Zernio."""
    API = "https://zernio.com/api/v1"

    def __init__(self, red):
        self.red = red

    def ok(self):
        return bool(os.environ.get("ZERNIO_API_KEY"))

    def _acc(self):
        import publish_zernio as Z
        return Z._acc(self.red)

    def _h(self):
        return {"Authorization": f"Bearer {os.environ['ZERNIO_API_KEY']}", "Content-Type": "application/json"}

    def nativo(self, pid):
        """Id de la publicación en la propia red (TikTok lo exige; Zernio guarda el suyo). Se guarda en caché."""
        if pid in NATIVOS:
            return NATIVOS[pid]
        out = pid
        try:
            r = requests.get(f"{self.API}/posts/{pid}", headers=self._h(), timeout=60)
            post = (r.json() or {}).get("post") or r.json()
            for pl in post.get("platforms") or []:
                if (pl.get("platform") or "").lower() != self.red:
                    continue
                nid = pl.get("platformPostId") or pl.get("platformId") or pl.get("postId")
                url = pl.get("platformPostUrl") or pl.get("url") or ""
                if not nid and self.red == "tiktok":
                    m = re.search(r"/video/(\d+)", url); nid = m.group(1) if m else None
                if not nid and self.red == "linkedin":
                    m = re.search(r"(urn:li:(?:share|ugcPost|activity):\d+)", url); nid = m.group(1) if m else None
                if nid:
                    out = str(nid)
        except Exception as e:
            say(f"{self.red}: no encuentro el id nativo de {pid}: {str(e)[:120]}")
        NATIVOS[pid] = out
        return out

    def comentarios(self, pid):
        pid = self.nativo(pid)
        r = requests.get(f"{self.API}/inbox/comments/{pid}", params={"accountId": self._acc(), "limit": 100},
                         headers=self._h(), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Zernio {self.red} comentarios {r.status_code}: {r.text[:300]}")
        return [{"id": c["id"], "texto": c.get("message", ""), "autor": (c.get("from") or {}).get("username")
                 or (c.get("from") or {}).get("name", ""), "mio": bool((c.get("from") or {}).get("isOwner")),
                 "likes": c.get("likeCount", 0)} for c in r.json().get("comments", [])]

    def _post(self, pid, body):
        pid = self.nativo(pid)
        body = {"accountId": self._acc(), **body}
        r = requests.post(f"{self.API}/inbox/comments/{pid}", json=body, timeout=60,
                          headers={**self._h(), "Idempotency-Key": hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()})
        if r.status_code >= 400:
            raise RuntimeError(f"Zernio {self.red} {r.status_code}: {r.text[:300]}")
        return (r.json().get("data") or {}).get("commentId")

    def responder(self, pid, cid, msg):
        return self._post(pid, {"message": msg, "commentId": cid})

    def comentar(self, pid, msg):
        return self._post(pid, {"message": msg})

    def fijar(self, pid, cid):
        if self.red != "tiktok" or not cid:
            return None
        r = requests.post(f"{self.API}/inbox/comments/{self.nativo(pid)}/{cid}/pin", json={"accountId": self._acc()},
                          headers=self._h(), timeout=60)
        return r.status_code < 400


def red_para(red, pid):
    if red == "instagram" and pid.startswith("ig:"):
        return Instagram()
    return Zernio(red)


# ------------------------------------------------------------------ textos
def _sol(p):
    return p.get("solucion") if p else None


def momento_solucion(clave, info, st):
    """Entre 12 y 24 h después de publicar (fijo para cada publicación, para que no salgan todas a la vez)."""
    base = info.get("ts")
    try:
        t0 = datetime.datetime.fromisoformat(base) if base else None
    except Exception:
        t0 = None
    if t0 is None:                                     # publicaciones sin hora: desde la primera vez que el bot las ve
        t0 = datetime.datetime.fromisoformat(st["posts"].setdefault(clave, {}).setdefault("visto", NOW.isoformat()))
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=datetime.timezone.utc)
    h = 12 + int(hashlib.md5(clave.encode()).hexdigest(), 16) % 12
    return t0 + datetime.timedelta(hours=h)


def texto_solucion(sol, comentarios):
    if sol["tipo"] == "test":
        c = sol["correcta"]
        return (f"✅ Solución: {sol['letras'][c]}) {sol['opciones'][c]}\n{sol['explicacion']}\n"
                "¿Acertaste? Cuéntanos 👇 Mañana, otra pregunta.")
    if sol["tipo"] == "vf":
        return (f"✅ Solución: {'VERDADERO' if sol['correcta'] == 0 else 'FALSO'}.\n{sol['explicacion']}\n"
                "¿Acertaste? Cuéntanos 👇")
    votos = {L: 0 for L in sol["letras"]}                 # encuesta: recuento de letras de los comentarios
    for c in comentarios:
        if c["mio"]:
            continue
        L = letra(c["texto"], sol)
        if L:
            votos[L] += 1
    total = sum(votos.values())
    if not total:
        return None
    filas = "\n".join(f"{L}) {o}: {round(100 * votos[L] / total)} %" for L, o in zip(sol["letras"], sol["opciones"]))
    mx = max(votos.values()); tops = [L for L in votos if votos[L] == mx]
    gana = (f"Gana la {tops[0]}) {sol['opciones'][sol['letras'].index(tops[0])]}." if len(tops) == 1
            else f"Empate entre la {' y la '.join(tops)}.")
    return f"📊 Resultados ({total} {'voto' if total == 1 else 'votos'}):\n{filas}\n{gana} ¡Gracias por participar! 🙌"


def letra(texto, sol):
    """La opción que ha elegido quien comenta, o None si no está clara (nunca se adivina)."""
    t = (texto or "").strip()
    if sol["letras"] == "VF":
        m = VF_SOLO.match(t)
        if m:
            return m.group(1).upper()
        m = VF_RX.search(t)
        return ("V" if m.group(1) else "F") if m else None
    for rx in (SOLO_LETRA, LETRA_EXPL, LETRA_MAYUS):
        found = {m.group(1).upper() for m in rx.finditer(t)}
        if len(found) == 1:
            return found.pop()
        if found:
            return None                                     # varias letras: no está claro
    hits = [sol["letras"][j] for j, o in enumerate(sol["opciones"]) if len(o) > 3 and o.lower() in t.lower()]
    return hits[0] if len(hits) == 1 else None


ANOTADO = ["¡Anotado, {n}! 😉 Mañana publicamos la solución aquí.", "¡Apuntado! Mañana te decimos si has acertado 👀",
           "¡Gracias por jugar, {n}! La solución, mañana en comentarios.", "Anotada tu respuesta 🙌 Mañana, la solución."]
ACIERTO = ["¡Correcta, {n}! 👏", "¡Bien visto! Es la {L} ✅", "¡Acertaste! 🙌", "¡Exacto, {n}! Es la {L} 👏"]
FALLO = ["¡Casi, {n}! La correcta era la {L}: {O}.", "Esta vez no 😅 Era la {L}: {O}.", "¡Cerca! La buena era la {L}: {O}."]
VOTO = ["¡Gracias por tu voto, {n}! 🙌", "¡Apuntado! Mañana publicamos los resultados 📊", "¡Gracias! Te leemos 🙌"]


def _plantilla(lista, **kw):
    t = random.choice(lista)
    n = (kw.get("n") or "").strip()
    t = t.replace(", {n}", f", {n}" if n else "").replace("{n}", n)
    return t.format(**{k: v for k, v in kw.items() if k != "n"})


def respuesta(com, pieza, info, revelada):
    """Texto de respuesta o None (no contestar)."""
    sol = _sol(pieza)
    n = (com["autor"] or "").split()[0][:20] if com["autor"] else ""
    if sol:
        L = letra(com["texto"], sol)
        if L and len(com["texto"]) <= 60:                 # contestación «de juego»: plantilla, rápida y segura
            if sol["tipo"] == "encuesta":
                return _plantilla(VOTO, n=n)
            if not revelada:
                return _plantilla(ANOTADO, n=n)
            ok = sol["letras"][sol["correcta"]]
            if L == ok:
                return _plantilla(ACIERTO, n=n, L=ok)
            return _plantilla(FALLO, n=n, L=ok, O=sol["opciones"][sol["correcta"]])
    return agente(com, pieza, info, revelada)


def agente(com, pieza, info, revelada):
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    import gemini
    sol = _sol(pieza)
    ctx = f"Publicación: «{info.get('hook')}» (tipo: {info.get('tematica')})."
    if sol:
        ctx += f"\nPregunta: {sol['pregunta']} · Opciones: {', '.join(sol['opciones'])}."
        if sol["tipo"] in ("test", "vf"):
            ctx += (f"\nSolución: {sol['letras'][sol['correcta']]} ({sol['opciones'][sol['correcta']]}). "
                    + ("YA PUBLICADA: puedes decirla." if revelada else "AÚN NO PUBLICADA: NO la digas ni la insinúes; "
                       "di que mañana la publicamos en comentarios."))
    hechos = open(os.path.join(HERE, "assets", "uda", "hechos.md")).read()
    try:
        r = gemini.ask(f"""Eres el community manager de UDA · Unión de Arquitectos (@uniondearquitectos), equipo técnico
externo para despachos de arquitectura. Contesta a este comentario en {com.get('red', 'redes')}.
{ctx}
Comentario de @{com['autor']}: «{com['texto']}»
Reglas: español de España, cercano y elegante, de colega a colega; 1 o 2 frases, máx. 200 caracteres, como mucho 1 emoji.
Si pregunta algo de arquitectura, contesta solo si estás seguro; si no, invita a que lo comente la comunidad. Si
pregunta por el servicio, precios o colaborar: invita a agendar una reunión en {WEB} (no des precios). Sobre UDA solo
puedes afirmar lo que dicen estos hechos: {hechos[:2500]}
NO contestes (responder=false) si es spam, un insulto, un emoji suelto, solo una mención a otra persona, o algo
polémico o personal. Nunca discutas.
Devuelve JSON: {{"responder": bool, "texto": str}}""", 0.6)
    except Exception as e:
        say("agente de comunidad no disponible:", str(e)[:150]); return None
    t = (r.get("texto") or "").strip()
    if not r.get("responder") or not t or len(t) > 280:
        return None
    if sol and sol["tipo"] in ("test", "vf") and not revelada:     # seguro: nunca destripar la solución antes de tiempo
        o = sol["opciones"][sol["correcta"]].lower()
        if o in t.lower() or re.search(r"\bcorrect[ao]\b|\bsoluci[oó]n es\b|\bes la [abcd]\b", t, re.I):
            return None
    return t


# ------------------------------------------------------------------ pasada
def main():
    st = load_state()
    NATIVOS.update(st.get("nativos", {}))
    hechos = set(st["contestados"])
    n_resp, resumen, errores = 0, [], {}
    for clave, red, pid, pieza, info in publicaciones():
        api = red_para(red, pid)
        if not api.ok():
            continue
        try:
            coms = api.comentarios(pid)
        except Exception as e:
            errores[red] = str(e)[:400]; say(f"{clave}: {str(e)[:400]}"); continue
        ps = st["posts"].setdefault(clave, {})
        sol = _sol(pieza)
        revelada = bool(ps.get("solucion"))
        # 1) la solución (o los resultados) entre 12 y 24 h después
        if sol and not revelada and NOW >= momento_solucion(clave, info, st):
            txt = texto_solucion(sol, coms)
            if txt:
                try:
                    if PRUEBA:
                        say(f"[prueba] {clave}: publicaría la solución:\n{txt}")
                    else:
                        cid = api.comentar(pid, txt)
                        fij = api.fijar(pid, cid)
                        ps["solucion"] = NOW.isoformat(); ps["solucion_id"] = cid; revelada = True
                        say(f"{clave}: solución publicada" + (" y fijada" if fij else ""))
                except Exception as e:
                    errores[red] = f"no deja comentar: {str(e)[:180]}"
            elif sol["tipo"] == "encuesta" and NOW >= momento_solucion(clave, info, st) + datetime.timedelta(hours=24):
                ps["solucion"] = "sin votos"                 # encuesta sin votos: no se publica nada
        # 2) contestar comentarios nuevos (uno por persona y publicación)
        ya_personas = set(ps.get("personas", []))
        for c in sorted(coms, key=lambda c: -int(c.get("likes") or 0)):
            if n_resp >= MAX_RESPUESTAS:
                break
            if c["mio"] or c["id"] in hechos or not c["texto"].strip():
                continue
            if c["autor"] and c["autor"] in ya_personas:
                hechos.add(c["id"]); continue
            c["red"] = red
            txt = respuesta(c, pieza, info, revelada)
            hechos.add(c["id"])
            if not txt:
                continue
            try:
                if PRUEBA:
                    say(f"[prueba] {clave} @{c['autor']}: «{c['texto'][:80]}» -> «{txt}»")
                else:
                    api.responder(pid, c["id"], txt)
                    time.sleep(2)
                n_resp += 1; ya_personas.add(c["autor"])
            except Exception as e:
                errores[red] = f"no deja responder: {str(e)[:180]}"; hechos.discard(c["id"])
        ps["personas"] = sorted(p for p in ya_personas if p)
        ps["comentarios"] = len(coms)
        resumen.append(f"| {info.get('fecha')} | {red} | {info.get('tematica')} | {(info.get('hook') or '')[:40]} | "
                       f"{len(coms)} | {'sí' if ps.get('solucion') else ('pendiente' if sol else '—')} |")
    st["contestados"] = sorted(hechos)[-20000:]
    st["errores"] = errores
    st["nativos"] = NATIVOS
    if not PRUEBA:
        json.dump(st, open(ESTADO, "w"), ensure_ascii=False, indent=0)
        open(RESUMEN, "w").write(
            f"# Bot de comunidad\n\n_Última pasada: {NOW:%Y-%m-%d %H:%M} UTC · {n_resp} respuestas_\n\n"
            + ("## Avisos\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in errores.items()) + "\n\n" if errores else "")
            + "| Fecha | Red | Tipo | Gancho | Comentarios | Solución publicada |\n|---|---|---|---|---|---|\n"
            + "\n".join(resumen) + "\n")
    say(f"comunidad: {n_resp} respuestas; avisos: {errores or 'ninguno'}")


if __name__ == "__main__":
    main()
