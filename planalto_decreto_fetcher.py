#!/usr/bin/env python3
"""
Planalto Decreto Fetcher

Fetches plain ``decreto`` documents from planalto.gov.br and saves them as clean
``.docx`` files (document text only, free of the page header/nav/footer chrome).

Why a separate module from ``br_legal_parser``:
    normas.leg.br is a JavaScript SPA whose content lives in a Shadow DOM and
    requires Selenium. planalto.gov.br decree pages are, by contrast, *static*
    HTML served as ISO-8859-1, and their URLs are not formula-derivable — they
    must be discovered from year/decade index pages. This module handles that
    index-driven discovery and static fetching, then reuses
    ``WordDocumentBuilder`` from ``br_legal_parser`` so the produced ``.docx``
    has the same shape as the normas.leg.br documents.

Access mechanism (as used by planalto):
    _dec_ano.htm  ->  per-year or per-decade index  ->  individual decree page
The per-year/decade index lists every decree as
    "<number>, de <D.M.YYYY>"  with a direct (irregular) href.
We scrape that index and match by (number, date); we never template decree URLs.
"""

import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Reuse the docx builder from the sibling br_legal_parser project.
sys.path.append(os.path.join(os.path.dirname(__file__), "br_legal_parser"))
from legal_document_fetcher import WordDocumentBuilder  # noqa: E402

logger = logging.getLogger(__name__)

CCIVIL = "https://www.planalto.gov.br/ccivil_03/"
BASE = CCIVIL + "decreto/"  # decree index + most decree pages live here
DEC_ANO_URL = urljoin(BASE, "_dec_ano.htm")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Matches the "DECRETO Nº <number>, DE <date>" heading that opens the enacted
# text. Tolerates the MS-Word "N o"/"N.º" spellings and non-breaking spaces.
_DECRETO_MARKER = re.compile(r"DECRETO\s*N", re.IGNORECASE)


@dataclass
class DecreteFetchResult:
    number: str
    date: Optional[str]
    success: bool
    url: Optional[str] = None
    filename: str = ""
    error_message: Optional[str] = None
    needs_review: bool = False


def _norm_number(raw: str) -> str:
    """Digits only, dots/spaces stripped."""
    return re.sub(r"[.\s]", "", raw or "")


# Ordinal indicators that planalto encodes as a superscript letter, e.g.
# "Art. 1<sup>o</sup>" or "DECRETO N<sup>o</sup>". Flattening the HTML with
# get_text() turns these into a bare "o"/"a" ("Art. 1o", "DECRETO No"), losing
# the ordinal reading. Map the superscript letter to its Unicode ordinal char.
_SUP_ORDINAL = {"o": "º", "a": "ª", "os": "ºs", "as": "ªs"}


# Bare-letter ordinals that planalto sometimes writes as plain ASCII in the
# source (e.g. "§ 1o", "Art. 2o", "art. 1o") instead of "§ 1º". Restricted to
# these high-confidence legal-reference contexts so ordinary words are never
# touched. The number is captured and the trailing o/a becomes º/ª.
_BARE_ORDINAL_RE = re.compile(
    r"((?:Art|art)\.?\s+|§\s*)(\d+)([oa])\b"
)


def _fix_bare_ordinals(text: str) -> str:
    """Restore º/ª on bare-letter ordinals in legal references (Art./art./§ + No).

    Scoped to the "Art."/"art."/"§" prefixes so ordinary words are never
    touched. The prefix and number are preserved; trailing o/a becomes º/ª.
    """
    def repl(m):
        ordinal = "º" if m.group(3) == "o" else "ª"
        return f"{m.group(1)}{m.group(2)}{ordinal}"
    return _BARE_ORDINAL_RE.sub(repl, text)


def _fix_ordinal_sups(soup: BeautifulSoup) -> None:
    """In-place: replace ordinal-indicator <sup> tags with the proper º/ª char.

    Only <sup> tags whose entire text is an ordinal letter (o/a/os/as, any case)
    are converted — superscripts used for footnote markers, exponents, etc. are
    left untouched.
    """
    for sup in soup.find_all("sup"):
        key = sup.get_text(strip=True).lower()
        repl = _SUP_ORDINAL.get(key)
        if repl is not None:
            # Replace the whole <sup> (and any wrapping <u>) with the ordinal
            # char. Unwrapping a surrounding <u> avoids an empty underline tag.
            sup.replace_with(repl)


