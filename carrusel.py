"""Carrusel diario de UDA (Instagram + TikTok modo foto + LinkedIn como documento PDF): 5-8 diapositivas editoriales con
la identidad premium de UDA (negro y oro, TeX Gyre Adventor). Nada de pegatinas: tipografía, filetes de oro
y trazado técnico dibujado en código.

Qué es: un tema concreto (una sección del DB SI, el contenido del proyecto según el CTE, qué cuesta contratar frente a
delegar, qué incluye un Proyecto de Ejecución delegado...) explicado en diapositivas, un "¿Te atreves?" con una pieza
tipo test ya verificada del mismo tema y la solución + cierre con UDA en la última.
Bloque de cada día: lunes negocio · martes datos de proyecto · miércoles contratar o delegar · jueves servicios ·
viernes negocio · sábado datos de proyecto · domingo servicios. Se publica a las 18:00 en punto (PUBLISH_AT).

Rigor (igual que en los reels, más estricto):
- Todo sale SOLO de UN o DOS fragmentos reales de la fuente del tema (BOE o documentos/web de UDA).
- Cada término de cada diapositiva lleva su CITA LITERAL y el código comprueba que está en el fragmento; las cifras
  tienen que estar en el fragmento; un precio va como precio de referencia; nunca "UDA firma".
- Después, el verificador (modelo "pro") contrasta frase a frase diapositivas y descripción con el material. Si no
  pasa, se reescribe una vez y, si no, se prueba otro tema; si nada pasa, ese día no hay carrusel.

    python carrusel.py      -> genera y publica (DRY_RUN=true: solo genera; QUIZ_MOCK=1: sin IA, para probar el diseño)
"""
import datetime, json, math, os, random, re, sys
from PIL import Image, ImageDraw, ImageFilter

import fx
import marca
import questions as QB
from fx import CARBON_D, TERRACOTA, F_BOLD, F_REG, NEGRO, NEGRO_C, ORO, CREMA
# identidad premium negro y oro: los nombres de la paleta se mantienen por legibilidad del código
CARBON = CREMA                    # tinta principal (sobre negro)
WHITE = CREMA                     # texto sobre bandas oscuras
BRONCE = ARENA = ORO              # acentos
GRIS = (150, 144, 132)            # texto secundario
PIEDRA = (30, 29, 26)             # cajas sobre el fondo
PIEDRA_D = (40, 38, 34)
CARD = NEGRO_C                    # tarjetas (con filete de oro)

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "carruseles.json")
W, H = 1080, 1350                                        # 4:5, el formato vertical de carrusel de Instagram
M = 84                                                   # margen
MOCK = os.environ.get("QUIZ_MOCK") == "1"
PLAN = {0: "negocio", 1: "servicios", 2: "contratar", 3: "negocio", 4: "servicios", 5: "contratar", 6: "negocio"}   # sin BOE ni CTE
ETIQUETA = {"negocio": "FACTURAR MÁS EN TU DESPACHO", "contratar": "CONTRATAR O DELEGAR", "servicios": "LO QUE PUEDES DELEGAR",
            "proyecto": "DATOS DE PROYECTO"}
INK2 = (205, 198, 186)                                      # texto de lectura (más contraste que el gris de los documentos)


def F(path, size):
    return fx.font(path, int(size))


# ------------------------------------------------------------------ 1. tema y material
def log():
    try:
        return json.load(open(LOG))
    except Exception:
        return []


def pick_tema(bloque, seed, skip=()):
    """El tema del bloque que lleva más tiempo sin carrusel (los nunca usados primero), al azar entre empates."""
    import verifier as V
    last = {e.get("tema"): i for i, e in enumerate(log())}
    ts = [t for t, d in QB.cfg()["temas"].items() if bloque in d["bloques"] and t not in skip and V.chunks_for_tema(t)]
    rng = random.Random(seed); rng.shuffle(ts)
    ts.sort(key=lambda t: last.get(t, -1))
    return ts[0] if ts else None


def material(tema, seed):
    """1-2 fragmentos de la fuente (los menos usados en carruseles) + piezas verificadas del tema como contexto."""
    import verifier as V
    used = {}
    for e in log():
        for c in e.get("fragmentos") or []:
            used[c] = used.get(c, 0) + 1
    chunks = V.chunks_for_tema(tema)
    rng = random.Random(seed); rng.shuffle(chunks)
    chunks.sort(key=lambda c: used.get(c[1], 0))
    sel = chunks[:1]
    if sel and len(sel[0][2]) < 1600 and len(chunks) > 1:
        sel.append(chunks[1])
    v = QB.verif()
    ps = [p for p in QB.load() if p.get("tema") == tema and QB.publishable(p, v)][:12]
    txt = "\n\n".join(f"[{V.norma(k).get('corto')} · {lab}]\n{t[:5000]}" for k, lab, t in sel)
    ctx = "\n".join(f"- {QB.text_of(p)}" for p in ps)
    return sel, txt, ctx


def quiz_question(tema, seed):
    """Una pieza tipo test YA VERIFICADA del mismo tema para la diapositiva "¿Te atreves?" (o None)."""
    v = QB.verif()
    used = {x["id"] for x in QB.used()} | {e.get("quiz_id") for e in log()}
    qs = [p for p in QB.load() if p.get("tema") == tema and p["tipo"] == "test" and QB.fits(p) and (QB.publishable(p, v) or MOCK)]
    qs.sort(key=lambda p: p["id"] in used)
    return QB.prepare(qs[0], seed) if qs else None


