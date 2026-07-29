#!/usr/bin/env python3
"""
Receita Federal act attachments: retrieval + conversion to renderable HTML.

An *anexo* segment (``idTipoSegmento == 16``) of a sijut2consulta act may carry
an ``arquivoBinario``. The portal's own Angular component renders the
**attachment** and suppresses the segment's ``textoIntegra`` entirely::

    ngIf = (segmento.idTipoSegmento !== 16 || !segmento.arquivoBinario) && !segmento.omitir   // text
    ngIf = segmento.arquivoBinario && !visaoSelecionada.isAnotacao() && !segmento.omitir      // attachment

That ``textoIntegra`` is a degraded, whitespace-flattened rendition of the
attached table ("ANO DE % DE ANO DE % DE AQUISIÇÃO REDUÇÃO … Até 1969 100% …"),
which is what the pipeline used to save. This module recovers the real thing.

Two retrieval channels
----------------------
* **Inline** — ``arquivoBinario.arquivoBinario`` is a base64 blob. True for the
  ``.htm``/``.html``/``.jpg`` attachments (35 of 307 in the corpus).
* **By reference** — ``arquivoBinario`` is ``null`` and only the id is given.
  Those must be pulled from an endpoint that is not in any public documentation
  and was found by probing (every sibling path — ``/arquivo-binario/``,
  ``/arquivo/``, ``/segmento/{id}/arquivo`` — returns 403)::

      GET {API_HOST}/api/consulta-externa/ato/{idAto}/anexo/{idArquivoBinario}
          Referer/Origin: same-site (else the WAF answers 403)
      -> 200 application/octet-stream

  This is the majority channel: **268 PDFs, 3 .doc and 1 .ods across 143 acts**,
  and 156 of those segments carry an *empty* ``textoIntegra`` — i.e. before this
  module those annexes were missing from the corpus outright, not merely
  unformatted.

Conversion (by ``idTipoArquivo``)
---------------------------------
==== ======== ==================================================================
code kind     strategy
==== ======== ==================================================================
4/5  htm/html bs4; emit each ``<table>`` verbatim, keep non-table prose as ``<p>``
6    pdf      PyMuPDF ``find_tables()``; text outside table bboxes as ``<p>``;
              a page yielding neither is rasterized to PNG so nothing vanishes
17   ods      stdlib ``zipfile`` + ``content.xml`` (honors ``number-columns-repeated``)
7    doc      legacy Word 97 OLE — LibreOffice if present, else the built-in
              ``receita_doc_parser`` (piece table + cell/row marks)
2    jpg      inlined as a ``data:`` URI
==== ======== ==================================================================

The raw bytes are **always** persisted under ``documents/attachments/`` before
conversion is attempted, so a conversion failure degrades to "unformatted" and
never to "lost".
"""

import base64
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

API_HOST = "https://normasinternet2.receita.fazenda.gov.br"
API_ANEXO = API_HOST + "/api/consulta-externa/ato/{id_ato}/anexo/{id_arquivo}"

# idTipoArquivo -> short kind label used in reports and converter dispatch.
FILE_KINDS: Dict[int, str] = {
    2: "jpg",
    4: "html",
    5: "html",
    6: "pdf",
    7: "doc",
    17: "ods",
}

# ODS/OpenDocument table namespace.
_ODS_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_ODS_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"

# A repeated-column/row count this large means "to the end of the sheet"; ODS
# writers use 1024/1048576 as padding. Never materialize those.
_ODS_REPEAT_CAP = 64