_PT_MONTHS_IDX = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12",
}


def _index_date_to_iso(text: str) -> Optional[str]:
    """Parse a planalto index date to 'YYYY-MM-DD'.

    Handles the several formats seen across per-year and per-decade indexes:
      * short numeric  "24.7.1963", "30 .4.2018", "de.31.12.1946"
      * long form      "de 30 de abril de 2018"
    Accepts 1- or 2-digit day/month and 2- or 4-digit year; 2-digit years are
    treated as 20th century (these indexes cover pre-2000 documents).
    """
    # Long form first (day de <month> de year).
    m = re.search(r"(\d{1,2})\s*de\s*([a-zç]+)\s*de\s*(\d{4})", text, re.IGNORECASE)
    if m:
        mo = _PT_MONTHS_IDX.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo}-{m.group(1).zfill(2)}"
    # Short numeric D.M.YYYY, tolerating stray spaces around the dots.
    m = re.search(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{2,4})", text)
    if not m:
        return None
    d, mo, y = m.groups()
    if len(y) == 2:
        y = "19" + y
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"


class PlanaltoIndexResolver:
    """Resolves decree number+date to a concrete planalto decree URL.

    Fetches and caches the top-level year index and each needed per-year /
    per-decade index page, building a {(number, iso_date): url} lookup.
    """

    def __init__(self, session: requests.Session):
        self.session = session
        self._year_index_map: Optional[Dict[str, str]] = None   # "1963" -> index url
        self._grouped_indexes: List[Tuple[range, str]] = []      # (year range, url)
        # Per index-URL cache of {(number, iso_date): decree_url} and
        # {number: [(iso_date, decree_url), ...]} for number-only fallback.
        self._entry_cache: Dict[str, Dict] = {}

    # -- top-level year index ------------------------------------------------
    def _load_year_index(self) -> None:
        if self._year_index_map is not None:
            return
        html = self._get(DEC_ANO_URL)
        soup = BeautifulSoup(html, "html.parser")
        year_map: Dict[str, str] = {}
        grouped: List[Tuple[range, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if ".htm" not in href.lower():
                continue
            abs_url = urljoin(DEC_ANO_URL, href)
            # Grouped decade index: e.g. Quadros/1960-1969.htm. Match only the
            # index *filename* — the ccivil path also embeds era folders like
            # "_Ato2007-2010" which are NOT decade groupings (those are per-year).
            m_range = re.search(r"/(\d{4})-(\d{4})\.htm", href)
            if m_range:
                lo, hi = int(m_range.group(1)), int(m_range.group(2))
                grouped.append((range(lo, hi + 1), abs_url))
                continue
            if "anteriores_a_" in href:
                m = re.search(r"anteriores_a_(\d{4})", href)
                if m:
                    grouped.append((range(0, int(m.group(1))), abs_url))
                continue
            # Single-year index. Only trust these two shapes:
            #   .../YYYY/Decreto/_decretosYYYY.htm  (recent, per-year folder)
            #   Quadros/YYYY.htm                    (1980..2000 single-year)
            # Prefer the year embedded in the href (anchor text can be blank).
            # Per-year index links come in several href shapes across eras
            # (_decretosYYYY.htm, _quadro.htm under a /YYYY/ folder,
            # Quadro_YYYY.htm, Quadros/YYYY.htm). The one reliable signal is the
            # anchor text, which is exactly the 4-digit year for every per-year
            # link. Key off that; the href itself is opaque and era-specific.
            m_text_year = re.match(r"^\s*((?:19|20)\d{2})\s*$", text)
            if m_text_year:
                year_map[m_text_year.group(1)] = abs_url
        self._year_index_map = year_map
        self._grouped_indexes = grouped
        logger.info(
            f"Year index loaded: {len(year_map)} per-year, {len(grouped)} grouped ranges"
        )

    def _index_url_for_year(self, year: int) -> Optional[str]:
        self._load_year_index()
        # Prefer a dedicated per-year index.
        url = self._year_index_map.get(str(year))
        if url:
            return url
        # Else fall back to the grouped/decade index covering the year.
        for yr_range, gurl in self._grouped_indexes:
            if year in yr_range:
                return gurl
        return None

    # -- per-year / per-decade index -----------------------------------------
    @staticmethod
    def parse_index_html(html: str, base_url: str) -> Dict:
        """Parse a planalto decree index page into number/date -> url lookups.

        Pure function (no network) so it can be unit-tested against fixtures.

        Returns a dict with:
          - "by_num_date": {(number_digits, iso_date): decree_url}
          - "by_num":      {number_digits: [(iso_date_or_None, decree_url), ...]}
        """
        soup = BeautifulSoup(html, "html.parser")
        by_num_date: Dict[Tuple[str, str], str] = {}
        by_num: Dict[str, List[Tuple[str, str]]] = {}
        for a in soup.find_all("a", href=True):
            if ".htm" not in a["href"].lower():
                continue
            # Normalize whitespace: entries wrap across lines / spans and use
            # several separators, e.g. "52.288, de 24.7.1963",
            # "Decreto nº 9.358, de 30 .4.2018", "22.400 de.31.12.1946".
            text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            # Number: first "NN.NNN" (or bare digits) token, optionally after
            # a "Decreto nº" prefix. Require it to sit before a date separator.
            m_num = re.search(r"(?:decreto\s*n[ºo°.]*\s*)?(\d{1,3}(?:\.\d{3})*|\d{2,})\b",
                              text, re.IGNORECASE)
            if not m_num:
                continue
            num = _norm_number(m_num.group(1))
            iso = _index_date_to_iso(text)
            decree_url = urljoin(base_url, a["href"])
            if iso:
                by_num_date[(num, iso)] = decree_url
            by_num.setdefault(num, []).append((iso, decree_url))
        return {"by_num_date": by_num_date, "by_num": by_num}

    def _load_entries(self, index_url: str) -> Dict:
        if index_url in self._entry_cache:
            return self._entry_cache[index_url]
        html = self._get(index_url)
        entries = self.parse_index_html(html, index_url)
        self._entry_cache[index_url] = entries
        logger.info(f"Parsed {len(entries['by_num_date'])} dated entries from {index_url}")
        return entries

    def resolve(self, number: str, iso_date: Optional[str], year: Optional[int]) -> Tuple[Optional[str], bool]:
        """Return (decree_url, needs_review).

        Matches on (number, date) when a date is available; otherwise falls back
        to a number-only match and flags needs_review.
        """
        num = _norm_number(number)
        # Determine which index to search.
        search_year = year
        if search_year is None and iso_date:
            search_year = int(iso_date.split("-")[0])
        if search_year is None:
            logger.warning(f"Decreto {number}: no year available; cannot pick index")
            return None, True

        index_url = self._index_url_for_year(search_year)
        if not index_url:
            logger.warning(f"Decreto {number}: no index page found for year {search_year}")
            return None, iso_date is None
        entries = self._load_entries(index_url)

        if iso_date and (num, iso_date) in entries["by_num_date"]:
            return entries["by_num_date"][(num, iso_date)], False

        # Number-only fallback (e.g. undated reference like Decreto nº 50.656).
        candidates = entries["by_num"].get(num, [])
        if len(candidates) == 1:
            logger.info(f"Decreto {number}: matched by number only -> needs_review")
            return candidates[0][1], True
        if len(candidates) > 1 and iso_date:
            # Try loosening the day/month if date present but exact key missed.
            for cand_iso, curl in candidates:
                if cand_iso and cand_iso[:4] == iso_date[:4]:
                    logger.info(f"Decreto {number}: matched by number + year -> needs_review")
                    return curl, True

        # Last resort: some decrees exist on planalto but are not linked from the
        # summary indexes (e.g. only under ../Atos/decretos/YYYY/). Probe the
        # known URL templates for the decree's own year and accept the first
        # that returns HTTP 200.
        probed = self._probe_direct_url(num, search_year)
        if probed:
            logger.info(f"Decreto {number}: found via direct-URL probe -> needs_review")
            return probed, True

        logger.warning(f"Decreto {number} ({iso_date}) not found in {index_url}")
        return None, True

    def _probe_direct_url(self, num: str, year: int) -> Optional[str]:
        """Try well-known planalto decree URL templates; return first 200 hit."""
        n = num  # digits only
        # Ordered by observed frequency. {y}=year, {n}=number.
        templates = [
            f"{CCIVIL}Atos/decretos/{year}/D{n}.html",  # sibling of decreto/
            f"{BASE}Antigos/D{n}.htm",
            f"{BASE}1950-1969/D{n}.htm",
            f"{BASE}1970-1979/D{n}.htm",
            f"{BASE}1930-1949/D{n}.htm",
            f"{BASE}{year}/D{n}.htm",
            f"{BASE}D{n}.htm",
        ]
        seen = set()
        for url in templates:
            if url in seen:
                continue
            seen.add(url)
            try:
                # planalto mishandles HEAD across its 301 case-normalizing
                # redirect, so use a streamed GET and inspect the final status.
                resp = self.session.get(url, timeout=20, allow_redirects=True, stream=True)
                status = resp.status_code
                resp.close()
                if status == 200:
                    return resp.url
            except requests.RequestException:
                continue
        return None

    # -- fetch helper --------------------------------------------------------
    def _get(self, url: str) -> str:
        resp = self.session.get(url, timeout=40, allow_redirects=True)
        resp.raise_for_status()
        # planalto pages are ISO-8859-1 with no charset meta.
        resp.encoding = "iso-8859-1"
        return resp.text


class PlanaltoDecretoFetcher:
    """Fetch decretos from planalto and save clean docx files."""

    def __init__(self, output_dir: str = "./output_decretos/documents",
                 delay_between_requests: float = 1.5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self.resolver = PlanaltoIndexResolver(self.session)
        self.doc_builder = WordDocumentBuilder()

    # -- content extraction --------------------------------------------------
    def extract_clean_content(self, html: str) -> Optional[BeautifulSoup]:
        """Return a BeautifulSoup fragment with only the decree text.

        Strips the "Presidência da República / Casa Civil / Subchefia" header
        block and page nav/footer; keeps everything from the "DECRETO Nº ..."
        marker onward (including the ementa table and any appended treaty text),
        dropping the trailing "Download para anexo" line.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Restore ordinal characters that planalto encodes as superscript
        # letters (Art. 1<sup>o</sup> -> Art. 1º) before any text flattening.
        _fix_ordinal_sups(soup)

        # Also fix bare-letter ordinals that appear as plain ASCII in the source
        # (e.g. "§ 1o", "art. 2o") within a single text node.
        from bs4 import NavigableString
        for ns in list(soup.find_all(string=_BARE_ORDINAL_RE)):
            fixed = _fix_bare_ordinals(str(ns))
            if fixed != str(ns):
                ns.replace_with(NavigableString(fixed))

        # Drop non-content elements outright.
        for tag in soup(["script", "style", "meta", "link", "noscript", "title", "head"]):
            tag.decompose()

        # Drop the "Download para anexo" link wherever it appears — it is a page
        # affordance (the decree's annex is an external file), not decree text.
        for a in soup.find_all("a"):
            if "download para anexo" in a.get_text(" ", strip=True).lower():
                a.decompose()

        body = soup.body or soup

        # Collect the top-level children in order, starting at the DECRETO marker.
        children = [c for c in body.find_all(recursive=False)]
        # Some pages wrap everything in a single container div; descend if so.
        if len(children) == 1 and getattr(children[0], "name", None) == "div":
            inner = [c for c in children[0].find_all(recursive=False)]
            if len(inner) > len(children):
                children = inner

        start_idx = None
        for i, c in enumerate(children):
            if getattr(c, "name", None) is None:
                continue
            text = c.get_text(" ", strip=True)
            if _DECRETO_MARKER.search(text) and re.search(r"\d", text):
                # Guard against the header table that merely mentions "Decreto".
                if "Subchefia" in text or "Presid" in text and "Casa Civil" in text:
                    continue
                start_idx = i
                break

        container = soup.new_tag("div")
        if start_idx is None:
            # Fallback: keep the whole body minus the obvious header block.
            logger.warning("DECRETO marker not found; keeping body minus header block")
            for c in children:
                if getattr(c, "name", None) is None:
                    continue
                t = c.get_text(" ", strip=True)
                if "Subchefia para Assuntos" in t and "Presid" in t:
                    continue
                container.append(c.extract())
        else:
            for c in children[start_idx:]:
                if getattr(c, "name", None) is None:
                    txt = str(c).strip()
                    if txt:
                        p = soup.new_tag("p")
                        p.string = txt
                        container.append(p)
                    continue
                t = c.get_text(" ", strip=True)
                # Drop the download-anchor footer line.
                if t.lower().startswith("download para anexo"):
                    continue
                container.append(c.extract())

        text_len = len(container.get_text(strip=True))
        if text_len < 50:
            logger.warning(f"Extracted decree content too short ({text_len} chars)")
            return None
        return container

    def _filename(self, number: str, iso_date: Optional[str]) -> str:
        date_fmt = iso_date.replace("-", "") if iso_date else "nodate"
        stem = f"decreto_{_norm_number(number)}_{date_fmt}"
        filename = f"{stem}.docx"
        filepath = self.output_dir / filename
        counter = 1
        while filepath.exists():
            filepath = self.output_dir / f"{stem}_{counter}.docx"
            counter += 1
        return str(filepath)

    def fetch_one(self, number: str, iso_date: Optional[str],
                  year: Optional[int], title: str) -> DecreteFetchResult:
        try:
            url, needs_review = self.resolver.resolve(number, iso_date, year)
            if not url:
                return DecreteFetchResult(
                    number=number, date=iso_date, success=False,
                    error_message="Decree URL not found in index", needs_review=True,
                )
            resp = self.session.get(url, timeout=40, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = "iso-8859-1"
            content = self.extract_clean_content(resp.text)
            if content is None:
                return DecreteFetchResult(
                    number=number, date=iso_date, success=False, url=url,
                    error_message="Failed to extract clean content",
                    needs_review=needs_review,
                )
            # The extracted body already begins with the decree's own
            # "DECRETO Nº ..." title line, so adding the canonical title as a
            # heading would duplicate it. Pass the "Legal Document" sentinel so
            # create_document() skips the heading; still set the docx core
            # title property for metadata.
            doc = self.doc_builder.create_document(content, "Legal Document")
            doc.core_properties.title = (title or f"Decreto nº {number}")[:255]
            filepath = self._filename(number, iso_date)
            self.doc_builder.save_document(doc, filepath)
            return DecreteFetchResult(
                number=number, date=iso_date, success=True, url=url,
                filename=os.path.basename(filepath), needs_review=needs_review,
            )
        except Exception as e:
            logger.error(f"Error fetching decreto {number}: {e}")
            return DecreteFetchResult(
                number=number, date=iso_date, success=False,
                error_message=str(e), needs_review=iso_date is None,
            )

    def fetch_many(self, docs, show_progress: bool = True) -> List[DecreteFetchResult]:
        """Fetch a list of CanonicalDoc objects (must expose number/date/year/canonical_name)."""
        results = []
        try:
            from tqdm import tqdm
            iterator = tqdm(docs, desc="Fetching decretos") if show_progress else docs
        except ImportError:
            iterator = docs
        for i, d in enumerate(iterator):
            year = int(d.year) if getattr(d, "year", None) else None
            res = self.fetch_one(d.number, d.date, year, d.canonical_name)
            if res.success:
                logger.info(f"✓ decreto {d.number} -> {res.filename}")
            else:
                logger.error(f"✗ decreto {d.number} - {res.error_message}")
            results.append(res)
            if i < len(docs) - 1:
                time.sleep(self.delay)
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    # Quick self-test against a couple of known decrees.
    f = PlanaltoDecretoFetcher(output_dir="./output_decretos/documents")
    for num, iso, yr, title in [
        ("361", "1991-12-10", 1991, "Decreto nº 361, de 10 de dezembro de 1991"),
        ("52.288", "1963-07-24", 1963, "Decreto nº 52.288, de 24 de julho de 1963"),
    ]:
        print(f.fetch_one(num, iso, yr, title))
