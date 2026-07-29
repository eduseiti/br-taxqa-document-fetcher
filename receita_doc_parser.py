#!/usr/bin/env python3
"""
Legacy Word 97 (``.doc``, OLE) annex parser — text **and tables**.

Why this exists: three Receita annexes are Word-97 binaries, and they are pure
table content (`IN SRF nº 84/2001`'s "Anexo Único.doc" is the monthly
cost-restatement index table). No in-process converter for OLE Word is available
in this environment — no LibreOffice, ``antiword``, ``pandoc`` or ``mammoth`` —
so those annexes previously degraded to the portal's flattened ``textoIntegra``:
every number in one unbroken run of characters, exactly the defect this whole
work set out to remove.

LibreOffice remains the preferred converter when it is installed (see
``receita_attachments.doc_to_fragment``); this module is the fallback that makes
the pipeline self-contained, needing only ``olefile``.

How Word 97 stores tables
-------------------------
The format is documented in [MS-DOC]. Two facts are all that is needed:

* The character stream lives in the ``WordDocument`` stream. Its layout is given
  by the **piece table** (``CLX`` → ``PlcPcd``), which maps character positions
  to byte offsets and records, per piece, whether text is 1-byte cp1252
  ("compressed") or 2-byte UTF-16LE. Reading ``fcMin..fcMac`` directly happens to
  work for these three files but is wrong in general, so the piece table is
  honored.
* Paragraph terminators carry the structure:
  ``\\r`` ends a paragraph, and **``\\x07`` ends a table cell**. A row is
  terminated by an *additional* ``\\x07`` paragraph that is empty. Rows
  accumulate into a table until a ``\\r`` paragraph at a row boundary closes it.

Distinguishing a row *end* from an empty *cell* is the only real difficulty:
[MS-DOC] marks row ends with the paragraph property ``sprmPFTtp``, which would
require decoding ``PlcfBtePapx``/``PAPX`` grpprl. Instead this module exploits
the fact that the unit sequence is **periodic** — ``N`` cells then one empty
row-end unit — and recovers ``N`` by finding the smallest period that puts an
empty unit at every row-end position (``_rows_from_units``). Reading "any empty
unit ends the row" instead is wrong on blank forms: ``IN SRF nº 208``'s Anexo II
is a fill-in table whose data cells are all empty, and it collapsed into 55
one-cell rows. Period detection recovers it as 28×3.

Every table is additionally checked for a consistent column count, and a table
that no period fits is reported as ragged rather than silently mangled. On this
corpus all 32 tables across the 3 files come out rectangular.
"""

import logging
import re
import struct
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# FIB (File Information Block) offsets in the WordDocument stream, per [MS-DOC].
_FIB_FLAGS = 0x000A          # bit 0x0200 = fWhichTblStm (1Table vs 0Table)
_FIB_FCMIN = 0x0018
_FIB_CCPTEXT = 0x004C
_FIB_FCCLX = 0x01A2          # fcClx (4 bytes) + lcbClx (4 bytes)

# Special characters in the Word character stream.
_CELL_END = "\x07"           # end of a table cell; an empty one ends the row
_PARA_END = "\r"
_FIELD_BEGIN, _FIELD_SEP, _FIELD_END = "\x13", "\x14", "\x15"

# Control characters that carry no text: embedded object / footnote / annotation
# placeholders, and the "optional hyphen" which must vanish rather than print.
_DROP = dict.fromkeys(map(ord, "\x00\x01\x02\x03\x04\x05\x08\x1f"), None)
_TRANSLATE = {
    ord("\x0b"): "\n",       # line break inside a paragraph
    ord("\x0c"): "\n",       # page break
    ord("\x1e"): "-",        # non-breaking hyphen
    ord("\xa0"): " ",        # non-breaking space
    ord("\x0e"): None,       # column break
    **_DROP,
}


class DocParseError(Exception):
    """The stream is not a Word 97 binary document we can read."""