@dataclass
class AttachmentResult:
    """Outcome of retrieving + converting one attachment."""
    id_arquivo: Optional[int]
    id_tipo: Optional[int]
    kind: str                       # "pdf", "html", ...
    name: str
    size: int = 0
    saved_as: Optional[str] = None  # path under documents/attachments/
    html: str = ""                  # converted fragment ("" = conversion failed)
    n_tables: int = 0
    converted: bool = False
    source: str = ""                # "inline" | "endpoint" | "cache"
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
class AttachmentClient:
    """Fetches act attachments, with a disk cache and polite pacing.

    The cache is keyed on ``{idAto}_{idArquivoBinario}`` and lives outside the
    per-type output tree, so a re-run does not re-download 268 PDFs.
    """

    def __init__(self, session, cache_dir: str = "./.attachment_cache",
                 delay: float = 0.5, timeout: int = 60):
        self.session = session
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.timeout = timeout
        self._last_request = 0.0

    def _pace(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def fetch(self, id_ato, id_arquivo) -> Tuple[Optional[bytes], str]:
        """Return ``(bytes, source)`` for a by-reference attachment.

        ``source`` is "cache" or "endpoint"; ``(None, "error")`` on failure.
        """
        cached = self.cache_dir / f"{id_ato}_{id_arquivo}.bin"
        if cached.exists():
            return cached.read_bytes(), "cache"

        url = API_ANEXO.format(id_ato=id_ato, id_arquivo=id_arquivo)
        self._pace()
        try:
            resp = self.session.get(
                url, timeout=self.timeout,
                headers={"Referer": API_HOST + "/", "Origin": API_HOST},
            )
        except Exception as e:  # requests.RequestException and friends
            logger.warning(f"anexo {id_ato}/{id_arquivo}: request error {e}")
            return None, "error"
        if resp.status_code != 200 or not resp.content:
            logger.warning(f"anexo {id_ato}/{id_arquivo}: HTTP {resp.status_code}")
            return None, "error"
        cached.write_bytes(resp.content)
        return resp.content, "endpoint"


def _safe_name(name: str) -> str:
    """Filesystem-safe version of the portal's original attachment filename."""
    cleaned = re.sub(r"[^\w.\-]+", "_", (name or "anexo").strip())
    return cleaned[:80] or "anexo"


def retrieve(binario: dict, id_ato, client: Optional[AttachmentClient],
             attachments_dir: Optional[Path], stem: str) -> AttachmentResult:
    """Get one attachment's bytes (inline or by reference) and persist them.

    Persisting happens **before** conversion so a converter failure still leaves
    the original in ``documents/attachments/``.
    """
    id_arq = binario.get("idArquivoBinario")
    id_tipo = binario.get("idTipoArquivo")
    name = binario.get("nomeArquivoBinario") or f"anexo_{id_arq}"
    result = AttachmentResult(
        id_arquivo=id_arq, id_tipo=id_tipo,
        kind=FILE_KINDS.get(id_tipo, f"tipo{id_tipo}"), name=name,
    )

    inline = binario.get("arquivoBinario")
    if inline:
        try:
            raw = base64.b64decode(inline)
            result.source = "inline"
        except Exception as e:
            result.error = f"base64 decode failed: {e}"
            return result
    elif client is not None:
        raw, source = client.fetch(id_ato, id_arq)
        result.source = source
        if raw is None:
            result.error = "download failed"
            return result
    else:
        result.error = "no client for by-reference attachment"
        return result

    result.size = len(raw)
    if attachments_dir is not None:
        attachments_dir.mkdir(parents=True, exist_ok=True)
        path = attachments_dir / f"{stem}__{id_arq}_{_safe_name(name)}"
        path.write_bytes(raw)
        result.saved_as = path.name

    html, n_tables, error = convert(raw, id_tipo, name)
    result.html = html
    result.n_tables = n_tables
    result.converted = bool(html)
    if error:
        result.error = error
    return result


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #
def convert(raw: bytes, id_tipo: Optional[int], name: str = "") -> Tuple[str, int, Optional[str]]:
    """Convert attachment bytes to an HTML fragment.

    Returns ``(html, n_tables, error)``. An empty ``html`` means the caller
    should fall back to the segment's flattened ``textoIntegra``.
    """
    kind = FILE_KINDS.get(id_tipo)
    try:
        if kind == "html":
            return html_to_fragment(raw)
        if kind == "pdf":
            return pdf_to_fragment(raw)
        if kind == "ods":
            return ods_to_fragment(raw)
        if kind == "jpg":
            return image_to_fragment(raw, "image/jpeg"), 0, None
        if kind == "doc":
            return doc_to_fragment(raw, name)
    except Exception as e:  # a bad attachment must never abort an act
        logger.warning(f"attachment {name!r} (tipo={id_tipo}): conversion failed: {e}")
        return "", 0, f"conversion failed: {e}"
    return "", 0, f"no converter for idTipoArquivo={id_tipo}"


def _decode(raw: bytes) -> str:
    """Decode attachment HTML, honoring a charset meta; Word exports vary."""
    head = raw[:2048].decode("ascii", "replace").lower()
    m = re.search(r'charset=["\']?([\w-]+)', head)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "cp1252", "latin-1"]:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def html_to_fragment(raw: bytes) -> Tuple[str, int, Optional[str]]:
    """Extract tables + prose from an attached HTML file (usually a Word export).

    Word's HTML export is full of ``mso-`` styling, ``<o:p>`` placeholders and
    conditional comments; only the block structure is kept. Tables are emitted
    verbatim (attributes intact, so ``_add_table`` sees rowspan/colspan) and any
    prose *outside* a table becomes a paragraph.
    """
    soup = BeautifulSoup(_decode(raw), "html.parser")
    for junk in soup.find_all(["script", "style", "meta", "link"]):
        junk.decompose()

    parts: List[str] = []
    n_tables = 0
    body = soup.body or soup
    for element in body.find_all(["table", "p", "h1", "h2", "h3", "div"], recursive=True):
        # Skip anything nested inside a table — the table emits it already.
        if element.find_parent("table") is not None:
            continue
        if element.name == "table":
            parts.append(str(element))
            n_tables += 1
        elif element.name == "div":
            # Only emit a div when it holds no block children of its own,
            # otherwise its children are visited separately (avoids duplicates).
            if element.find(["table", "p", "h1", "h2", "h3", "div"]):
                continue
            text = element.get_text(" ", strip=True)
            if text:
                parts.append(f"<p>{text}</p>")
        else:
            text = element.get_text(" ", strip=True)
            if text:
                tag = element.name if element.name.startswith("h") else "p"
                parts.append(f"<{tag}>{text}</{tag}>")
    return "\n".join(parts), n_tables, None


