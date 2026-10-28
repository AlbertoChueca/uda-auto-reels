"""Agente 9 · CAZATENDENCIAS: cada día mira qué está funcionando AHORA en arquitectura, interiorismo y reformas en
TikTok e Instagram (España) y lo convierte en contenido para UDA antes de que se genere el reel.

Qué hace (una vez al día, antes del primer reel; si falla, el reel sale igual con el banco de siempre):
  1. Busca en Google (Gemini con búsqueda) las tendencias de la semana: temas y estilos que se están viralizando,
     formatos que funcionan, búsquedas y hashtags, y lo que ya está quemado.
  2. Lee nuestros resultados reales (performance.json) para no perseguir modas que a nuestra audiencia no le funcionan.
  3. Mira las canciones en tendencia de la Biblioteca de Música Comercial de TikTok (España).
  4. Escribe piezas NUEVAS para el banco visual (fuentes/visual.json) a partir de esas tendencias: una galería, unos
     tips, una estancia de antes/después con el estilo de moda y una casa para «del boceto al render». Llevan
     «tendencia» y la fecha: visual.py las elige primero mientras estén frescas (10 días).
  5. Deja su cuaderno (agents/cazatendencias.md) y tendencias.json (hashtags y búsquedas que usan las descripciones).

Reglas: nada de marcas, edificios famosos, arquitectos con nombre, normativa (CTE, BOE), precios ni cifras; todo
original y verosímil. Las piezas pasan los mismos controles que el resto (formato, longitudes, sin duplicados).

    python cazatendencias.py            # una vez al día (no hace nada si ya se hizo hoy)
    python cazatendencias.py --forzar   # aunque ya se haya hecho hoy
    python cazatendencias.py --prueba   # enseña lo que haría, sin guardar
"""
import datetime, difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(HERE, "fuentes", "visual.json")
SALIDA = os.path.join(HERE, "tendencias.json")
CUADERNO = os.path.join(HERE, "agents", "cazatendencias.md")
STAMP = os.path.join(HERE, "agents", "cazatendencias_last_update.txt")
FRESCO_DIAS = 10
PROHIBIDO = re.compile(r"\b(CTE|BOE|decreto|UDA|Uni[óo]n de Arquitectos|IKEA|Zara|Pinterest|Instagram|TikTok|"
                       r"Gaud[íi]|Calatrava|Foster|Hadid|Ando|Le Corbusier|Moneo|Campo Baeza|\d+ ?(€|euros|%))\b", re.I)
PUBLICO = ("arquitectos autónomos y fundadores de despachos de arquitectura en España (45-55 años), y amantes de la "
           "arquitectura y el interiorismo que siguen cuentas de reformas e interiores")


def say(*a):
    print("cazatendencias:", *a, flush=True)


def _grounded(prompt):
    import ampliar_banco
    return ampliar_banco._grounded(prompt)


def _ask(prompt, t=0.7):
    import gemini
    return gemini.ask(prompt, t)


def buscar():
    hoy = datetime.date.today()
    return _grounded(f"""Eres CAZATENDENCIAS de contenido de arquitectura en redes. Hoy es {hoy:%d/%m/%Y}. Busca en Google
qué está funcionando ESTA SEMANA y este mes (no hace años) en TikTok e Instagram en ESPAÑA en arquitectura, interiorismo,
reformas y casas: temas y estilos que se están viralizando (materiales, colores, tipos de estancia, de casa o de reforma),
formatos de vídeo que funcionan, búsquedas que la gente hace y hashtags en español que se usan ahora. Incluye también lo
que ya está quemado. Solo cosas que se puedan mostrar con imágenes originales (sin marcas ni edificios famosos).
Devuelve SOLO JSON:
{{"temas": [{{"tema": str, "por_que": str}}] (5-8), "estilos": [str] (4-6, p. ej. «suelo de terrazo», «verde salvia»),
"formatos": [str] (3-5), "busquedas": [str] (5-8, frases que la gente busca en TikTok, en minúsculas),
"hashtags": [str] (6-10, con #, en español, sin espacios), "quemado": [str] (2-4), "fuentes": [str] (URLs)}}""")


def nuestros_datos():
    try:
        perf = json.load(open(os.path.join(HERE, "performance.json")))
    except Exception:
        return "(sin datos aún)"
    rows = sorted([r for r in perf.values() if r.get("hook")],
                  key=lambda r: -((r.get("views") or 0) + 30 * (r.get("saved") or 0) + 40 * (r.get("shares") or 0)))
    return "\n".join(f"- {r.get('date')} | {r.get('tematica') or r.get('formato')} | «{r.get('hook')}» | views {r.get('views')} "
                     f"| guardados {r.get('saved')} | compartidos {r.get('shares')}" for r in rows[:12]) or "(sin datos aún)"