# --------------------------------------------------------------------------- #
# Text extraction (piece table aware)
# --------------------------------------------------------------------------- #
def extract_text(data: bytes) -> str:
    """Return the full character stream of a Word 97 ``.doc``.

    Honors the ``CLX``/``PlcPcd`` piece table, so both cp1252-"compressed" and
    UTF-16LE pieces decode correctly and pieces are concatenated in character
    order (which is not byte order in a fast-saved document).
    """
    try:
        import olefile
    except ImportError as e:  # pragma: no cover - environment guard
        raise DocParseError(f"olefile not installed: {e}")

    import io

    if not olefile.isOleFile(io.BytesIO(data)):
        raise DocParseError("not an OLE compound file")

    # olefile raises assorted low-level errors (ValueError, IOError, struct
    # errors) on a truncated or malformed container. They are all "this is not a
    # readable .doc", so they are normalized here rather than escaping into the
    # fetch pipeline.
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception as e:
        raise DocParseError(f"unreadable OLE container: {e}")

    try:
        wd = ole.openstream("WordDocument").read()
        if len(wd) < _FIB_FCCLX + 8:
            raise DocParseError("WordDocument stream too short for a FIB")

        w_ident = struct.unpack_from("<H", wd, 0)[0]
        if w_ident != 0xA5EC:
            raise DocParseError(f"unexpected wIdent {w_ident:#x} (not Word 97+)")

        flags = struct.unpack_from("<H", wd, _FIB_FLAGS)[0]
        table_name = "1Table" if (flags & 0x0200) else "0Table"
        if not ole.exists(table_name):
            raise DocParseError(f"missing {table_name} stream")
        table = ole.openstream(table_name).read()

        fc_clx, lcb_clx = struct.unpack_from("<ll", wd, _FIB_FCCLX)
        pieces = _piece_table(table, fc_clx, lcb_clx)
        if not pieces:
            # No usable piece table: fall back to the contiguous fcMin..fcMac
            # range, assuming cp1252 (correct for a non-fast-saved ANSI doc).
            fc_min = struct.unpack_from("<l", wd, _FIB_FCMIN)[0]
            ccp_text = struct.unpack_from("<l", wd, _FIB_CCPTEXT)[0]
            return wd[fc_min:fc_min + ccp_text].decode("cp1252", "replace")

        out: List[str] = []
        for fc, n_chars, compressed in pieces:
            if compressed:
                out.append(wd[fc:fc + n_chars].decode("cp1252", "replace"))
            else:
                out.append(wd[fc:fc + n_chars * 2].decode("utf-16-le", "replace"))
        return "".join(out)
    except DocParseError:
        raise
    except Exception as e:
        raise DocParseError(f"malformed Word structures: {e}")
    finally:
        ole.close()


def _piece_table(table: bytes, fc_clx: int, lcb_clx: int
                 ) -> List[Tuple[int, int, bool]]:
    """Parse ``CLX`` → list of ``(byte_offset, n_chars, is_cp1252)`` pieces.

    ``CLX`` is a sequence of ``Prc`` blocks (tag 0x01, skipped) followed by a
    ``Pcdt`` (tag 0x02) holding a ``PlcPcd``: ``n+1`` character positions
    followed by ``n`` 8-byte ``Pcd`` structures. In each ``Pcd`` the 32-bit
    ``fc`` uses bit 30 as "text is cp1252", in which case the real byte offset is
    ``fc/2``.
    """
    if lcb_clx <= 0 or fc_clx < 0 or fc_clx + lcb_clx > len(table):
        return []

    clx = table[fc_clx:fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx):
        tag = clx[pos]
        if tag == 0x01:                      # Prc: 2-byte cbGrpprl, then data
            if pos + 3 > len(clx):
                return []
            cb = struct.unpack_from("<h", clx, pos + 1)[0]
            pos += 3 + cb
        elif tag == 0x02:                    # Pcdt: 4-byte lcb, then PlcPcd
            if pos + 5 > len(clx):
                return []
            lcb = struct.unpack_from("<L", clx, pos + 1)[0]
            plc = clx[pos + 5:pos + 5 + lcb]
            return _parse_plcpcd(plc)
        else:
            return []
    return []


def _parse_plcpcd(plc: bytes) -> List[Tuple[int, int, bool]]:
    """Decode a ``PlcPcd``: ``(n+1)`` CPs of 4 bytes, then ``n`` Pcds of 8."""
    # 4*(n+1) + 8*n == len(plc)  =>  n = (len(plc) - 4) / 12
    if len(plc) < 16 or (len(plc) - 4) % 12 != 0:
        return []
    n = (len(plc) - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}l", plc, 0)
    pieces: List[Tuple[int, int, bool]] = []
    base = 4 * (n + 1)
    for i in range(n):
        fc_raw = struct.unpack_from("<L", plc, base + i * 8 + 2)[0]
        compressed = bool(fc_raw & 0x40000000)
        fc = fc_raw & 0x3FFFFFFF
        if compressed:
            fc //= 2
        n_chars = cps[i + 1] - cps[i]
        if n_chars > 0:
            pieces.append((fc, n_chars, compressed))
    return pieces


# --------------------------------------------------------------------------- #
# Structure: paragraphs and tables
# --------------------------------------------------------------------------- #
def _strip_fields(text: str) -> str:
    """Drop Word field *instructions*, keeping the field *result*.

    A field is ``\\x13 instruction [\\x14 result] \\x15``. Only the result is
    what a reader sees, so the instruction (e.g. ``PAGE``, ``HYPERLINK "…"``) is
    discarded.
    """
    out: List[str] = []
    depth = 0
    in_instruction = False
    for ch in text:
        if ch == _FIELD_BEGIN:
            depth += 1
            in_instruction = True
        elif ch == _FIELD_SEP and depth:
            in_instruction = False
        elif ch == _FIELD_END and depth:
            depth -= 1
            in_instruction = False
        elif not (depth and in_instruction):
            out.append(ch)
    return "".join(out)


