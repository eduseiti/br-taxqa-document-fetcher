#!/usr/bin/env python3
"""
Offline tests for Receita Federal **rendering fidelity**: ordinals, tables,
amendment/revocation annotations and annexes.

These lock in the four defects fixed in the rendering-fidelity work. All are
fixture-driven — no network, no browser. Fixtures under ``tests/fixtures/`` are
trimmed captures of the live API:

  * ``receita_ato_14400_vigente.json``  — IN SRF nº 84/2001, ``vigente`` view:
      segment 455831 revoked (blanked to the stub "II -" by the API itself) and
      segment 834855, an *anexo* carrying the inline ``tabela.htm``
  * ``receita_anexo_tabela.htm``        — that attachment, decoded (7×8 table)
  * ``receita_ato_15079_{vigente,original}.json`` — IN SRF nº 208/2002 segment
      815178, the same amended provision in both views, to pin the **inverted
      ``omitir`` mask** that made the old pipeline publish superseded wording
  * ``receita_ato_61197_vigente.json``  — IN RFB nº 1548, a **wholly revoked**
      act (``vigente: false`` + ``ancorasNoAto``)
  * ``receita_ato_92278_vigente.json``  — Resolução CGSN nº 140, a future-dated
      (``agendado``) segment: annotation with empty text
  * ``receita_anexo_sample.pdf``        — a real PDF annex with a ruled table

Run:
    python -m pytest tests/test_receita_rendering.py -v
"""

import json
import os
import sys

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "br_legal_parser")))