def musica():
    try:
        import publish_zernio as Z, requests
        r = requests.get(f"{Z.API}/accounts/{Z._acc('tiktok')}/tiktok/commercial-music", headers=Z._h(),
                         params={"countryCode": "ES"}, timeout=60)
        ef = re.compile(r"sound|error|alert|warning|notification|effect|sfx|\bboom\b|magic|\(\d{4,}\)|efecto|sonido", re.I)
        return [f"{t.get('name')} · {t.get('artist')}" for t in (r.json().get("tracks") or [])
                if not ef.search(f"{t.get('name')} {t.get('artist')}")][:10]
    except Exception as e:
        say("música de TikTok no disponible:", str(e)[:120])
        return []


def piezas(T, banco):
    ya = {"galeria": [p.get("hook", "") for p in banco["galeria"]], "tips": [p.get("hook", "") for p in banco["tips"]],
          "antes_despues": [p.get("descripcion", "") for p in banco["antes_despues"]],
          "proceso": [p.get("descripcion", "") for p in banco["proceso"]]}
    return _ask(f"""Eres el CAZATENDENCIAS del equipo de redes de UDA (arquitectura). Público: {PUBLICO}.
TENDENCIAS DE ESTA SEMANA (búsqueda en Google): {json.dumps(T, ensure_ascii=False)[:3500]}
LO QUE MEJOR NOS FUNCIONA A NOSOTROS: {nuestros_datos()}
YA EXISTEN (no repitas ni parafrasees): {json.dumps(ya, ensure_ascii=False)[:2500]}

Convierte las tendencias en piezas para reels 100 % visuales con imágenes ORIGINALES generadas por IA. Español de España.
Prohibido: marcas, edificios o arquitectos con nombre, normativa, precios, cifras, porcentajes y la palabra UDA.
1. "galeria": {{"hook": máx. 40 caracteres (lo que la gente quiere ver; puede ser pregunta), "cierre": pregunta máx. 30
   caracteres, "escenas": 6 x {{"idea": descripción visual concreta de una fotografía de interior o arquitectura (máx. 25
   palabras), "label": 1-3 palabras}}}}
2. "tips": {{"hook": «5 ...» máx. 45 caracteres, "tips": 5 x {{"tip": consejo práctico máx. 6 palabras, "idea":
   fotografía que lo muestra (máx. 22 palabras)}}}}
3. "antes_despues": {{"descripcion": la estancia ANTES, anticuada (máx. 18 palabras, empieza por «un/una»), "estilo": el
   estilo de moda del DESPUÉS (máx. 14 palabras)}}
4. "proceso": {{"descripcion": una casa que encaje con la tendencia (máx. 16 palabras, empieza por «una»)}}
Además "notas": 3-5 viñetas para el cuaderno del equipo (qué aprovechar esta semana y qué evitar), y "por_tipo":
{{"galeria": str, "tips": str, "antes_despues": str, "proceso": str}} con la búsqueda de TikTok (minúsculas, 3-6 palabras)
más útil para cada uno.
Devuelve SOLO JSON con: galeria, tips, antes_despues, proceso, notas, por_tipo.""", 0.8)


def _txt(*vs):
    return " ".join(str(v or "") for v in vs)