def _clean(text: str) -> str:
    """Normalize a unit of text: translate specials, collapse whitespace."""
    text = text.translate(_TRANSLATE)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _rows_from_units(units: List[str]) -> Tuple[List[List[str]], bool]:
    """Group a table block's cell-terminated units into rows.

    Each row is ``N`` cell units followed by one **empty** row-end unit, so the
    unit sequence is periodic with period ``N+1``. Recovering ``N`` by period
    detection — the smallest ``N`` for which every row-end position is empty —
    is what makes genuinely empty *cells* distinguishable from row *ends*.

    The naive reading ("an empty unit ends the row") fails exactly on blank
    forms: ``IN SRF nº 208``'s Anexo II is a fill-in table whose data cells are
    all empty, and it collapsed into 55 one-cell rows.

    Returns ``(rows, exact)``; ``exact`` is False when no period fits, in which
    case the naive split is used and the caller reports the table as ragged.
    """
    n_units = len(units)
    if n_units == 0:
        return [], True

    for width in range(1, n_units):
        period = width + 1
        if n_units % period:
            continue
        if all(units[i + width] == "" for i in range(0, n_units, period)):
            return [units[i:i + width] for i in range(0, n_units, period)], True

    # No consistent period: fall back to "empty unit ends the row".
    rows: List[List[str]] = []
    cells: List[str] = []
    for unit in units:
        if unit == "" and cells:
            rows.append(cells)
            cells = []
        else:
            cells.append(unit)
    if cells:
        rows.append(cells)
    return rows, False


def parse_blocks(text: str) -> List[Tuple[str, object]]:
    """Split the character stream into ``("para", str)`` / ``("table", rows)``.

    Cell-terminated units accumulate into a table block; a normal ``\\r``
    paragraph closes it. A paragraph appearing while a block is open is treated
    as a continuation of the current cell (a multi-paragraph cell), not as the
    end of the table. Row grouping is delegated to ``_rows_from_units``.
    """
    text = _strip_fields(text)

    blocks: List[Tuple[str, object]] = []
    units: List[str] = []
    buf: List[str] = []

    def flush_table() -> None:
        if units:
            rows, exact = _rows_from_units(units)
            if rows:
                blocks.append(("table", rows) if exact else ("table_ragged", rows))
            units.clear()

    for ch in text:
        if ch == _CELL_END:
            units.append(_clean("".join(buf)))
            buf.clear()
        elif ch == _PARA_END:
            unit = _clean("".join(buf))
            buf.clear()
            # Only a paragraph arriving *mid-row* belongs to a cell. At a row
            # boundary (last unit is the empty row-end mark) the paragraph is
            # real prose and closes the table — several annexes are a stack of
            # small tables separated by heading paragraphs.
            if units and units[-1] != "":
                if unit:
                    units[-1] = (units[-1] + "\n" + unit).strip()
            else:
                flush_table()
                if unit:
                    blocks.append(("para", unit))
        else:
            buf.append(ch)

    flush_table()
    tail = _clean("".join(buf))
    if tail:
        blocks.append(("para", tail))
    return blocks


def rectangularity(rows: List[List[str]]) -> Tuple[int, bool]:
    """Return ``(column_count, is_rectangular)`` for a parsed table.

    Used as the validation signal for the row-end heuristic: a table whose rows
    disagree on width is reported so it can be reviewed, rather than silently
    emitted as a mangled grid.
    """
    if not rows:
        return 0, False
    widths = {len(r) for r in rows}
    return max(widths), len(widths) == 1


# --------------------------------------------------------------------------- #
# HTML rendering
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def doc_to_html(data: bytes) -> Tuple[str, int, Optional[str]]:
    """Convert Word 97 bytes to an HTML fragment.

    Returns ``(html, n_tables, error)``. Tables become real ``<table>`` elements
    (so ``WordDocumentBuilder._add_table`` produces real Word tables) and prose
    becomes ``<p>``, both in document order.
    """
    try:
        text = extract_text(data)
    except DocParseError as e:
        return "", 0, f"legacy .doc parse failed: {e}"

    parts: List[str] = []
    n_tables = 0
    ragged = 0
    for kind, payload in parse_blocks(text):
        if kind == "para":
            parts.append(f"<p>{_esc(payload)}</p>")
            continue
        rows: List[List[str]] = payload  # type: ignore[assignment]
        width, rect = rectangularity(rows)
        if kind == "table_ragged" or not rect:
            ragged += 1
        out = ["<table>"]
        for row in rows:
            padded = row + [""] * (width - len(row))
            out.append("<tr>" + "".join(
                f"<td>{_esc(c)}</td>" for c in padded) + "</tr>")
        out.append("</table>")
        parts.append("".join(out))
        n_tables += 1

    if not parts:
        return "", 0, "legacy .doc contained no extractable content"
    error = f"{ragged} table(s) with inconsistent column counts" if ragged else None
    return "\n".join(parts), n_tables, error


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            html, n, err = doc_to_html(f.read())
        print(f"\n=== {path}: {n} table(s), error={err}")
        for kind, payload in parse_blocks(extract_text(open(path, "rb").read())):
            if kind == "para":
                print(f"  P: {payload[:90]}")
            else:
                w, ok = rectangularity(payload)
                flag = " RAGGED" if kind == "table_ragged" else ""
                print(f"  T: {len(payload)} rows x {w} cols rectangular={ok}{flag}")
                for row in payload[:3]:
                    print(f"       {row}")
