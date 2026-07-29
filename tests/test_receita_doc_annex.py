#!/usr/bin/env python3
"""
Offline tests for the legacy Word 97 (``.doc``) annex parser.

These pin the bugfix for the last unconverted annex class. Three Receita annexes
are Word-97 binaries containing **nothing but tables**; treating them as
unconvertible meant the pipeline fell back to the portal's flattened
``textoIntegra`` — every number of a 14-table index in one unbroken run of
characters — which is the exact defect the rendering-fidelity work set out to
remove.

Fixtures (real files from the corpus):

  * ``receita_anexo_word97.doc``      — ``IN SRF nº 84/2001`` "Anexo Único.doc":
      14 cost-restatement index tables, monthly rows × year columns
  * ``receita_anexo_word97_form.doc`` — ``IN SRF nº 208/2002`` "ANEXO II.doc":
      a blank fill-in **form**, i.e. a table whose data cells are all empty —
      the case that defeats naive row-end detection

Run:
    python -m pytest tests/test_receita_doc_annex.py -v
"""

import os
import sys

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "br_legal_parser")))

import receita_attachments  # noqa: E402
import receita_doc_parser  # noqa: E402
from receita_norma_fetcher import ReceitaNormaFetcher  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
INDEX_DOC = os.path.join(FIXTURES, "receita_anexo_word97.doc")
FORM_DOC = os.path.join(FIXTURES, "receita_anexo_word97_form.doc")


