#!/usr/bin/env python3
"""
Offline unit tests for the Instrução Normativa (Receita Federal) fetching path.

No network or browser required — idAto extraction, verification, and text
reconstruction are tested against saved fixtures under ``tests/fixtures/``:

  * ``receita_consulta_in107_1988.html``   — a trimmed consulta.action result
  * ``receita_ato_14681_original.json``     — the ``visao/original`` API JSON
  * ``receita_ato_14681_vigente_406.json``  — a 406 view-unavailable body

Run:
    python -m pytest tests/test_instrucao_normativa_fetching.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "br_legal_parser")))

from receita_norma_fetcher import (  # noqa: E402
    ACT_TYPES,
    ReceitaNormaFetcher,
    build_search_params,
    extract_id_atos,
    _norm_number,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
IN_SRF = ACT_TYPES["instrucao_normativa_srf"]


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


def _load_json(name: str) -> dict:
    return json.loads(_read(name))


def _fetcher(tmp_path) -> ReceitaNormaFetcher:
    """A fetcher with no network I/O in __init__ except output dir creation."""
    return ReceitaNormaFetcher(IN_SRF, output_dir=str(tmp_path), save_docx=False)


# --------------------------------------------------------------------------- #
# idAto extraction from the consulta.action result page
# --------------------------------------------------------------------------- #
def test_extract_id_atos_from_result_html():
    html = _read("receita_consulta_in107_1988.html")
    ids = extract_id_atos(html)
    assert ids == ["14681"]  # unique, first-seen order


def test_extract_id_atos_dedups_and_handles_antigo_variant():
    html = ('<a href="link.action?idAto=100">a</a>'
            '<a href="link.action?antigo=1&idAto=100">dup</a>'
            '<a href="link.action?antigo=1&amp;idAto=200">b</a>')
    assert extract_id_atos(html) == ["100", "200"]


def test_extract_id_atos_empty():
    assert extract_id_atos("<html>no results</html>") == []


# --------------------------------------------------------------------------- #
# Search field set: the full form must be submitted, type code + number set
# --------------------------------------------------------------------------- #
def test_build_search_params_full_field_set():
    p = build_search_params(IN_SRF, "107", 1988, tipo_data="1")
    assert p["tiposAtosSelecionados"] == "42"
    assert p["lblTiposAtosSelecionados"] == "Instrução Normativa"
    assert p["numero_ato"] == "107"
    assert p["ano_ato"] == "1988"
    assert p["tipoData"] == "1"
    assert p["tipoConsulta"] == "formulario"
    # Every documented field is present (empty ones included).
    for key in ("facetsExistentes", "orgaosSelecionados", "ordemColuna",
                "ordemDirecao", "tipoAtoFacet", "siglaOrgaoFacet",
                "anoAtoFacet", "termoBusca", "p"):
        assert key in p


def test_build_search_params_strips_dotted_number_and_blank_year():
    p = build_search_params(IN_SRF, "1.234", None)
    assert p["numero_ato"] == "1234"
    assert p["ano_ato"] == ""


# --------------------------------------------------------------------------- #
# Verification against the canonical (type, number, órgão, date)
# --------------------------------------------------------------------------- #
def test_verify_accepts_matching_act(tmp_path):
    data = _load_json("receita_ato_14681_original.json")
    f = _fetcher(tmp_path)
    assert f.verify(data, "107", "1988-07-14") is True


def test_verify_rejects_wrong_date(tmp_path):
    data = _load_json("receita_ato_14681_original.json")
    f = _fetcher(tmp_path)
    assert f.verify(data, "107", "2001-10-11") is False


def test_verify_rejects_wrong_number(tmp_path):
    data = _load_json("receita_ato_14681_original.json")
    f = _fetcher(tmp_path)
    assert f.verify(data, "108", "1988-07-14") is False


def test_verify_rejects_wrong_orgao(tmp_path):
    # Same act, but asked for as an RFB act -> órgão sigla mismatch (SRF vs RFB).
    data = _load_json("receita_ato_14681_original.json")
    f = ReceitaNormaFetcher(ACT_TYPES["instrucao_normativa_rfb"],
                            output_dir=str(tmp_path), save_docx=False)
    assert f.verify(data, "107", "1988-07-14") is False


def test_verify_rejects_wrong_type(tmp_path):
    data = _load_json("receita_ato_14681_original.json")
    # Mutate the type sigla to simulate a non-IN act.
    data["epigrafe"]["tipoAto"]["siglaTipoAto"] = "PT"
    f = _fetcher(tmp_path)
    assert f.verify(data, "107", "1988-07-14") is False


def test_verify_number_only_when_no_date(tmp_path):
    # Undated canonical entry: date is not used as a discriminator.
    data = _load_json("receita_ato_14681_original.json")
    f = _fetcher(tmp_path)
    assert f.verify(data, "107", None) is True


# --------------------------------------------------------------------------- #
# Text reconstruction from épigrafe + ementas + outrosSegmentos
# --------------------------------------------------------------------------- #
def test_reconstruct_text_includes_epigrafe_ementa_and_body(tmp_path):
    data = _load_json("receita_ato_14681_original.json")
    text = ReceitaNormaFetcher.reconstruct_text(data)
    assert "Instrução Normativa SRF nº 107" in text
    # Ementa summary present.
    assert "lucro real" in text
    # Body first segment present.
    assert "Secretário da Receita Federal" in text
    # HTML tags stripped (no raw <br> etc.).
    assert "<br>" not in text and "<p>" not in text


def test_reconstruct_text_strips_segment_markup(tmp_path):
    data = {
        "epigrafeCompleta": "Instrução Normativa SRF nº 1, de 1 de janeiro de 2000",
        "ementas": [],
        "outrosSegmentos": [
            {"ordemSegmentoAto": 2, "textoIntegra": "Seção I \n<br>\n Introdução"},
            {"ordemSegmentoAto": 1, "textoIntegra": "<b>Art. 1º</b> Fica instituído."},
            {"ordemSegmentoAto": 3, "omitir": True, "textoIntegra": "OMITIDO"},
        ],
    }
    text = ReceitaNormaFetcher.reconstruct_text(data)
    # Ordered by ordemSegmentoAto, omitted segment dropped, markup stripped.
    assert text.index("Art. 1º") < text.index("Seção I")
    assert "OMITIDO" not in text
    assert "<b>" not in text and "<br>" not in text


# --------------------------------------------------------------------------- #
# 406 view-unavailable fixture is well-formed (documents the fallback trigger)
# --------------------------------------------------------------------------- #
def test_406_fixture_is_not_acceptable():
    body = _load_json("receita_ato_14681_vigente_406.json")
    assert body["status"] == "NOT_ACCEPTABLE"
    assert "não está disponível" in body["message"]


def test_norm_number():
    assert _norm_number("1.234") == "1234"
    assert _norm_number(" 107 ") == "107"
    assert _norm_number("84") == "84"


# --------------------------------------------------------------------------- #
# Republication selection: same act published multiple times in the DOU
# --------------------------------------------------------------------------- #
def _act(id_ato, pub, orgao="SRF", numero="208", data="2002-09-27"):
    return (id_ato, {
        "dataPublicacao": pub,
        "epigrafe": {
            "tipoAto": {"siglaTipoAto": "IN"},
            "numeroAto": numero,
            "dataAto": data,
            "orgaos": [{"siglaOrgao": orgao}],
        },
    })


def test_select_primary_picks_earliest_publication(tmp_path):
    # The earliest DOU publication carries the full text; later ones are
    # retificação excerpts. Order of discovery should not matter.
    f = _fetcher(tmp_path)
    matched = [
        _act("15081", "2004-03-11"),
        _act("15080", "2002-10-08"),
        _act("15079", "2002-10-01"),
    ]
    primary, alternates, ambiguous = f._select_primary(matched)
    assert ambiguous is False
    assert primary[0] == "15079"                       # earliest publication
    assert {a[0] for a in alternates} == {"15080", "15081"}


def test_select_primary_single_candidate(tmp_path):
    f = _fetcher(tmp_path)
    primary, alternates, ambiguous = f._select_primary([_act("14681", "1988-07-20")])
    assert ambiguous is False and primary[0] == "14681" and alternates == []


def test_select_primary_flags_distinct_acts_as_ambiguous(tmp_path):
    # Two acts with the same number but different act dates (only reachable via an
    # undated canonical entry) are genuinely ambiguous -> route to review.
    f = _fetcher(tmp_path)
    matched = [
        _act("100", "2001-10-15", data="2001-10-11"),
        _act("200", "1979-12-25", data="1979-12-20"),
    ]
    primary, alternates, ambiguous = f._select_primary(matched)
    assert ambiguous is True and primary is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
