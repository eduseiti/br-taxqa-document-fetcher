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
    # Verification keys on the numeric idTipoAto (== the form tipo code), which is
    # robust to the punctuated siglas; mutate it to simulate a non-IN act.
    data["epigrafe"]["tipoAto"]["idTipoAto"] = 57  # Portaria
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
# Generalized registry: all Receita-portal act types, one folder per kind
# --------------------------------------------------------------------------- #
def _epi(id_tipo, numero, data_ato, orgaos):
    """Minimal épigrafe JSON for verify() tests."""
    return {"epigrafe": {
        "tipoAto": {"idTipoAto": id_tipo},
        "numeroAto": numero,
        "dataAto": data_ato,
        "orgaos": [{"siglaOrgao": o} for o in orgaos],
    }}


def test_registry_covers_expected_types():
    # A spread across tipo codes and órgãos must be registered.
    for slug, code, orgao in [
        ("instrucao_normativa_srf", "42", "SRF"),
        ("instrucao_normativa_rfb", "42", "RFB"),
        ("solucao_de_consulta_cosit", "72", "Cosit"),
        ("parecer_normativo_cst", "59", "CST"),
        ("ato_declaratorio_comum_pgfn", "7", "PGFN"),
        ("ato_declaratorio_interpretativo_srf", "10", "SRF"),
        ("ato_declaratorio_executivo_codac", "9", "Codac"),
        ("portaria_mf", "57", "MF"),
        ("resolucao_cgsn", "67", "CGSN"),
    ]:
        act = ACT_TYPES[slug]
        assert act.tipo_code == code
        assert act.orgao == orgao
    # Edge types match on tipo+number+date only (no fixed órgão).
    assert ACT_TYPES["solucao_de_consulta"].orgao is None
    assert ACT_TYPES["parecer_normativo"].orgao is None


def test_search_params_include_orgao_filter():
    # Fixed-órgão type submits the órgão facet value; edge type leaves it empty.
    p = build_search_params(ACT_TYPES["ato_declaratorio_comum_srf"], "22", 1997)
    assert p["orgaosSelecionados"] == "SRF"
    assert p["tiposAtosSelecionados"] == "7"
    p_edge = build_search_params(ACT_TYPES["solucao_de_consulta"], "15", 2009)
    assert p_edge["orgaosSelecionados"] == ""


def test_verify_by_id_tipo_ato_for_non_in_type(tmp_path):
    # Ato Declaratório (code 7), sigla "AD" — verified by idTipoAto, not sigla.
    f = ReceitaNormaFetcher(ACT_TYPES["ato_declaratorio_comum_srf"],
                            output_dir=str(tmp_path), save_docx=False)
    assert f.verify(_epi(7, "22", "1997-04-30", ["SRF"]), "22", "1997-04-30") is True
    # Wrong tipo code (executivo=9) rejected even with matching number/date/órgão.
    assert f.verify(_epi(9, "22", "1997-04-30", ["SRF"]), "22", "1997-04-30") is False


def test_verify_orgao_case_insensitive(tmp_path):
    # Portal mixes casing (Cosit vs COSIT); verification must be case-insensitive.
    f = ReceitaNormaFetcher(ACT_TYPES["solucao_de_consulta_cosit"],
                            output_dir=str(tmp_path), save_docx=False)
    assert f.verify(_epi(72, "100", "2020-09-28", ["COSIT"]), "100", "2020-09-28") is True
    assert f.verify(_epi(72, "100", "2020-09-28", ["SRF"]), "100", "2020-09-28") is False


def test_verify_skips_orgao_when_none(tmp_path):
    # orgao=None: any órgão accepted, still keyed on tipo+number+date.
    f = ReceitaNormaFetcher(ACT_TYPES["solucao_de_consulta"],
                            output_dir=str(tmp_path), save_docx=False)
    assert f.verify(_epi(72, "15", "2009-03-09", ["SRRF03"]), "15", "2009-03-09") is True
    assert f.verify(_epi(73, "15", "2009-03-09", ["SRRF03"]), "15", "2009-03-09") is False


def test_ad_collision_resolved_by_orgao_and_date(tmp_path):
    # AD nº 22/1997 exists for SRF, Cosar and Cosit with 3 different dates.
    # The SRF fetcher accepts only the SRF/date-matching one.
    f = ReceitaNormaFetcher(ACT_TYPES["ato_declaratorio_comum_srf"],
                            output_dir=str(tmp_path), save_docx=False)
    srf = _epi(7, "22", "1997-04-30", ["SRF"])
    cosar = _epi(7, "22", "1997-06-02", ["Cosar"])
    cosit = _epi(7, "22", "1997-07-17", ["Cosit"])
    assert f.verify(srf, "22", "1997-04-30") is True
    assert f.verify(cosar, "22", "1997-04-30") is False   # wrong órgão + date
    assert f.verify(cosit, "22", "1997-04-30") is False


def test_persist_writes_under_type_documents_dir(tmp_path):
    f = ReceitaNormaFetcher(ACT_TYPES["solucao_de_consulta_cosit"],
                            output_dir=str(tmp_path), save_docx=False)
    assert f.documents_dir == tmp_path / "documents"
    assert f._stem("100", "2020-09-28") == "sc_cosit_100_20200928"


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