def _raw(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _tables(html: str):
    return BeautifulSoup(html, "html.parser").find_all("table")


def _rows(table):
    return [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            for tr in table.find_all("tr")]


# --------------------------------------------------------------------------- #
# Text extraction via the piece table
# --------------------------------------------------------------------------- #
def test_extract_text_reads_the_whole_character_stream():
    text = receita_doc_parser.extract_text(_raw(INDEX_DOC))
    assert len(text) == 7819                       # == the FIB's ccpText
    assert "Índices para valores expressos em Reais" in text
    assert "\x07" in text                          # cell marks are preserved


def test_extract_text_rejects_non_ole_input():
    with pytest.raises(receita_doc_parser.DocParseError):
        receita_doc_parser.extract_text(b"%PDF-1.4 not a word document")


def test_extract_text_rejects_ole_that_is_not_word():
    # A valid OLE container without a WordDocument stream must not be mistaken
    # for a .doc (the .ods annex is a ZIP, but other OLE formats exist).
    import olefile  # noqa: F401  (ensures the dependency is present)
    with pytest.raises(receita_doc_parser.DocParseError):
        receita_doc_parser.extract_text(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)


# --------------------------------------------------------------------------- #
# Row grouping: period detection vs the naive "empty unit ends the row"
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("units,expected", [
    # 3 columns: N cells then an empty row-end unit.
    (["", "1995", "1994", "", "JAN", "0,8166", "-", ""],
     [["", "1995", "1994"], ["JAN", "0,8166", "-"]]),
    # A blank form: every data cell empty. The naive rule collapses this into
    # one-cell rows; period detection keeps it 3-wide.
    (["BENEFICIÁRIO", "CPF", "RENDIMENTOS", "", "", "", "", ""],
     [["BENEFICIÁRIO", "CPF", "RENDIMENTOS"], ["", "", ""]]),
    # A trailing empty cell must not be mistaken for the row end.
    (["a", "b", "", "", "c", "d", "", ""],
     [["a", "b", ""], ["c", "d", ""]]),
])
def test_rows_from_units_recovers_the_period(units, expected):
    rows, exact = receita_doc_parser._rows_from_units(units)
    assert exact is True
    assert rows == expected


def test_rows_from_units_accepts_a_single_wide_row():
    # 4 cells + one row-end unit is a legitimate 1-row, 4-column table, even
    # though two of its cells are empty.
    rows, exact = receita_doc_parser._rows_from_units(["a", "b", "", "c", ""])
    assert exact is True
    assert rows == [["a", "b", "", "c"]]


def test_rows_from_units_reports_when_no_period_fits():
    # No width puts an empty unit at every row-end position, so the block is
    # genuinely irregular and must be reported rather than guessed at.
    rows, exact = receita_doc_parser._rows_from_units(["a", "b", "", "c", "d"])
    assert exact is False          # ragged -> caller flags it
    assert rows == [["a", "b"], ["c", "d"]]


# --------------------------------------------------------------------------- #
# The reference defect: IN SRF nº 84's Anexo Único
# --------------------------------------------------------------------------- #
def test_index_annex_yields_fourteen_rectangular_tables():
    html, n_tables, error = receita_doc_parser.doc_to_html(_raw(INDEX_DOC))
    assert error is None
    assert n_tables == 14
    tables = _tables(html)
    assert len(tables) == 14
    for table in tables:
        rows = _rows(table)
        assert len(rows) == 13                              # 1 header + 12 months
        assert len({len(r) for r in rows}) == 1              # rectangular

    first = _rows(tables[0])
    assert first[0] == ["", "1995", "1994"]
    assert first[1] == ["JAN", "0,8166", "-"]
    assert first[12] == ["DEZ", "0,9596", "0,7986"]


def test_index_annex_preserves_every_value_from_the_flattened_text():
    """Nothing the portal's own flattened rendition contains may be lost.

    The flattened ``textoIntegra`` is the degraded fallback we are replacing, so
    it doubles as an independent inventory of what the tables must contain.
    """
    html, _, _ = receita_doc_parser.doc_to_html(_raw(INDEX_DOC))
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    # Values sampled across the different column layouts (3, 4, 5, 6 and 8 wide).
    for value in ("0,8166", "226,5838", "8944,793", "720,4779", "151,5152",
                  "33,2962", "165,7657", "JAN", "DEZ", "1990", "1993",
                  "Índices para valores expressos em Cruzeiros Reais"):
        assert value in text, value


def test_index_annex_becomes_real_word_tables_end_to_end():
    """Through the whole segment -> fragment -> docx path, not just the parser."""
    from legal_document_fetcher import WordDocumentBuilder

    data = {
        "_view": "vigente",
        "epigrafeCompleta": "Instrução Normativa SRF nº 84, de 11 de outubro de 2001",
        "ementas": [],
        "outrosSegmentos": [{
            "ordemSegmentoAto": 1, "idTipoSegmento": 16,
            # The flattened fallback the portal ships for this annex.
            "textoIntegra": "Tabela de Atualização 1995 1994 JAN 0,8166 - FEV 0,8166 -",
            "arquivoBinario": {
                "idArquivoBinario": 19357, "idTipoArquivo": 7,
                "nomeArquivoBinario": "Anexo Único.doc",
                "arquivoBinario": _b64(INDEX_DOC),
            },
        }],
    }
    stats: dict = {}
    fragment = ReceitaNormaFetcher._segments_html(data, stats=stats)

    assert stats["attachment_tables"] == 14
    assert stats["attachments_failed"] == 0

    doc = WordDocumentBuilder().create_document(
        BeautifulSoup(fragment, "html.parser"), "Legal Document")
    assert len(doc.tables) == 14
    assert doc.tables[0].rows[1].cells[0].text.strip() == "JAN"
    assert doc.tables[0].rows[1].cells[1].text.strip() == "0,8166"

    # The flattened duplicate must be gone, and the .txt must show table rows.
    text = ReceitaNormaFetcher.fragment_to_text(fragment)
    assert "Tabela de Atualização 1995 1994 JAN" not in text
    assert "JAN | 0,8166 | -" in text


def _b64(path: str) -> str:
    import base64
    return base64.b64encode(_raw(path)).decode("ascii")


# --------------------------------------------------------------------------- #
# The blank-form annex: empty cells must not collapse the grid
# --------------------------------------------------------------------------- #
def test_blank_form_annex_keeps_its_column_structure():
    html, n_tables, error = receita_doc_parser.doc_to_html(_raw(FORM_DOC))
    assert error is None                    # no ragged tables
    tables = _tables(html)
    assert n_tables == len(tables) == 4

    # The beneficiary table is the form's body: a 3-column grid of blank rows.
    body = max((_rows(t) for t in tables), key=len)
    assert body[0] == ["BENEFICIÁRIO", "CPF", "RENDIMENTOS"]
    assert len(body) == 28
    assert all(len(r) == 3 for r in body)
    assert all(cell == "" for cell in body[1])   # blank fill-in row

    # Headings between the sub-tables stay prose, not swallowed into cells.
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    assert "RELAÇÃO DE SERVIDORES DE ORGANISMO INTERNACIONAL" in text
    assert "2. BENEFICIÁRIO DOS RENDIMENTOS" in text


# --------------------------------------------------------------------------- #
# Dispatch: .doc no longer reports itself as unconvertible
# --------------------------------------------------------------------------- #
def test_attachment_convert_handles_idtipoarquivo_7():
    html, n_tables, error = receita_attachments.convert(
        _raw(INDEX_DOC), 7, "Anexo Único.doc")
    assert error is None
    assert n_tables == 14
    assert "<table>" in html


def test_unreadable_doc_still_degrades_to_the_flattened_text():
    """A corrupt .doc must fall back, not raise — content never regresses to
    nothing just because a converter failed."""
    data = {
        "_view": "vigente",
        "epigrafeCompleta": "IN SRF nº 1",
        "ementas": [],
        "outrosSegmentos": [{
            "ordemSegmentoAto": 1, "idTipoSegmento": 16,
            "textoIntegra": "conteúdo achatado de reserva",
            "arquivoBinario": {
                "idArquivoBinario": 1, "idTipoArquivo": 7,
                "nomeArquivoBinario": "quebrado.doc",
                "arquivoBinario": "bm90IGEgd29yZCBmaWxlIGF0IGFsbA==",  # base64 junk
            },
        }],
    }
    stats: dict = {}
    fragment = ReceitaNormaFetcher._segments_html(data, stats=stats)
    assert "conteúdo achatado de reserva" in fragment
    assert stats["attachments_failed"] == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