import receita_attachments  # noqa: E402
from receita_norma_fetcher import ACT_TYPES, ReceitaNormaFetcher  # noqa: E402
from receita_text_normalize import iter_rewrites, normalize_fragment  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _raw(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def _render(data: dict):
    """Render an act fixture to (fragment, plain text, docx Document)."""
    from legal_document_fetcher import WordDocumentBuilder

    fragment = ReceitaNormaFetcher._segments_html(data)
    text = ReceitaNormaFetcher.fragment_to_text(fragment)
    doc = WordDocumentBuilder().create_document(
        BeautifulSoup(fragment, "html.parser"), "Legal Document")
    return fragment, text, doc


def _all_runs(doc):
    for para in doc.paragraphs:
        for run in para.runs:
            yield run
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        yield run


# --------------------------------------------------------------------------- #
# 1. Ordinal normalization
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("source,expected", [
    # Real corpus contexts (see receita_text_normalize --audit-ordinals).
    ("o disposto nos arts. 5o e 6o da Lei", "o disposto nos arts. 5º e 6º da Lei"),
    ("no § 3o do art. 1o da Instrução", "no § 3º do art. 1º da Instrução"),
    ("atualizado até 1o de janeiro de 1996", "atualizado até 1º de janeiro de 1996"),
    ("do artigo 14 do Decreto No 3.659, de 14", "do artigo 14 do Decreto nº 3.659, de 14"),
    ("Instruções Normativas SRF Nos 127, de 30", "Instruções Normativas SRF nºs 127, de 30"),
    ("(IN SRF n°93, de 1997, art. 3°, §§ 5° e 6°)",
     "(IN SRF nº93, de 1997, art. 3º, §§ 5º e 6º)"),
    ("quinquênios, 13° salário, etc.", "quinquênios, 13º salário, etc."),
    ('"Artigo 6º Funcionários 19a.Seção', '"Artigo 6º Funcionários 19ª.Seção'),
    ("13a Edição, São Paulo", "13ª Edição, São Paulo"),
    ("duas opções: 1a) - realizá-las", "duas opções: 1ª) - realizá-las"),
])
def test_ordinal_rewrites(source, expected):
    assert normalize_fragment(source) == expected


@pytest.mark.parametrize("source", [
    # The preposition "No" — 336 corpus occurrences that must never be touched.
    "Art. 1º No caso de pessoa física",
    "Parágrafo único. No sistema de locação",
    "§ 6º No caso a que se refere",
    # Numbers that merely contain an ordinal-looking neighbourhood.
    "por valor igual ou inferior a R$ 20.000,00 (vinte mil reais)",
    "o disposto no art. 10 desta Instrução",
    "de 26 de dezembro de 1995",
    "conforme o Anexo I desta Instrução Normativa",
])
def test_ordinal_rules_leave_prose_untouched(source):
    assert normalize_fragment(source) == source


def test_ordinal_rules_do_not_touch_attribute_values():
    # Rules run on text nodes only, so an href can never be rewritten. (bs4
    # re-escapes '&' as '&amp;' on serialization, which is correct HTML — what
    # matters is that the ordinal tokens inside the attribute survive verbatim.)
    html = '<a href="/link.action?idAto=1o&n=No 5">art. 1o</a>'
    out = normalize_fragment(html)
    href = BeautifulSoup(out, "html.parser").find("a")["href"]
    assert href == "/link.action?idAto=1o&n=No 5"
    assert ">art. 1º<" in out


# --------------------------------------------------------------------------- #
# 2. <strike> is unwrapped, never rendered struck
# --------------------------------------------------------------------------- #
def test_strike_ordinal_unwrapped_to_plain_ordinal():
    # All 366 corpus occurrences are this typographic hack, not a revocation.
    assert normalize_fragment("Art. 1<strike>º</strike> Fica instituído.") == \
        "Art. 1º Fica instituído."


def test_non_ordinal_strike_unwrapped_and_reported():
    html = "<p>texto <strike>revogado aqui</strike> fim</p>"
    assert normalize_fragment(html) == "<p>texto revogado aqui fim</p>"
    rules = [rw.rule for rw in iter_rewrites(html)]
    assert "strike_non_ordinal" in rules  # surfaces in the audit, never silent


def test_strike_never_becomes_a_struck_run():
    from legal_document_fetcher import WordDocumentBuilder

    frag = normalize_fragment("<p>Art. 1<strike>º</strike> e <strike>outro</strike></p>")
    doc = WordDocumentBuilder().create_document(
        BeautifulSoup(frag, "html.parser"), "Legal Document")
    assert all(run.font.strike is not True for run in _all_runs(doc))
    assert "1º" in doc.paragraphs[0].text


# --------------------------------------------------------------------------- #
# 3. Inline HTML attachment becomes a real table
# --------------------------------------------------------------------------- #
def test_inline_html_attachment_yields_real_table():
    html, n_tables, error = receita_attachments.convert(
        _raw("receita_anexo_tabela.htm"), 4, "tabela.htm")
    assert error is None and n_tables == 1
    table = BeautifulSoup(html, "html.parser").find("table")
    rows = table.find_all("tr")
    assert len(rows) == 7
    assert len(rows[1].find_all(["td", "th"])) == 8
    cells = [c.get_text(" ", strip=True) for c in rows[2].find_all(["td", "th"])]
    assert cells[0] == "Até 1969" and cells[1] == "100%"


def test_act_with_attachment_renders_table_and_drops_flattened_text():
    data = _load("receita_ato_14400_vigente.json")
    fragment, text, doc = _render(data)

    # The old pipeline produced 0 tables; the table must now be a real one.
    assert len(doc.tables) >= 1
    table = doc.tables[0]
    assert len(table.rows) == 7 and len(table.columns) == 8
    assert table.rows[2].cells[0].text.strip() == "Até 1969"
    assert table.rows[2].cells[1].text.strip() == "100%"

    # The portal suppresses textoIntegra when an anexo's attachment renders, so
    # the flattened duplicate must be gone from both artifacts.
    flattened = "ANO DE % DE ANO DE % DE AQUISIÇÃO REDUÇÃO"
    assert flattened not in text
    assert flattened not in fragment


# --------------------------------------------------------------------------- #
# 4. Revocation: blanked wording + annotation, and the global no-strike rule
# --------------------------------------------------------------------------- #
def test_revoked_provision_is_a_stub_with_an_annotation():
    data = _load("receita_ato_14400_vigente.json")
    fragment, text, doc = _render(data)

    # ``vigente`` truncates a revoked provision to its label server-side.
    assert "alienação de bens ou direitos por valor igual ou inferior" not in text
    assert "R$ 20.000,00" not in text
    assert "II -" in text
    assert "Revogado(a) pelo(a) Instrução Normativa SRF nº 599" in text


def test_annotation_is_its_own_block_right_after_its_segment():
    data = _load("receita_ato_14400_vigente.json")
    _, text, _ = _render(data)
    lines = [ln for ln in text.split("\n\n") if ln.strip()]
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("II -"))
    assert "Revogado(a) pelo(a)" in lines[idx + 1]


