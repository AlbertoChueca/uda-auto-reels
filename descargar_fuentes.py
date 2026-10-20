"""Descarga las fuentes del generador y del verificador (fuentes/fuentes.json):

- tipo "boe": texto oficial del BOE. Modo "consolidado" = texto vigente (API de datos abiertos, legislación consolidada);
  "diario" = texto tal y como se publicó en el BOE del día (sirve para los reales decretos que publicaron los DB del CTE);
  "auto" = primero consolidado y, si no hay, diario. Antes de guardar se comprueba que el TÍTULO descargado contiene las
  palabras "clave" (p. ej. "314/2006"): un id equivocado nunca se cuela como fuente; si no coincide, se busca por título.
- tipo "web": la web de UDA (uniondearquitectos.com), convertida a texto.
- tipo "uda": documentos de UDA ya transcritos en el repositorio (solo se comprueba que están).
- "manual": pega el texto en fuentes/<archivo>.

    python descargar_fuentes.py            # descarga las que falten (la web siempre se refresca)
    python descargar_fuentes.py --todas    # vuelve a descargarlas todas (p. ej. tras una reforma)

Cada texto se guarda en fuentes/<archivo> con una cabecera "# Título · id · fecha". Escribe fuentes/estado.md.
"""
import datetime, html, json, os, re, sys, xml.etree.ElementTree as ET
from html.parser import HTMLParser
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "fuentes")
API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
DIARIO = "https://www.boe.es/diario_boe/xml.php"
HDR = {"Accept": "application/xml", "User-Agent": "uda-reels/1.0 (+https://uniondearquitectos.com)"}


def _get(url, **kw):
    r = requests.get(url, headers=kw.pop("headers", HDR), timeout=120, **kw)
    r.raise_for_status()
    return r


def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ------------------------------------------------------------------ BOE
def titulo(boe_id):
    root = ET.fromstring(_get(f"{API}/id/{boe_id}/metadatos").content)
    t = root.find(".//titulo")
    return (t.text or "").strip() if t is not None else ""


def buscar(q):
    """Busca por título en la API del BOE y devuelve [(id, título)]. Si la búsqueda no está disponible devuelve []."""
    try:
        query = json.dumps({"query": {"query_string": {"query": f'titulo:({q})'}}})
        root = ET.fromstring(_get(API, params={"query": query, "limit": 10}).content)
        out = []
        for it in root.iter("item"):
            i, t = it.find("identificador"), it.find("titulo")
            if i is not None and t is not None:
                out.append((i.text.strip(), (t.text or "").strip()))
        return out
    except Exception as e:
        print("  búsqueda no disponible:", str(e)[:120]); return []


def texto_consolidado(boe_id):
    """Texto vigente: para cada bloque, la última versión; párrafos separados por saltos de línea."""
    root = ET.fromstring(_get(f"{API}/id/{boe_id}/texto").content)
    parts = []
    for b in list(root.iter("bloque")) or [root]:
        vers = b.findall("version") or [b]
        for el in vers[-1].iter():
            if el.tag in ("p", "titulo") and "".join(el.itertext()).strip():
                parts.append(_clean("".join(el.itertext())))
    return "\n".join(parts)


def diario(boe_id):
    """(título, texto) del documento tal y como se publicó en el BOE (XML del diario)."""
    root = ET.fromstring(_get(DIARIO, params={"id": boe_id}).content)
    t = root.find(".//metadatos/titulo")
    tx = root.find(".//texto")
    parts = []
    if tx is not None:
        in_table = {id(d) for tb in tx.iter("table") for d in tb.iter() if d is not tb}
        for el in tx.iter():
            if el.tag == "tr":                                       # tablas: una fila por línea, celdas con " | "
                cells = [_clean("".join(c.itertext())) for c in el if c.tag in ("td", "th")]
                if any(cells):
                    parts.append(" | ".join(cells))
            elif id(el) not in in_table and el.tag in ("p", "h1", "h2", "h3", "h4", "h5", "li") \
                    and "".join(el.itertext()).strip():
                parts.append(_clean("".join(el.itertext())))
    return (_clean(t.text) if t is not None else ""), "\n".join(parts)