# ------------------------------------------------------------------ 2. guion (IA) y verificación
ROLE = """Eres el EDITOR de los carruseles de UDA · Unión de Arquitectos (uniondearquitectos.com), un estudio online que hace
de departamento técnico externo para despachos de arquitectura. Tu público son fundadores y socios de despachos y
arquitectos autónomos de España que proyectan bloques, promociones y edificios de envergadura: quieren facturar más,
cobrar mejor su hora y dedicar su tiempo a proyectar. Haces carruseles para Instagram, TikTok y LinkedIn, PREMIUM y
elegantes, que un fundador GUARDA y ENVÍA a su socio: claros, rigurosos, con criterio de socio senior, nada de
obviedades ni tono de teletienda. ESPAÑOL DE ESPAÑA (peninsular), nunca latinoamericano: tú y vosotros (nunca "ustedes" para el público), vocabulario de España (ordenador, móvil, vale, coger, pedir cita, encargo, obra, plantilla, autónomo); nunca "computadora", "celular", "agendar", "checar", "platicar", "chamba", "tomar un encargo" por coger. Escribes en español de España, de colega a colega,
profesional y directo, sin promesas ni estadísticas; UDA nunca firma (la firma es del despacho)."""

SCHEMA = """{
 "subtema": str (el subtema concreto, 2-7 palabras),
 "titulo_lineas": [str, ...] (2-4 líneas MUY cortas del titular de portada, máx. 16 caracteres cada una, p. ej. ["Evacuación", "en 5 claves"]),
 "subtitulo": str (8-20 palabras: qué resuelve el carrusel en un proyecto real),
 "diapositivas": [ (3-5)
   {"titulo": str (1-5 palabras),
    "items": [ {"termino": str (1-6 palabras), "texto": str (6-28 palabras; marca 1-2 palabras clave con **asteriscos**), "cita": str (fragmento LITERAL de la fuente, 10-40 palabras, que respalda el item)} ] (2-3 items),
    "clave": str o "" (opcional, 6-20 palabras: la idea que no hay que olvidar, SOLO con datos de la fuente)} ],
 "referencia": str (norma y artículo/sección/apartado del fragmento, p. ej. "CTE, Parte I, Anejo I"),
 "caption_gancho": str (máx. 14 palabras, máx. 1 emoji, primera línea de la descripción),
 "caption_intro": str (25-60 palabras: por qué esto importa al redactar un proyecto),
 "caption_puntos": [str] (3-5 líneas cortas "Término → idea clave", empiezan por "▪️"),
 "reto": str (máx. 25 palabras: una pregunta para comentar)
}"""


def write(tema, bloque, txt, ctx, notes=None, avoid=()):
    import gemini, verifier
    prompt = f"""{ROLE}

TEMA: {QB.tema_titulo(tema)} · BLOQUE: {ETIQUETA[bloque]}
FUENTE (lo ÚNICO que puedes afirmar; no añadas ningún dato, cifra, apartado, excepción ni ejemplo que no esté aquí):
\"\"\"
{txt}
\"\"\"
Piezas ya verificadas del tema (contexto, mismas reglas): {ctx or 'ninguna'}
HECHOS CIERTOS DE UDA (solo para la descripción): {verifier.facts()}

Elige UN subtema concreto de la fuente que funcione muy bien como carrusel (qué exige, qué documentos lleva, diferencias
que se confunden, pasos, condiciones...). {("Evita estos subtemas ya publicados: " + "; ".join(avoid)) if avoid else ""}
Reglas: cada frase debe poder comprobarse en la fuente; nada de "siempre/nunca/todos" si la fuente no lo dice; precios
de UDA siempre como precio de referencia; el presupuesto cerrado se envía en 24 horas;
SOLO ventajas claras para el fundador que delega en UDA (más tiempo, más facturación, sin costes fijos, sin formar ni
despedir, presupuesto cerrado en 24 h que puede repercutir a su cliente, marca blanca); NUNCA condiciones de pago, cláusulas
ni nada que suene a letra pequeña o a riesgo para el despacho; lenguaje claro para el fundador de un despacho, sin jerga de coaching ("zona de genialidad", "mindset"...); la "clave" de
cada lámina aporta algo concreto (margen, horas o riesgo que se evita), nunca repite la tarjeta; español de España;
sin emojis dentro de las diapositivas; escribe SOLO lo que se lee.
{("CORRIGE estos problemas que encontró el verificador en tu versión anterior: " + json.dumps(notes, ensure_ascii=False)) if notes else ""}
Devuelve JSON exactamente con esta forma:
{SCHEMA}"""
    return gemini.ask(prompt, 0.6)


def _wc(s):
    return len(str(s or "").split())


def _nums(t):
    return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", str(t))}