def test_no_run_in_the_document_is_struck():
    """The global invariant: the target rendering has no strikethrough at all."""
    for name in ("receita_ato_14400_vigente.json", "receita_ato_15079_vigente.json",
                 "receita_ato_61197_vigente.json", "receita_ato_92278_vigente.json"):
        _, _, doc = _render(_load(name))
        assert all(run.font.strike is not True for run in _all_runs(doc)), name


# --------------------------------------------------------------------------- #
# 5. Amendment: the inverted omitir mask between views
# --------------------------------------------------------------------------- #
SUPERSEDED = "para trabalhar com vínculo empregatício, na data da chegada"
CURRENT = "atuar como médico bolsista no âmbito do Programa Mais Médicos"


def test_vigente_keeps_current_wording_and_annotates_it():
    _, text, _ = _render(_load("receita_ato_15079_vigente.json"))
    assert CURRENT in text
    assert SUPERSEDED not in text
    assert "Redação dada pelo(a) Instrução Normativa RFB nº 1383" in text


def test_original_view_publishes_the_superseded_wording_and_no_annotation():
    """Mirror-image assertion that locks in the bug the view switch replaces.

    Against ``original`` the ``omitir`` mask is inverted and ``ancorasDestino``
    is absent entirely — i.e. the old default published the *superseded* text
    with no indication that it had been amended.
    """
    _, text, _ = _render(_load("receita_ato_15079_original.json"))
    assert SUPERSEDED in text
    assert CURRENT not in text
    assert "Redação dada pelo(a)" not in text


# --------------------------------------------------------------------------- #
# 5b. Document-level cases
# --------------------------------------------------------------------------- #
def test_wholly_revoked_act_gets_exactly_one_banner_under_the_epigrafe():
    data = _load("receita_ato_61197_vigente.json")
    assert data["vigente"] is False  # fixture sanity
    fragment, text, _ = _render(data)

    banner = "Revogado(a) pelo(a) Instrução Normativa RFB nº 2172"
    assert text.count(banner) == 1
    blocks = [b for b in text.split("\n\n") if b.strip()]
    assert banner in blocks[1]        # immediately under the épigrafe
    assert data["epigrafeCompleta"] in blocks[0]


def test_future_dated_segment_renders_its_annotation_with_empty_text():
    _, text, _ = _render(_load("receita_ato_92278_vigente.json"))
    assert "Resolução CGSN nº 189, de 23 de abril de 2026" in text


def test_multivigente_fallback_strips_struck_segments():
    """An act that falls back to ``multivigente`` must not become the one
    document carrying superseded wording."""
    data = {
        "_view": "multivigente",
        "epigrafeCompleta": "Instrução Normativa SRF nº 1, de 1 de janeiro de 2000",
        "ementas": [],
        "outrosSegmentos": [
            {"ordemSegmentoAto": 1, "textoIntegra": "Art. 1º Texto vigente."},
            {"ordemSegmentoAto": 2, "tachado": True,
             "textoIntegra": "Art. 2º Texto revogado que não deve aparecer.",
             "ancorasDestino": [{"texto": "[Revogado(a) pelo(a) IN SRF nº 2]"}]},
        ],
    }
    _, text, doc = _render(data)
    assert "Texto vigente" in text
    assert "não deve aparecer" not in text
    assert all(run.font.strike is not True for run in _all_runs(doc))
    # The same act rendered from ``vigente`` keeps everything (tachado unset).
    data["_view"] = "vigente"
    _, text_vigente, _ = _render(data)
    assert "Art. 2º" in text_vigente


