#!/usr/bin/env python3
"""
Offline unit tests for the decreto / decreto-lei fetching additions.

No network or browser required — index parsing and content cleaning are tested
against saved HTML fixtures under ``tests/fixtures/``.

Run:
    python -m pytest tests/test_decreto_fetching.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "br_legal_parser")))

from legal_document_processor import parse_pt_date, construct_urn_helper
from bs4 import BeautifulSoup

from planalto_decreto_fetcher import (
    PlanaltoIndexResolver,
    PlanaltoDecretoFetcher,
    _index_date_to_iso,
    _norm_number,
    _fix_ordinal_sups,
    _fix_bare_ordinals,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read().decode("iso-8859-1")


# --------------------------------------------------------------------------- #
# Portuguese long-form date parser
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("8 de junho de 1965", "1965-06-08"),
    ("24 de julho de 1963", "1963-07-24"),
    ("1º de maio de 1943", "1943-05-01"),       # ordinal day marker
    ("30 de abril de 2018", "2018-04-30"),
    ("10 de dezembro de 1937", "1937-12-10"),
    ("nonsense", None),
    ("", None),
])
def test_parse_pt_date(text, expected):
    assert parse_pt_date(text) == expected


# --------------------------------------------------------------------------- #
# URN construction per type
# --------------------------------------------------------------------------- #
def test_construct_urn_types():
    assert construct_urn_helper("9250", "1995-12-26") == \
        "urn:lex:br:federal:lei:1995-12-26;9250"
    assert construct_urn_helper("5452", "1943-05-01", "decreto.lei") == \
        "urn:lex:br:federal:decreto.lei:1943-05-01;5452"
    assert construct_urn_helper("3000", "1999-03-26", "decreto") == \
        "urn:lex:br:federal:decreto:1999-03-26;3000"


def test_construct_urn_no_date_uses_placeholder():
    assert construct_urn_helper("50656", None, "decreto") == \
        "urn:lex:br:federal:decreto:1900-01-01;50656"


# --------------------------------------------------------------------------- #
# Index short-date parsing (planalto's several formats)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("52.288, de 24.7.1963", "1963-07-24"),
    ("56.435, de 8.6.1965", "1965-06-08"),
    ("Decreto nº 9.358, de 30 .4.2018", "2018-04-30"),   # stray space
    ("22.400 de.31.12.1946", "1946-12-31"),              # 'de.' variant
    ("Decreto nº 7.030, de 14 de dezembro de 2009", "2009-12-14"),  # long form
    ("de 24.7.63", "1963-07-24"),                        # 2-digit year -> 19xx
])
def test_index_date_to_iso(text, expected):
    assert _index_date_to_iso(text) == expected


def test_norm_number():
    assert _norm_number("52.288") == "52288"
    assert _norm_number("9.358") == "9358"
    assert _norm_number("167") == "167"
    assert _norm_number(" 5 452 ") == "5452"


# --------------------------------------------------------------------------- #
# Ordinal superscript restoration (planalto encodes ordinals as <sup>o</sup>)
# --------------------------------------------------------------------------- #
def test_fix_ordinal_sups_converts_ordinal_superscripts():
    html = ("<p>DECRETO N<sup>o</sup> 361</p>"
            "<p>Art. 1<u><sup>o</sup></u> texto</p>"
            "<p>2<sup>a</sup> parte</p>"
            "<p>arts. 1<sup>os</sup> e 2</p>")
    soup = BeautifulSoup(html, "html.parser")
    _fix_ordinal_sups(soup)
    # get_text("") concatenates adjacent text nodes the way runs are joined in
    # the .docx (the sibling <sup> is replaced by a bare "º" text node, so
    # "N" + "º" -> "Nº"). A separator would spuriously insert spaces.
    text = soup.get_text("")
    assert "DECRETO Nº 361" in text
    assert "Art. 1º texto" in text
    assert "2ª parte" in text
    assert "1ºs" in text
    # No bare-letter ordinals leaked through.
    assert "N o" not in text and "1o " not in text


@pytest.mark.parametrize("text,expected", [
    ("§ 1o do art. 347", "§ 1º do art. 347"),
    ("Art. 2o Este Decreto", "Art. 2º Este Decreto"),
    ("art. 1o, inciso I", "art. 1º, inciso I"),
    ("§ 9o", "§ 9º"),
])
def test_fix_bare_ordinals_fixes_legal_refs(text, expected):
    assert _fix_bare_ordinals(text) == expected


@pytest.mark.parametrize("text", [
    "no ano de 1990",     # 'ano' must not be touched
    "apenas 10 anos",
    "o art. 84",          # no trailing o/a on the number
    "inciso IV",
])
def test_fix_bare_ordinals_leaves_ordinary_text(text):
    assert _fix_bare_ordinals(text) == text


def test_fix_ordinal_sups_leaves_non_ordinal_superscripts():
    # A superscript that is not an ordinal indicator (e.g. a footnote marker or
    # exponent) must be left untouched.
    html = "<p>x<sup>2</sup> e nota<sup>1</sup></p>"
    soup = BeautifulSoup(html, "html.parser")
    _fix_ordinal_sups(soup)
    assert soup.find("sup") is not None  # still present
    assert "º" not in soup.get_text()


# --------------------------------------------------------------------------- #
# Index HTML parsing against a saved decade-index fragment
# --------------------------------------------------------------------------- #
def test_parse_index_html_maps_number_date_to_url():
    html = _read_fixture("index_1960_1969_fragment.html")
    base = "https://www.planalto.gov.br/ccivil_03/decreto/Quadros/1960-1969.htm"
    entries = PlanaltoIndexResolver.parse_index_html(html, base)

    # 52.288 of 1963-07-24 -> ../1950-1969/D52288.htm (resolved absolute)
    assert entries["by_num_date"][("52288", "1963-07-24")] == \
        "https://www.planalto.gov.br/ccivil_03/decreto/1950-1969/D52288.htm"
    # 56.435 of 1965-06-08 -> ../Antigos/D56435.htm
    assert entries["by_num_date"][("56435", "1965-06-08")] == \
        "https://www.planalto.gov.br/ccivil_03/decreto/Antigos/D56435.htm"

    # Number-only fallback lookup is also populated.
    assert "52288" in entries["by_num"]
    assert entries["by_num"]["56435"][0][0] == "1965-06-08"


# --------------------------------------------------------------------------- #
# Content cleaning: decree body only, no page chrome
# --------------------------------------------------------------------------- #
def test_extract_clean_content_strips_chrome():
    html = _read_fixture("decree_d0361.html")
    fetcher = PlanaltoDecretoFetcher.__new__(PlanaltoDecretoFetcher)  # no I/O in __init__ needed
    content = fetcher.extract_clean_content(html)
    assert content is not None
    text = content.get_text(" ", strip=True)

    # The enacted text is present...
    assert "DECRETO" in text.upper()
    assert "361" in text
    # ...but the header/footer chrome is gone.
    assert "Subchefia para Assuntos" not in text
    assert "Casa Civil" not in text
    assert "Download para anexo" not in text.lower() or "download para anexo" not in text.lower()


def test_extract_clean_content_starts_at_decreto_marker():
    html = _read_fixture("decree_d0361.html")
    fetcher = PlanaltoDecretoFetcher.__new__(PlanaltoDecretoFetcher)
    content = fetcher.extract_clean_content(html)
    # First non-empty block should be the DECRETO heading, not the header block.
    first_block = next(
        (c.get_text(" ", strip=True) for c in content.find_all(recursive=False)
         if c.get_text(strip=True)),
        "",
    )
    assert first_block.upper().startswith("DECRETO")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