def clean(c, src_texts):
    """Valida forma, longitudes, citas literales y cifras (lo que no cabe o no se puede comprobar se rechaza)."""
    import verifier as V, writer
    sp = lambda s: re.sub(r"\s+", " ", str(s or "")).strip()
    lines = [sp(x) for x in (c.get("titulo_lineas") or []) if sp(x)]
    if not 1 <= len(lines) <= 4 or any(len(x) > 18 for x in lines):
        raise ValueError("titular de portada no válido")
    slides = []
    for s in (c.get("diapositivas") or [])[:5]:
        items = [{"termino": sp(i.get("termino")), "texto": sp(i.get("texto")), "cita": sp(i.get("cita"))}
                 for i in (s.get("items") or [])[:3]]
        items = [i for i in items if 1 <= _wc(i["termino"]) <= 7 and 4 <= _wc(i["texto"]) <= 30
                 and V.quote_in(i["cita"], src_texts)]
        if len(items) >= 2 and 1 <= _wc(s.get("titulo")) <= 6:
            clave = sp(s.get("clave"))
            slides.append({"titulo": sp(s["titulo"]), "items": items, "clave": clave if 4 <= _wc(clave) <= 22 else ""})
    if len(slides) < 3:
        raise ValueError("menos de 3 diapositivas válidas (o citas que no están en la fuente)")
    pts = [sp(p) for p in (c.get("caption_puntos") or []) if 2 <= _wc(p) <= 16][:5]
    out = {"subtema": sp(c.get("subtema"))[:60], "titulo_lineas": lines, "subtitulo": sp(c.get("subtitulo")),
           "diapositivas": slides, "referencia": sp(c.get("referencia"))[:90],
           "caption_gancho": sp(c.get("caption_gancho")), "caption_intro": sp(c.get("caption_intro")),
           "caption_puntos": pts, "reto": sp(c.get("reto"))}
    if not 5 <= _wc(out["subtitulo"]) <= 24 or not 3 <= _wc(out["caption_gancho"]) <= 18 or not _wc(out["reto"]) <= 30:
        raise ValueError("subtítulo, gancho o reto fuera de medida")
    vals = out["titulo_lineas"] + [out["subtitulo"], out["caption_gancho"], out["caption_intro"], out["reto"]] + \
        out["caption_puntos"] + [x for s in slides for x in [s["titulo"], s["clave"]] + [i["termino"] for i in s["items"]]
                                 + [i["texto"] for i in s["items"]]]
    if any(writer.has_meta(v) for v in vals):
        raise ValueError("lleva indicaciones de diseño o de tono")
    extra = _nums(" ".join(vals)) - _nums(" ".join(src_texts) + V.facts()) - {"1", "2", "3", "4", "5"}
    if extra:
        raise ValueError(f"cifras que no están en la fuente: {sorted(extra)[:4]}")
    joined = " ".join(vals)
    if "€" in joined and not re.search(r"referencia|orientativ|estimativ", joined, re.I):
        raise ValueError("precio sin decir que es de referencia")
    if re.search(r"\bUDA\b[^.]{0,30}\b(firma|visa|asume la responsabilidad)", joined, re.I):
        raise ValueError("dice que UDA firma")
    return out


def verify(c, tema, txt):
    import gemini, verifier
    texts = {"titular": " ".join(c["titulo_lineas"]), "subtitulo": c["subtitulo"], "referencia": c["referencia"],
             "diapositivas": [{"titulo": s["titulo"], "items": s["items"], "clave": s["clave"]} for s in c["diapositivas"]],
             "descripcion": [c["caption_gancho"], c["caption_intro"]] + c["caption_puntos"] + [c["reto"]]}
    try:
        res = gemini.ask(f"""{verifier.ROLE}
Revisas un CARRUSEL del tema "{QB.tema_titulo(tema)}".
FUENTE (lo único que vale como verdad):
\"\"\"
{txt}
\"\"\"
HECHOS CIERTOS DE UDA: {verifier.facts()}

TEXTOS DEL CARRUSEL:
{json.dumps(texts, ensure_ascii=False, indent=1)}

Comprueba frase a frase: ¿todo lo que afirman está respaldado por la fuente (y cada item por su cita)? Es un problema
cualquier dato, cifra, apartado, excepción o generalización que no esté en la fuente, asociar una definición al término
equivocado, una referencia que no corresponde, un precio que no se presenta como precio de referencia, decir que UDA
firma, prometer resultados o un tono condescendiente.
Devuelve JSON: {{"ok": bool, "problemas": [{{"frase": str, "motivo": str}}]}}""", 0.1, careful=True)
    except Exception as e:
        return False, [{"frase": "-", "motivo": f"verificador no disponible: {str(e)[:150]}"}]
    probs = res.get("problemas") or []
    return bool(res.get("ok")) and not probs, probs


def content_for(tema, bloque, seed):
    sel, txt, ctx = material(tema, seed)
    if not sel:
        raise RuntimeError("sin fuente")
    src = [t for _, _, t in sel]
    if MOCK:
        return sel, mock_content(tema, bloque, sel)
    notes = None
    avoid = [e.get("subtema") for e in log() if e.get("tema") == tema and e.get("subtema")]
    for attempt in range(2):
        try:
            c = clean(write(tema, bloque, txt, ctx, notes, avoid), src)
        except Exception as e:
            print(f"carrusel: guion no válido ({str(e)[:150]})", flush=True); notes = [str(e)[:150]]; continue
        ok, probs = verify(c, tema, txt)
        if ok:
            print(f"carrusel: verificado ({c['subtema']})", flush=True)
            return sel, c
        notes = probs
        print("carrusel: el verificador pide cambios:", json.dumps(probs, ensure_ascii=False)[:400], flush=True)
    raise RuntimeError(f"no hay carrusel verificado para {QB.tema_titulo(tema)}")