def test_omitir_segments_are_skipped_in_any_view():
    data = {
        "_view": "vigente",
        "epigrafeCompleta": "IN SRF nº 1",
        "ementas": [],
        "outrosSegmentos": [
            {"ordemSegmentoAto": 1, "omitir": False, "textoIntegra": "mantido"},
            {"ordemSegmentoAto": 2, "omitir": True, "textoIntegra": "SUPERSEDIDO"},
        ],
    }
    stats: dict = {}
    fragment = ReceitaNormaFetcher._segments_html(data, stats=stats)
    assert "SUPERSEDIDO" not in fragment
    assert stats["segments_omitted"] == 1


# --------------------------------------------------------------------------- #
# 6. PDF annex conversion
# --------------------------------------------------------------------------- #
def test_pdf_annex_yields_a_table():
    html, n_tables, error = receita_attachments.convert(
        _raw("receita_anexo_sample.pdf"), 6, "Anexo I.pdf")
    assert error is None and n_tables == 1
    table = BeautifulSoup(html, "html.parser").find("table")
    header = [c.get_text(strip=True) for c in table.find_all("tr")[0].find_all(["td", "th"])]
    assert header == ["Ano-calendário", "Valores isentos mensais (em R$)"]
    # Prose outside the table survives as a paragraph, in reading order.
    assert "RENDIMENTOS PREVIDENCIÁRIOS ISENTOS" in html
    assert html.index("RENDIMENTOS PREVIDENCIÁRIOS") < html.index("<table>")


def test_ods_annex_conversion_expands_repeated_cells():
    """``number-columns-repeated`` runs are expanded but capped, so the huge
    trailing padding every ODS writer emits does not explode the table."""
    import io
    import zipfile

    content = (
        '<?xml version="1.0"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:spreadsheet><table:table>'
        '<table:table-row>'
        '<table:table-cell><text:p>Ano</text:p></table:table-cell>'
        '<table:table-cell><text:p>Valor</text:p></table:table-cell>'
        '<table:table-cell table:number-columns-repeated="1024"/>'
        '</table:table-row>'
        '<table:table-row>'
        '<table:table-cell><text:p>2010</text:p></table:table-cell>'
        '<table:table-cell><text:p>1.499,15</text:p></table:table-cell>'
        '</table:table-row>'
        '</table:table></office:spreadsheet></office:body></office:document-content>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.xml", content)

    html, n_tables, error = receita_attachments.convert(buf.getvalue(), 17, "Planilha.ods")
    assert error is None and n_tables == 1
    rows = BeautifulSoup(html, "html.parser").find_all("tr")
    assert [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])] == ["Ano", "Valor"]
    assert [c.get_text(strip=True) for c in rows[1].find_all(["td", "th"])] == ["2010", "1.499,15"]


def test_annex_text_is_normalized_like_segment_text():
    """Annex-derived text goes through the same ordinal rules.

    Normalizing only ``textoIntegra`` left 173 legacy encodings in the corpus,
    all of them inside PDF annexes — which are, if anything, richer in them
    ("Art. 3°, §§ 1° e 4°") since they are scans of the same-era typescript.
    """
    import base64

    annex = base64.b64encode(
        b"<html><body><p>Art. 3&#176;, &#167;&#167; 1&#176; e 4&#176; da Lei No 8.383</p>"
        b"<table><tr><td>art. 1o</td></tr></table></body></html>"
    ).decode()
    data = {
        "_view": "vigente",
        "epigrafeCompleta": "Solução de Consulta Cosit nº 1",
        "ementas": [],
        "outrosSegmentos": [{
            "ordemSegmentoAto": 1, "idTipoSegmento": 16, "textoIntegra": "flattened",
            "arquivoBinario": {"idArquivoBinario": 1, "idTipoArquivo": 5,
                               "nomeArquivoBinario": "anexo.html",
                               "arquivoBinario": annex},
        }],
    }
    text = ReceitaNormaFetcher.fragment_to_text(
        ReceitaNormaFetcher._segments_html(data))
    assert "Art. 3º, §§ 1º e 4º da Lei nº 8.383" in text
    assert "art. 1º" in text                       # inside a table cell too
    assert "3°" not in text and " No 8.383" not in text