def pdf_to_fragment(raw: bytes) -> Tuple[str, int, Optional[str]]:
    """Extract tables and text from a PDF annex, preserving reading order.

    Table detection is PyMuPDF's ``find_tables()`` — reliable on the ruled tables
    this corpus uses. Text blocks whose bbox falls inside a detected table are
    dropped (the table already carries them); the rest become paragraphs, and
    blocks and tables are interleaved by vertical position so a caption above a
    table stays above it. A page that yields neither table nor text is a scanned
    image, and is rasterized so its content is not silently lost.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", 0, "PyMuPDF not installed"

    parts: List[str] = []
    n_tables = 0
    with fitz.open(stream=raw, filetype="pdf") as doc:
        for page in doc:
            try:
                tables = page.find_tables().tables
            except Exception as e:
                logger.debug(f"find_tables failed on a page: {e}")
                tables = []

            # (y_top, kind, payload) so tables and prose interleave correctly.
            items: List[Tuple[float, str, str]] = []
            boxes = []
            for t in tables:
                rows = t.extract()
                if not rows or not any(any(c for c in r) for r in rows):
                    continue
                boxes.append(t.bbox)
                items.append((t.bbox[1], "table", _rows_to_table_html(rows)))
                n_tables += 1

            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
                text = " ".join((text or "").split())
                if not text:
                    continue
                # Drop blocks that sit inside a table's bbox.
                cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
                if any(bx0 <= cx <= bx1 and by0 <= cy <= by1
                       for bx0, by0, bx1, by1 in boxes):
                    continue
                items.append((y0, "text", f"<p>{_esc(text)}</p>"))

            if not items:
                # Scanned page: keep it as an image rather than losing it.
                try:
                    pix = page.get_pixmap(dpi=110)
                    parts.append(image_to_fragment(pix.tobytes("png"), "image/png"))
                except Exception as e:
                    logger.warning(f"Could not rasterize empty PDF page: {e}")
                continue

            items.sort(key=lambda it: it[0])
            parts.extend(payload for _, _, payload in items)

    return "\n".join(parts), n_tables, None


def ods_to_fragment(raw: bytes) -> Tuple[str, int, Optional[str]]:
    """Convert an OpenDocument spreadsheet to HTML tables (stdlib only).

    ``number-columns-repeated`` / ``number-rows-repeated`` are how ODS encodes
    runs of identical cells, including the huge trailing padding every writer
    emits; they are expanded, but capped so a 1024-wide padding run does not
    become 1024 empty columns.
    """
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        content = zf.read("content.xml")
    root = ET.fromstring(content)

    def cell_text(cell) -> str:
        return " ".join(
            "".join(p.itertext()).strip()
            for p in cell.findall(f"{{{_ODS_TEXT_NS}}}p")
        ).strip()

    parts: List[str] = []
    n_tables = 0
    for table in root.iter(f"{{{_ODS_TABLE_NS}}}table"):
        rows: List[List[str]] = []
        for row in table.findall(f"{{{_ODS_TABLE_NS}}}table-row"):
            cells: List[str] = []
            for cell in row.findall(f"{{{_ODS_TABLE_NS}}}table-cell"):
                repeat = min(int(cell.get(f"{{{_ODS_TABLE_NS}}}number-columns-repeated", 1)),
                             _ODS_REPEAT_CAP)
                cells.extend([cell_text(cell)] * repeat)
            while cells and not cells[-1]:
                cells.pop()
            row_repeat = min(int(row.get(f"{{{_ODS_TABLE_NS}}}number-rows-repeated", 1)),
                             _ODS_REPEAT_CAP)
            if cells:
                rows.extend([list(cells)] * row_repeat)
        while rows and not any(rows[-1]):
            rows.pop()
        if rows:
            parts.append(_rows_to_table_html(rows))
            n_tables += 1
    return "\n".join(parts), n_tables, None


def doc_to_fragment(raw: bytes, name: str = "") -> Tuple[str, int, Optional[str]]:
    """Convert a legacy ``.doc`` (Word 97 OLE) annex to tables + prose.

    Two paths, in order of fidelity:

    1. **LibreOffice**, when installed — the reference implementation, and it
       handles merged cells and nested tables that the fallback approximates.
    2. **``receita_doc_parser``** — a self-contained Word-97 reader (needs only
       ``olefile``). This is what actually runs here, and it matters: these
       annexes are *pure table content* (``IN SRF nº 84/2001``'s "Anexo Único.doc"
       is 14 cost-restatement index tables), so treating them as unconvertible
       meant falling back to the portal's flattened text — every number in one
       unbroken run — which is precisely the defect this work exists to remove.
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / (_safe_name(name) or "anexo.doc")
            if src.suffix.lower() != ".doc":
                src = src.with_suffix(".doc")
            src.write_bytes(raw)
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "html",
                     "--outdir", tmp, str(src)],
                    check=True, capture_output=True, timeout=180,
                )
                produced = list(Path(tmp).glob("*.html"))
                if produced:
                    return html_to_fragment(produced[0].read_bytes())
                logger.warning("LibreOffice produced no output for %r; "
                               "falling back to the built-in parser", name)
            except Exception as e:
                logger.warning("LibreOffice failed on %r (%s); "
                               "falling back to the built-in parser", name, e)

    import receita_doc_parser
    return receita_doc_parser.doc_to_html(raw)


def image_to_fragment(raw: bytes, mime: str) -> str:
    """Inline raw image bytes as a ``data:`` URI (what ``_add_image`` supports)."""
    b64 = base64.b64encode(raw).decode("ascii")
    return f'<p><img src="data:{mime};base64,{b64}"></p>'


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _rows_to_table_html(rows: List[List[Optional[str]]]) -> str:
    """Build a plain ``<table>`` from a row-major matrix of cell strings."""
    width = max((len(r) for r in rows), default=0)
    out = ["<table>"]
    for i, row in enumerate(rows):
        cells = list(row) + [""] * (width - len(row))
        tag = "th" if i == 0 else "td"
        out.append("<tr>" + "".join(
            f"<{tag}>{_esc(' '.join((c or '').split()))}</{tag}>" for c in cells
        ) + "</tr>")
    out.append("</table>")
    return "".join(out)