def mock_content(tema, bloque, sel):
    """Contenido de PRUEBA de diseño (sin IA): frases recortadas del propio fragmento."""
    frases = [f for f in re.split(r"(?<=[.:])\s+", " ".join(t for _, _, t in sel).replace("\n", " ")) if 6 <= _wc(f) <= 28][:12]
    while len(frases) < 9:
        frases.append("Frase de prueba para comprobar el diseño del carrusel en el móvil.")
    sl = []
    for k in range(3):
        its = [{"termino": " ".join(f.split()[:3]).strip(".:,"), "texto": "**" + f.split()[0] + "** " + " ".join(f.split()[1:]),
                "cita": f} for f in frases[k * 3:k * 3 + 3]]
        sl.append({"titulo": ["Lo esencial", "Lo que se confunde", "Antes de entregar"][k], "items": its,
                   "clave": "Idea clave de prueba para ver el bloque carbón." if k == 1 else ""})
    return {"subtema": "Prueba de diseño", "titulo_lineas": ["Prueba de", "carrusel", "UDA"],
            "subtitulo": "Texto de prueba del subtítulo para comprobar cómo respira la portada del carrusel.",
            "diapositivas": sl, "referencia": "PRUEBA · " + sel[0][1][:40], "caption_gancho": "Prueba de carrusel 📐",
            "caption_intro": "Texto de prueba.", "caption_puntos": ["▪️ Uno → idea", "▪️ Dos → idea"], "reto": "¿Lo revisas siempre?"}


# ------------------------------------------------------------------ 3. dibujo
def background(seed, dark=False):
    im = Image.new("RGB", (W, H), NEGRO); d = ImageDraw.Draw(im, "RGBA")   # RGB: el alfa se mezcla
    line = ORO + (9,)
    strong = ORO + (17,)
    for k, y in enumerate(range(0, H, 36)):
        d.line([(0, y), (W, y)], fill=strong if k % 5 == 0 else line, width=1)
    for k, x in enumerate(range(0, W, 36)):
        d.line([(x, 0), (x, H)], fill=strong if k % 5 == 0 else line, width=1)
    return im.convert("RGBA")