def test_xml_illegal_characters_are_stripped_not_fatal():
    """A PDF glyph PyMuPDF cannot map arrives as U+0001, which lxml rejects.

    Before this guard a single such character raised "All strings must be XML
    compatible" and cost the **entire act** (2 acts in the corpus), not just the
    glyph.
    """
    from legal_document_fetcher import WordDocumentBuilder

    data = {
        "_view": "vigente",
        "epigrafeCompleta": "Solução de Consulta Cosit nº 337",
        "ementas": [],
        "outrosSegmentos": [
            {"ordemSegmentoAto": 1,
             "textoIntegra": "\x01 35% (trinta e cinco por cento), para rendimentos"},
        ],
    }
    fragment = ReceitaNormaFetcher._segments_html(data)
    assert "\x01" not in fragment
    assert "35% (trinta e cinco por cento)" in fragment  # real content untouched

    # The whole point: the document must now build.
    doc = WordDocumentBuilder().create_document(
        BeautifulSoup(fragment, "html.parser"), "Legal Document")
    assert any("trinta e cinco" in p.text for p in doc.paragraphs)


@pytest.mark.parametrize("bad", ["\x00", "\x01", "\x0b", "\x1f", "\x7f", "￾"])
def test_xml_safe_strips_each_illegal_class(bad):
    from receita_text_normalize import xml_safe
    assert xml_safe(f"a{bad}b") == "ab"


def test_xml_safe_keeps_legal_whitespace_and_accents():
    from receita_text_normalize import xml_safe
    assert xml_safe("Instrução\tSRF\nnº 84\r\n") == "Instrução\tSRF\nnº 84\r\n"


def test_unconvertible_attachment_falls_back_to_flattened_text():
    """A legacy .doc annex has no in-process converter; the portal's flattened
    text must be kept so content never regresses to nothing."""
    data = {
        "_view": "vigente",
        "epigrafeCompleta": "IN SRF nº 1",
        "ementas": [],
        "outrosSegmentos": [{
            "ordemSegmentoAto": 1, "idTipoSegmento": 16,
            "textoIntegra": "Tabela de Atualização 1995 0,8166",
            "arquivoBinario": {
                "idArquivoBinario": 1, "idTipoArquivo": 7,
                "nomeArquivoBinario": "Anexo.doc",
                "arquivoBinario": None,
            },
        }],
    }
    stats: dict = {}
    # No client -> by-reference attachment cannot be fetched at all.
    fragment = ReceitaNormaFetcher._segments_html(data, client=None, stats=stats)
    assert "Tabela de Atualização 1995 0,8166" in fragment
    assert stats["attachments_failed"] == 1


# --------------------------------------------------------------------------- #
# 7. .txt reconstruction walks in document order and renders tables
# --------------------------------------------------------------------------- #
def test_fragment_to_text_renders_tables_as_pipe_delimited_rows():
    fragment = ('<p>antes</p>'
                '<table><tr><th>Ano</th><th>Valor</th></tr>'
                '<tr><td>2010</td><td>1.499,15</td></tr></table>'
                '<p>depois</p>')
    text = ReceitaNormaFetcher.fragment_to_text(fragment)
    assert text == "antes\n\nAno | Valor\n2010 | 1.499,15\n\ndepois"


def test_fragment_to_text_keeps_br_as_a_line_break():
    # The old ``_collapse_ws`` path folded "<br>"-separated lines into one.
    text = ReceitaNormaFetcher.fragment_to_text("<p>ANEXO ÚNICO <br> Tabela de Atualização</p>")
    assert text == "ANEXO ÚNICO\nTabela de Atualização"


def test_fragment_to_text_does_not_drop_content():
    """Regression guard for the old ``find_all('p')`` implementation, which
    silently dropped every table from the .txt."""
    data = _load("receita_ato_14400_vigente.json")
    _, text, _ = _render(data)
    assert "Até 1969 | 100%" in text
    assert "PERCENTUAIS DE REDUÇÃO DO GANHO DE CAPITAL" in text