def valida(P, banco):
    """Solo entra lo que cumple el formato del banco. Devuelve {sección: pieza}."""
    out, hoy = {}, str(datetime.date.today())
    sello = {"tendencia": True, "fecha": hoy}
    g = P.get("galeria") or {}
    esc = [e for e in g.get("escenas") or [] if e.get("idea") and e.get("label") and len(e["label"].split()) <= 3]
    if (len(esc) >= 6 and 8 <= len(g.get("hook", "")) <= 46 and not PROHIBIDO.search(_txt(g.get("hook"), *[_txt(e["idea"], e["label"]) for e in esc]))
            and not difflib.get_close_matches(g["hook"], [p.get("hook", "") for p in banco["galeria"]], 1, 0.75)):
        out["galeria"] = {"id": f"t{hoy.replace('-', '')}g", "hook": g["hook"].strip(),
                          "cierre": (g.get("cierre") or "¿Con cuál te quedas?").strip()[:40],
                          "escenas": [{"idea": e["idea"].strip(), "label": e["label"].strip()} for e in esc[:6]], **sello}
    t = P.get("tips") or {}
    tips = [x for x in t.get("tips") or [] if x.get("tip") and x.get("idea") and len(x["tip"].split()) <= 7]
    if (len(tips) >= 5 and 8 <= len(t.get("hook", "")) <= 48 and re.match(r"^\d", t.get("hook", ""))
            and not PROHIBIDO.search(_txt(t.get("hook"), *[_txt(x["tip"], x["idea"]) for x in tips]))
            and not difflib.get_close_matches(t["hook"], [p.get("hook", "") for p in banco["tips"]], 1, 0.75)):
        out["tips"] = {"id": f"t{hoy.replace('-', '')}t", "hook": t["hook"].strip(),
                       "tips": [{"tip": x["tip"].strip(), "idea": x["idea"].strip()} for x in tips[:5]], **sello}
    a = P.get("antes_despues") or {}
    if a.get("descripcion") and len(a["descripcion"].split()) <= 22 and not PROHIBIDO.search(_txt(a.get("descripcion"), a.get("estilo"))):
        out["antes_despues"] = {"id": f"t{hoy.replace('-', '')}a", "tipo": "estancia", "descripcion": a["descripcion"].strip(),
                                "estilo": str(a.get("estilo") or "").strip()[:120], **sello}
    p = P.get("proceso") or {}
    if p.get("descripcion") and len(p["descripcion"].split()) <= 20 and not PROHIBIDO.search(p["descripcion"]):
        out["proceso"] = {"id": f"t{hoy.replace('-', '')}p", "tipo": "casa", "descripcion": p["descripcion"].strip(), **sello}
    return out


def main():
    forzar, prueba = "--forzar" in sys.argv, "--prueba" in sys.argv
    hoy = str(datetime.date.today())
    if not forzar and not prueba and os.path.exists(STAMP) and open(STAMP).read().strip() == hoy:
        return say("ya se cazaron las tendencias de hoy")
    T = buscar()
    say("tendencias:", "; ".join(x.get("tema", "") for x in T.get("temas") or [])[:300])
    banco = json.load(open(BANCO))
    P = piezas(T, banco)
    nuevas = valida(P, banco)
    say("piezas nuevas:", {k: v.get("hook") or v.get("descripcion") for k, v in nuevas.items()})
    tags = [h for h in (T.get("hashtags") or []) if re.fullmatch(r"#[\wáéíóúñü]{3,30}", h or "", re.I) and not PROHIBIDO.search(h)]
    res = {"fecha": hoy, "temas": T.get("temas"), "estilos": T.get("estilos"), "formatos": T.get("formatos"),
           "busquedas": T.get("busquedas"), "hashtags": [h.lower() for h in tags][:10], "quemado": T.get("quemado"),
           "por_tipo": P.get("por_tipo") or {}, "musica_tiktok": musica(), "fuentes": (T.get("fuentes") or [])[:8],
           "piezas": {k: v["id"] for k, v in nuevas.items()}}
    nb = (f"# Cuaderno de cazatendencias ({hoy})\n\n## Tendencias de la semana\n"
          + "\n".join(f"- {x.get('tema')}: {x.get('por_que')}" for x in T.get("temas") or [])
          + "\n\n## Estilos\n" + "\n".join(f"- {s}" for s in T.get("estilos") or [])
          + "\n\n## Para nuestro equipo\n" + "\n".join(f"- {n}" for n in P.get("notas") or [])
          + "\n\n## Ya quemado\n" + "\n".join(f"- {q}" for q in T.get("quemado") or [])
          + "\n\n## Música en tendencia (TikTok, España)\n" + "\n".join(f"- {m}" for m in res["musica_tiktok"]) + "\n")
    if prueba:
        print(json.dumps(res, ensure_ascii=False, indent=1)); print(json.dumps(nuevas, ensure_ascii=False, indent=1)); print(nb)
        return
    for k, v in nuevas.items():
        banco[k].append(v)
    json.dump(banco, open(BANCO, "w"), ensure_ascii=False, indent=1)
    json.dump(res, open(SALIDA, "w"), ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(CUADERNO), exist_ok=True)
    open(CUADERNO, "w").write(nb)
    open(STAMP, "w").write(hoy)
    say(f"{len(nuevas)} piezas de tendencia añadidas al banco")


def actuales():
    """Lo que usan las descripciones: tendencias de los últimos días (o {})."""
    try:
        T = json.load(open(SALIDA))
        if (datetime.date.today() - datetime.date.fromisoformat(T["fecha"])).days <= FRESCO_DIAS:
            return T
    except Exception:
        pass
    return {}


def fresca(p):
    try:
        return p.get("tendencia") and (datetime.date.today() - datetime.date.fromisoformat(p["fecha"])).days <= FRESCO_DIAS
    except Exception:
        return False


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                      # nunca bloquea el reel
        say("omitido:", str(e)[:300])