def ornament(w, h, col=BRONCE, seed=0):
    """Trazado técnico dibujado en código: planta esquemática con ejes, muros y línea de cota (sin texto)."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    c = tuple(col[:3]) + (255,); c2 = tuple(col[:3]) + (120,)
    x0, y0, x1, y1 = 30, 40, w - 30, h - 60
    for x in (x0, (x0 + x1) // 2, x1):                                  # ejes
        for yy in range(0, h, 28):
            d.line([(x, yy), (x, yy + 14)], fill=c2, width=2)
    d.rectangle([x0, y0, x1, y1], outline=c, width=8)                   # muros exteriores
    xm = rng.randint(int(x0 + (x1 - x0) * 0.35), int(x0 + (x1 - x0) * 0.6))
    ym = rng.randint(int(y0 + (y1 - y0) * 0.35), int(y0 + (y1 - y0) * 0.6))
    d.line([(xm, y0), (xm, ym - 40)], fill=c, width=5); d.line([(xm, ym + 40), (xm, y1)], fill=c, width=5)
    d.line([(x0, ym), (xm - 50, ym)], fill=c, width=5)
    d.arc([xm - 80, ym - 40, xm, ym + 40], 270, 360, fill=c2, width=3)  # puerta
    d.line([(x1 - 120, y0), (x1 - 40, y0)], fill=(0, 0, 0, 0), width=10)  # hueco de ventana
    d.line([(x1 - 120, y0 - 6), (x1 - 40, y0 - 6)], fill=c2, width=2); d.line([(x1 - 120, y0 + 6), (x1 - 40, y0 + 6)], fill=c2, width=2)
    d.line([(x0, h - 22), (x1, h - 22)], fill=c, width=2)               # cota
    for x in (x0, x1):
        d.line([(x - 10, h - 12), (x + 10, h - 32)], fill=c, width=3)
    return im


def _rich_tokens(text):
    out, bold = [], False
    for part in re.split(r"(\*\*)", text):
        if part == "**":
            bold = not bold; continue
        for w in part.split():
            if out and re.fullmatch(r"[.,;:!?)»…]+", w):
                out[-1] = (out[-1][0] + w, out[-1][1])
            else:
                out.append((w, bold))
    return out


def rich(text, size, maxw, color=INK2, hi=CARBON, path=F_REG, bold_path=F_BOLD, align="left", gap=1.32, draw_on=None, xy=(0, 0)):
    """Texto con palabras clave en negrita (en tinta más clara, sin subrayado). Devuelve la altura (y dibuja si draw_on)."""
    toks = _rich_tokens(text)
    fn, fb = F(path, size), F(bold_path, size)
    sp = fn.getlength(" ")
    lines, cur, x = [], [], 0.0
    for w, b in toks:
        wl = (fb if b else fn).getlength(w)
        if cur and x + wl > maxw:
            lines.append((cur, x - sp)); cur, x = [], 0.0
        cur.append((w, b, x)); x += wl + sp
    if cur:
        lines.append((cur, x - sp))
    lh = int(size * gap)
    if draw_on is not None:
        d = ImageDraw.Draw(draw_on, "RGBA")
        for li, (ws, lw) in enumerate(lines):
            ox = xy[0] + ((maxw - lw) / 2 if align == "center" else 0)
            y = xy[1] + li * lh
            for w, b, x in ws:
                d.text((ox + x, y), w, font=fb if b else fn, fill=hi if b else color)
    return lh * len(lines)


def header(im, n, total, dark=False):
    lg = fx.logo(44, WHITE if dark else CARBON, ARENA if dark else GRIS, align="left")
    im.alpha_composite(lg, (M, 54))
    d = ImageDraw.Draw(im)
    if total:
        t = f"{n:02d} / {total:02d}"; f = F(F_REG, 28)
        d.text((W - M - f.getlength(t), 66), t, font=f, fill=ARENA if dark else GRIS)
    d.line([(M, 138), (W - M, 138)], fill=(ARENA if dark else CARBON), width=2)


def footer(im, txt=None, dark=False):
    d = ImageDraw.Draw(im); f = F(F_REG, 24)
    t = txt or f"{marca.HANDLE} · {marca.WEB}"
    d.text((M, H - 64), t[:80], font=f, fill=ARENA if dark else GRIS)


def label(txt, col=BRONCE, size=28):
    return fx.spaced(txt, F_BOLD, size, col, 0.08)


def slide_cover(c, bloque, tema, total, seed):
    im = background(seed); d = ImageDraw.Draw(im)
    top = 760
    d.rectangle([0, 0, W, top], fill=NEGRO_C); d.rectangle([0, top - 4, W, top], fill=ORO)
    lg = fx.logo(44, WHITE, ARENA, align="left"); im.alpha_composite(lg, (M, 54))
    f = F(F_REG, 28); t = f"01 / {total:02d}"
    d.text((W - M - f.getlength(t), 66), t, font=f, fill=ARENA)
    corto = QB.tema_corto(tema).upper()
    lab = label(ETIQUETA[bloque] if tema.startswith("uda_") else f"{ETIQUETA[bloque]} · {corto}", ARENA, 26)
    im.alpha_composite(lab, (M, 200))
    n = len(c["titulo_lineas"])
    hs = rich(c["subtitulo"], 38, W - 2 * M - 40, color=ARENA, hi=WHITE)
    size = {1: 150, 2: 132, 3: 112, 4: 96}[n]
    while size > 64 and (max(F(F_BOLD, size).getlength(l) for l in c["titulo_lineas"]) > W - 2 * M
                         or 262 + n * size * 1.08 + 60 + hs + 40 > top):
        size -= 4
    y = 262
    for l in c["titulo_lineas"]:
        d.text((M, y), l, font=F(F_BOLD, size), fill=WHITE); y += int(size * 1.08)
    d.rectangle([M, y + 14, M + 120, y + 22], fill=BRONCE)
    rich(c["subtitulo"], 38, W - 2 * M - 40, color=ARENA, hi=WHITE, draw_on=im, xy=(M, y + 50))
    orn = ornament(560, 380, BRONCE, seed)
    im.alpha_composite(orn, (W - M - orn.width + 20, top + 60))
    sw = fx.pill("DESLIZA  →", 34, ORO, NEGRO, padx=30, pady=14, radius=4)
    im.alpha_composite(sw, (M, top + 120))
    ref = c.get("referencia")
    if ref:
        rich("Fuente: " + ref, 26, 380, color=GRIS, draw_on=im, xy=(M, top + 220))
    footer(im)
    return im


def slide_content(s, n, total, seed, ref):
    im = background(f"{seed}-{n}"); header(im, n, total); d = ImageDraw.Draw(im, "RGBA")
    num = f"{n - 1:02d}"
    for scale in (1.0, 0.94, 0.88, 0.82, 0.76, 0.7, 0.64):
        ts, term, body = 70 * scale, 44 * scale, 36 * scale
        th = rich(s["titulo"], ts, W - 2 * M - 150, path=F_BOLD)
        cards = []
        for it in s["items"]:
            ht = rich(it["termino"], term, W - 2 * M - 70, path=F_BOLD)
            hb = rich(it["texto"], body, W - 2 * M - 70)
            cards.append(int(ht + hb + 74 * scale))
        kh = (rich(s["clave"], body, W - 2 * M - 80, path=F_BOLD) + 110 * scale) if s["clave"] else 0
        need = 180 + th + 40 + sum(cards) + 24 * len(cards) + kh + 120
        if need <= H:
            break
    y = 180
    d.text((M, y - 6), num, font=F(F_BOLD, ts * 1.15), fill=BRONCE)
    rich(s["titulo"], ts, W - 2 * M - 150, color=CARBON, path=F_BOLD, draw_on=im, xy=(M + 150, y + 6)); y += max(th, ts * 1.2) + 40
    for it, ch in zip(s["items"], cards):
        d.rectangle([M, y, W - M, y + ch], fill=CARD)
        d.rectangle([M, y, W - M, y + 6], fill=BRONCE)
        ht = rich(it["termino"], term, W - 2 * M - 70, color=CARBON, path=F_BOLD, draw_on=im, xy=(M + 35, y + 30 * scale))
        rich(it["texto"], body, W - 2 * M - 70, draw_on=im, xy=(M + 35, y + 30 * scale + ht + 6))
        y += ch + 24
    if s["clave"]:
        d.rectangle([M, y, W - M, y + kh], fill=ORO)
        im.alpha_composite(label("CLAVE", NEGRO, 24), (M + 35, int(y + 30 * scale)))
        rich(s["clave"], body, W - 2 * M - 80, color=NEGRO, hi=NEGRO, path=F_BOLD, draw_on=im, xy=(M + 35, y + 30 * scale + 44))
    footer(im, ("Fuente: " + ref) if ref else None)
    return im


def slide_quiz(P, n, total, seed):
    im = background(f"{seed}-quiz"); header(im, n, total); d = ImageDraw.Draw(im, "RGBA")
    for sc in (1.0, 0.92, 0.85, 0.78, 0.7, 0.62):
        qs, os_ = 46 * sc, 38 * sc
        qh = rich(P["pregunta"], qs, W - 2 * M - 70, path=F_BOLD)
        ohs = [max(92 * sc, rich(o, os_, W - 2 * M - 160) + 44 * sc) for o in P["op"]]
        need = 180 + 120 + qh + 90 + sum(ohs) + 16 * 4 + 140
        if need <= H:
            break
    y = 180
    d.text((M, y), "¿Te atreves?", font=F(F_BOLD, 86), fill=CARBON); y += 120
    d.rectangle([M, y, W - M, y + qh + 60], fill=CARD); d.rectangle([M, y, W - M, y + 6], fill=BRONCE)
    rich(P["pregunta"], qs, W - 2 * M - 70, color=CARBON, path=F_BOLD, draw_on=im, xy=(M + 35, y + 30)); y += qh + 90
    for k, (o, h_) in enumerate(zip(P["op"], ohs)):
        oh = rich(o, os_, W - 2 * M - 160)
        d.rectangle([M, y, W - M, y + h_], fill=PIEDRA_D)
        r = 30 * min(1, sc + 0.1)
        d.rectangle([M + 30, y + h_ / 2 - r, M + 30 + 2 * r, y + h_ / 2 + r], fill=CARBON)
        f = F(F_BOLD, 36 * min(1, sc + 0.1)); L = QB.LETTERS[k]; bb = f.getbbox(L)
        d.text((M + 30 + r - (bb[0] + bb[2]) / 2, y + h_ / 2 - (bb[1] + bb[3]) / 2), L, font=f, fill=WHITE)
        rich(o, os_, W - 2 * M - 160, color=CARBON, draw_on=im, xy=(M + 120, y + (h_ - oh) / 2 + 2)); y += h_ + 16
    p = fx.pill("LA SOLUCIÓN, EN LA ÚLTIMA IMAGEN  →", 30, ORO, NEGRO, padx=28, pady=14, radius=4)
    im.alpha_composite(p, (M, int(min(H - p.height - 90, y + 16))))
    footer(im)
    return im


def slide_cta(P, n, total, seed):
    im = background(f"{seed}-cta", dark=True); header(im, n, total, dark=True); d = ImageDraw.Draw(im, "RGBA")
    y = 180
    if P:
        im.alpha_composite(label("SOLUCIÓN", ARENA, 28), (M, y)); y += 56
        txt = f"**{P['letra']}.** {P['op'][P['ok']]}"
        ex = P.get("explicacion") or ""
        ex = ex if len(ex.split()) <= 40 else ""
        h1 = rich(txt, 44, W - 2 * M - 70, path=F_BOLD); h2 = rich(ex, 32, W - 2 * M - 70) if ex else 0
        d.rectangle([M, y, W - M, y + h1 + h2 + 76], fill=PIEDRA); d.rectangle([M, y, W - M, y + 6], fill=BRONCE)
        rich(txt, 44, W - 2 * M - 70, color=CARBON, path=F_BOLD, draw_on=im, xy=(M + 35, y + 32))
        if ex:
            rich(ex, 32, W - 2 * M - 70, draw_on=im, xy=(M + 35, y + 44 + h1))
        y += h1 + h2 + 120
    lg = fx.logo(96, WHITE, ARENA)
    im.alpha_composite(lg, ((W - lg.width) // 2, y)); y += lg.height + 34
    cl = fx.text_block(marca.CLAIM, F_BOLD, 44, W - 2 * M, WHITE, align="center")
    im.alpha_composite(cl, ((W - cl.width) // 2, y)); y += cl.height + 12
    sub = fx.text_block("Proyectos Básicos y de Ejecución · Precio cerrado · Tu firma al final", F_REG, 28, W - 2 * M, ARENA,
                        align="center")
    im.alpha_composite(sub, ((W - sub.width) // 2, y)); y += sub.height + 30
    for a, b in (("Guárdalo", "para tu próximo proyecto"), ("Envíaselo", "a tu socio del despacho")):
        f1, f2 = F(F_BOLD, 34), F(F_REG, 34)
        wtot = f1.getlength(a + " ") + f2.getlength(b)
        x = (W - wtot) / 2
        d.text((x, y), a + " ", font=f1, fill=WHITE); d.text((x + f1.getlength(a + " "), y), b, font=f2, fill=ARENA); y += 52
    y += 14
    for v_ in marca.VENTAJAS_CIERRE:
        lv = fx.text_block("✓  " + v_, F_REG, 32, W - 2 * M, CREMA, align="center")
        im.alpha_composite(lv, ((W - lv.width) // 2, int(y))); y += 46
    y += 10
    p1 = fx.pill(marca.CTA.upper(), 28, ORO, NEGRO, padx=26, pady=12, radius=4)
    im.alpha_composite(p1, ((W - p1.width) // 2, int(y))); y += p1.height + 20
    p2 = fx.pill(marca.WEB, 50, CREMA, NEGRO, padx=38, pady=16, radius=4)
    im.alpha_composite(p2, ((W - p2.width) // 2, int(min(y, H - p2.height - 90))))
    footer(im, dark=True)
    return im


MIN_SCORE = float(os.environ.get("REVIEW_MIN_SCORE", "8"))


def review(paths, c, tema):
    """Directora de arte + editora: puntúa el carrusel terminado (imágenes reales). Devuelve (nota, problemas)."""
    import base64, io, gemini
    parts = [{"text": f"""Eres directora de arte y editora jefa de una revista de arquitectura. Revisas un carrusel de UDA ·