# --------------------------------------------------------------------------- #
# 8. Attachment endpoint: URL shape, same-site headers, raw persistence
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, content=b"%PDF-1.4 fake", status_code=200):
        self.content = content
        self.status_code = status_code


class _FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse()


def test_attachment_client_url_and_headers(tmp_path):
    session = _FakeSession()
    client = receita_attachments.AttachmentClient(
        session, cache_dir=str(tmp_path / "cache"), delay=0)
    raw, source = client.fetch(14400, 19357)

    assert raw == b"%PDF-1.4 fake" and source == "endpoint"
    url, kwargs = session.calls[0]
    assert url == ("https://normasinternet2.receita.fazenda.gov.br"
                   "/api/consulta-externa/ato/14400/anexo/19357")
    # Without same-site Referer/Origin the WAF answers 403.
    assert kwargs["headers"]["Referer"].startswith(receita_attachments.API_HOST)
    assert kwargs["headers"]["Origin"] == receita_attachments.API_HOST


def test_attachment_client_uses_the_disk_cache_on_a_second_call(tmp_path):
    session = _FakeSession()
    client = receita_attachments.AttachmentClient(
        session, cache_dir=str(tmp_path / "cache"), delay=0)
    client.fetch(14400, 19357)
    raw, source = client.fetch(14400, 19357)
    assert source == "cache" and raw == b"%PDF-1.4 fake"
    assert len(session.calls) == 1  # no second request


def test_raw_attachment_bytes_are_always_persisted(tmp_path):
    session = _FakeSession()
    client = receita_attachments.AttachmentClient(
        session, cache_dir=str(tmp_path / "cache"), delay=0)
    attachments_dir = tmp_path / "documents" / "attachments"

    result = receita_attachments.retrieve(
        {"idArquivoBinario": 19357, "idTipoArquivo": 7,
         "nomeArquivoBinario": "Anexo Único.doc", "arquivoBinario": None},
        14400, client, attachments_dir, "in_srf_84_20011011")

    # Conversion is expected to fail (no LibreOffice), but the bytes must land.
    assert result.saved_as == "in_srf_84_20011011__19357_Anexo_Único.doc"
    assert (attachments_dir / result.saved_as).read_bytes() == b"%PDF-1.4 fake"
    assert result.source == "endpoint" and result.size == 13


def test_persisted_json_stays_a_lossless_mirror_of_the_api(tmp_path):
    """Normalization is a rendering concern: the saved JSON must keep the
    original encodings so any rule can be revisited without re-fetching."""
    data = {
        "idAto": 1, "epigrafeCompleta": "IN SRF nº 1",
        "epigrafe": {"tipoAto": {"idTipoAto": 42}, "numeroAto": "1",
                     "dataAto": "2000-01-01", "orgaos": [{"siglaOrgao": "SRF"}]},
        "ementas": [], "_view": "vigente",
        "outrosSegmentos": [{"ordemSegmentoAto": 1,
                             "textoIntegra": "art. 1o da Lei No 9.250"}],
    }
    fetcher = ReceitaNormaFetcher(ACT_TYPES["instrucao_normativa_srf"],
                                  output_dir=str(tmp_path), save_docx=False,
                                  fetch_attachments=False)
    from receita_norma_fetcher import ReceitaFetchResult
    result = ReceitaFetchResult(number="1", date="2000-01-01", success=False)
    fetcher._persist(data, "1", "2000-01-01", "IN SRF nº 1", result)

    saved = json.loads((tmp_path / "documents" / "in_srf_1_20000101.json").read_text("utf-8"))
    assert saved["outrosSegmentos"][0]["textoIntegra"] == "art. 1o da Lei No 9.250"
    assert saved["_fetched_at"]  # provenance for a moving-target view

    text = (tmp_path / "documents" / "in_srf_1_20000101.txt").read_text("utf-8")
    assert "art. 1º da Lei nº 9.250" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