def boe(n):
    """Devuelve (id, título, texto, modo) o lanza excepción."""
    modo = n.get("modo", "consolidado")
    cands = [n["boe"]] if n.get("boe") else []
    errores = []
    for attempt in range(2):
        for bid in cands:
            if modo in ("consolidado", "auto"):
                try:
                    t = titulo(bid)
                    if all(c.lower() in t.lower() for c in n.get("clave", [])):
                        txt = texto_consolidado(bid)
                        if len(txt) >= 2000:
                            return bid, t, txt, "consolidado"
                        errores.append(f"{bid}: consolidado demasiado corto")
                    else:
                        errores.append(f"{bid}: el título no coincide ({t[:80]})")
                except Exception as e:
                    errores.append(f"{bid} consolidado: {str(e)[:80]}")
            if modo in ("diario", "auto"):
                try:
                    t, txt = diario(bid)
                    if all(c.lower() in t.lower() for c in n.get("clave", [])) and len(txt) >= 2000:
                        return bid, t, txt, "diario"
                    errores.append(f"{bid} diario: título '{t[:60]}' / {len(txt)} caracteres")
                except Exception as e:
                    errores.append(f"{bid} diario: {str(e)[:80]}")
        if attempt == 0 and n.get("buscar"):
            cands = [i for i, _ in buscar(n["buscar"]) if i not in cands]
        else:
            break
    raise RuntimeError("; ".join(errores)[-400:] or "no encontrada")


# ------------------------------------------------------------------ web de UDA
class _Text(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "summary", "details",
             "header", "footer", "blockquote", "figcaption", "button", "a", "dt", "dd"}

    def __init__(self):
        super().__init__(); self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "template"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "template"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def web(url):
    r = _get(url, headers={"User-Agent": HDR["User-Agent"], "Accept": "text/html"})
    p = _Text(); p.feed(r.text)
    lines, seen = [], set()
    for l in "".join(p.out).split("\n"):
        l = _clean(html.unescape(l))
        if len(l) >= 3 and l not in seen and not l.lower().startswith(("cookie", "aceptar", "rechazar")):
            seen.add(l); lines.append(l)
    return "\n".join(lines)


# ------------------------------------------------------------------ main
def main(todas=False):
    cfg = json.load(open(os.path.join(DIR, "fuentes.json")))
    rows = [f"# Estado de las fuentes ({datetime.date.today()})\n", "| fuente | estado |", "|---|---|"]
    for k, n in cfg["normas"].items():
        path = os.path.join(DIR, n["archivo"])
        tipo = n.get("tipo", "boe")
        if tipo == "uda" or n.get("manual"):
            ok = os.path.exists(path)
            rows.append(f"| {n['titulo']} | {'✅ en el repositorio' if ok else '✋ falta: pega su texto en fuentes/' + n['archivo']} |")
            continue
        if os.path.exists(path) and not todas and tipo != "web":
            rows.append(f"| {n['titulo']} | ✅ ya estaba |"); continue
        print("•", n["titulo"], flush=True)
        try:
            if tipo == "web":
                txt = web(n["url"])
                if len(txt) < 500:
                    raise RuntimeError("la página no tiene texto suficiente")
                open(path, "w").write(f"# {n['titulo']} · {n['url']} · descargado {datetime.date.today()}\n\n{txt}\n")
                rows.append(f"| {n['titulo']} | ✅ {len(txt) // 1000} mil caracteres |")
                continue
            bid, t, txt, modo = boe(n)
            open(path, "w").write(f"# {t} · {bid} · {modo} · descargado {datetime.date.today()}\n\n{txt}\n")
            rows.append(f"| {n['titulo']} | ✅ {bid} · {modo} ({len(txt) // 1000} mil caracteres) |")
        except Exception as e:
            have = os.path.exists(path)
            rows.append(f"| {n['titulo']} | {'⚠️ se mantiene la versión anterior' if have else '❌'} · {str(e)[:220]} |")
    open(os.path.join(DIR, "estado.md"), "w").write("\n".join(rows) + "\n")
    print("\n".join(rows))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main("--todas" in sys.argv)