Unión de Arquitectos (tema: {QB.tema_titulo(tema)} · {c['subtema']}) para Instagram y LinkedIn. Público: fundadores de
despachos y arquitectos autónomos que hacen bloques de viviendas y proyectos de envergadura; buscan facturar más y ganar
tiempo, y leen en el móvil entre obra y obra.
Puntúa 1-10: utilidad real para ese fundador (ideas claras y sencillas, sin jerga innecesaria; nada de obviedades vacías),
claridad y jerarquía, legibilidad en el móvil, acabado premium y elegante, coherencia de marca (identidad negro y oro:
fondo negro, filetes y acentos dorados, texto crema) y probabilidad de que lo guarden o lo envíen a un socio. El diseño
oscuro es intencionado: no lo penalices.
Un 8 es el mínimo para publicar. Devuelve JSON: {{"overall": number, "problemas": [str]}}"""}]
    for p in paths:
        im = Image.open(p).convert("RGB"); im.thumbnail((540, 675)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}})
    try:
        r = gemini.ask(parts, 0.3)
        return float(r.get("overall") or 0), r.get("problemas") or []
    except Exception as e:
        return 0.0, [f"revisor no disponible: {str(e)[:120]}"]


def render(c, P, bloque, tema, out_dir, seed):
    os.makedirs(out_dir, exist_ok=True)
    total = 1 + len(c["diapositivas"]) + (1 if P else 0) + 1
    slides = [slide_cover(c, bloque, tema, total, seed)]
    for i, s in enumerate(c["diapositivas"]):
        slides.append(slide_content(s, i + 2, total, seed, c.get("referencia")))
    if P:
        slides.append(slide_quiz(P, len(slides) + 1, total, seed))
    slides.append(slide_cta(P, len(slides) + 1, total, seed))
    paths, rgb = [], []
    for i, s in enumerate(slides):
        p = os.path.join(out_dir, f"carrusel_{i + 1:02d}.jpg")
        r = s.convert("RGB"); r.save(p, "JPEG", quality=92, optimize=True)        # Instagram solo acepta JPEG por URL
        paths.append(p); rgb.append(r)
    pdf = os.path.join(out_dir, "carrusel.pdf")                                   # LinkedIn: carrusel como documento
    rgb[0].save(pdf, "PDF", save_all=True, append_images=rgb[1:], resolution=150)
    return paths, pdf


# ------------------------------------------------------------------ 4. descripción
TAGS = ["#arquitectura", "#arquitectos", "#normativa", "#CTE", "#despachodearquitectura"]


def caption(c, P):
    pts = "\n".join(c["caption_puntos"])
    quiz = "\n\n🎯 En la penúltima imagen, una pregunta tipo test: ¿la aciertas? Dime tu letra en comentarios." if P else ""
    ref = f"\n\nFuente: {c['referencia']}" if c.get("referencia") else ""
    return (f"{c['caption_gancho']}\n\n{c['caption_intro']}\n\n{pts}{ref}{quiz}\n\n💬 {c['reto']}\n\n"
            f"📌 Guárdalo para tu próximo proyecto. 📤 Envíaselo a tu socio del despacho.\n\n"
            f"{marca.CTA_CAPTION}\n\n" + " ".join(TAGS))


# ------------------------------------------------------------------ 5. publicar
def publish(paths, pdf, cap, c):
    import publish_zernio as Z
    res = {}
    if not os.environ.get("ZERNIO_API_KEY"):
        return {"zernio": "error: falta el secreto ZERNIO_API_KEY (se usa para alojar las imágenes)"}
    try:
        urls = [Z.upload(p) for p in paths]
    except Exception as e:
        return {"error": f"no se pudieron subir las imágenes: {str(e)[:200]}"}
    title = " ".join(c["titulo_lineas"])
    try:
        if os.environ.get("IG_TOKEN"):                    # Instagram directo por la API de Meta (gratis)
            import publish_ig as IG
            res["instagram_carrusel"] = f"ig:{IG.publish_image_carousel(urls, cap)['id']}"
        else:
            res["instagram_carrusel"] = Z.instagram_carousel(urls, cap)
    except Exception as e:
        res["instagram_carrusel"] = f"error: {str(e)[:300]}"
    if os.environ.get("TIKTOK", "true").lower() != "false":
        try:
            res["tiktok_carrusel"] = Z.tiktok_photos(urls, title, cap)
        except Exception as e:
            res["tiktok_carrusel"] = f"error: {str(e)[:300]}"
    if os.environ.get("LINKEDIN", "carrusel").lower() == "carrusel":
        if Z.linkedin_used_today():
            print("LinkedIn: hoy ya hay una publicación; no se publica otra", flush=True)
        else:
            try:
                res["linkedin_documento"] = Z.linkedin_document(Z.upload(pdf), cap, title)
            except Exception as e:
                res["linkedin_documento"] = f"error: {str(e)[:300]}"
    return res


# ------------------------------------------------------------------ main
def main():
    today = datetime.date.today()
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    if not dry and os.environ.get("FORCE") != "true" and any(e.get("fecha") == str(today) and e.get("publicado") for e in log()):
        print("ya se publicó el carrusel de hoy"); return
    if not MOCK and not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Falta GEMINI_API_KEY: sin verificador no se publica ningún carrusel.")
    if os.environ.get("PUBLISH_AT") and any(e.get("fecha") == str(today) and e.get("publicado") for e in log()):
        print("carrusel: hoy ya se publicó uno (a mano); el programado no repite", flush=True)
        return
    seed = str(today)
    bloque = os.environ.get("CARRUSEL_BLOQUE") or "auto"
    bloque = PLAN[today.weekday()] if bloque not in ETIQUETA else bloque
    out_dir = os.path.join(HERE, "out", f"carrusel_{today}")
    tried, c, tema, sel = [], None, os.environ.get("CARRUSEL_TEMA") or None, []
    for attempt in range(3):
        tema = tema if (attempt == 0 and tema) else pick_tema(bloque, f"{seed}-{attempt}", tried)
        if not tema:
            break
        tried.append(tema)
        try:
            sel, c = content_for(tema, bloque, seed)
            break
        except Exception as e:
            print(f"carrusel: tema {tema} descartado: {str(e)[:200]}", flush=True); c = None
    if not c:
        raise SystemExit("hoy no hay carrusel verificado (mejor no publicar que publicar un error)")
    P = None                                               # sin test: no es contenido de repaso
    paths, pdf = render(c, P, bloque, tema, out_dir, seed)
    score = None
    if not MOCK:                                           # nivel premium: por debajo de 8 no se publica
        score, probs = review(paths, c, tema)
        print(f"carrusel: revisión {score}/10 {probs[:3]}", flush=True)
        if score < MIN_SCORE:
            for attempt in range(2):
                tema2 = pick_tema(bloque, f"{seed}-r{attempt}", tried) or tema
                tried.append(tema2)
                try:
                    sel2, c2 = content_for(tema2, bloque, f"{seed}-r{attempt}")
                except Exception as e:
                    print("carrusel: reintento sin contenido:", str(e)[:150], flush=True); continue
                P2 = None
                paths2, pdf2 = render(c2, P2, bloque, tema2, out_dir, seed)
                s2, probs = review(paths2, c2, tema2)
                print(f"carrusel: reintento {tema2} {s2}/10 {probs[:3]}", flush=True)
                if s2 >= MIN_SCORE:
                    tema, sel, c, P, paths, pdf, score = tema2, sel2, c2, P2, paths2, pdf2, s2
                    break
            if score < MIN_SCORE:
                raise SystemExit(f"hoy no hay carrusel con nota suficiente ({score}/10, mínimo {MIN_SCORE:g})")
    cap = caption(c, P)
    open(os.path.join(out_dir, "descripcion.txt"), "w").write(cap)
    print(f"carrusel: {QB.tema_titulo(tema)} · {c['subtema']} · {len(paths)} imágenes", flush=True)
    if not dry and os.environ.get("PUBLISH_AT"):           # espera a las 18:00 en punto (hora de España)
        try:
            import time
            from zoneinfo import ZoneInfo
            hh, mm = map(int, os.environ["PUBLISH_AT"].split(":"))
            now = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
            secs = (now.replace(hour=hh, minute=mm, second=0, microsecond=0) - now).total_seconds()
            if 0 < secs <= 3600:
                print(f"carrusel: espero {secs / 60:.1f} min para publicar a las {hh}:{mm:02d}", flush=True)
                time.sleep(secs)
        except Exception as e:
            print("carrusel: sin espera:", str(e)[:100], flush=True)
    res = {} if dry else publish(paths, pdf, cap, c)
    print("publicación:", json.dumps(res, ensure_ascii=False), flush=True)
    ok = any(isinstance(v, str) and not v.startswith("error") for v in res.values())
    entry = {"fecha": str(today), "bloque": bloque, "tema": tema, "subtema": c["subtema"], "titulo": " ".join(c["titulo_lineas"]),
             "fragmentos": [lab for _, lab, _ in sel], "quiz_id": P and P["id"], "imagenes": len(paths), "nota": score,
             "publicado": ok,
             "destinos": res, "dry_run": dry}
    if not dry:                                            # las pruebas no cuentan como tema usado
        L = log(); L.append(entry); json.dump(L, open(LOG, "w"), ensure_ascii=False, indent=0)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(
            f"## Carrusel {today}\n- Bloque: {bloque} · Tema: {QB.tema_titulo(tema)} · {c['subtema']}\n- Imágenes: {len(paths)}\n"
            f"- Publicación: {json.dumps(res, ensure_ascii=False)}\n")
    if not dry and not ok:
        raise SystemExit("el carrusel no se pudo publicar en ningún sitio")


class _Tee:
    """Copia la salida a carrusel_estado.txt (se guarda en el repositorio: así se ve por qué no se publicó)."""
    def __init__(self, a, b):
        self.a, self.b = a, b

    def write(self, s):
        self.a.write(s); self.b.write(s); return len(s)

    def flush(self):
        self.a.flush(); self.b.flush()


if __name__ == "__main__":
    _f = open(os.path.join(HERE, "carrusel_estado.txt"), "w")
    _f.write(f"Carrusel {datetime.datetime.utcnow():%Y-%m-%d %H:%M} UTC\n")
    sys.stdout = _Tee(sys.stdout, _f)
    try:
        main()
    except SystemExit as e:
        print("NO PUBLICADO:", e); raise
    except Exception as e:
        import traceback; traceback.print_exc(file=sys.stdout); raise
    finally:
        sys.stdout = sys.stdout.a; _f.close()
