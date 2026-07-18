#!/usr/bin/env python3
"""
Receita Federal Norm Fetcher (sijut2consulta)

Fetches Receita Federal acts — starting with "Instrução Normativa SRF" — from the
Receita norms portal (``normas.receita.fazenda.gov.br``) without a browser.

Why this is a separate path from ``br_legal_parser`` / ``planalto_decreto_fetcher``:
    normas.leg.br (``lei``, ``decreto_lei``) is a Shadow-DOM SPA needing Selenium;
    planalto (``decreto``) is static ISO-8859-1 HTML with index-driven URLs. The
    Receita portal is different again: a server-rendered Struts search form
    (``consulta.action``, GET) plus a **public JSON REST API** on a companion host
    (``normasinternet2.receita.fazenda.gov.br``). Both stages are reachable with
    plain ``requests``.

Two stages (both verified live against IN SRF nº 107/1988, idAto=14681):

  1. Search  -> ``GET /sijut2consulta/consulta.action`` with the full form field
     set -> server-rendered HTML listing -> scrape the internal act id
     (``link.action?idAto=NNNN``).
  2. Content -> ``GET normasinternet2/api/consulta-externa/ato/{idAto}/visao/{slug}``
     -> JSON: épigrafe (type/number/date/órgão for verification), ementa, and the
     full body as an ordered list of segments (``outrosSegmentos``).

Because the same number can exist for different years/órgãos (SRF was renamed RFB
in 2007) and genuine collisions exist (nº 84 in 1979 and 2001), a returned
``idAto`` is **always verified** against the canonical (órgão, number, date) using
the stage-2 JSON before it is accepted.

Generalization: only the ``(tipo_code, orgao_sigla)`` pair is act-type-specific.
``ActType`` captures that so the same fetcher serves ``instrucao_normativa_rfb``
and other RFB act types (ADE, ADI, Portaria, Solução de Consulta, …) that live in
the same ``sijut2consulta`` system.
"""

import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Reuse the docx builder from the sibling br_legal_parser project, for parity
# with the other pipelines (also emits raw JSON + plain text).
sys.path.append(os.path.join(os.path.dirname(__file__), "br_legal_parser"))
from legal_document_fetcher import WordDocumentBuilder  # noqa: E402

logger = logging.getLogger(__name__)

# Hosts.
SIJUT_BASE = "https://normas.receita.fazenda.gov.br/sijut2consulta"
CONSULTA_URL = SIJUT_BASE + "/consulta.action"
API_HOST = "https://normasinternet2.receita.fazenda.gov.br"
API_ATO = API_HOST + "/api/consulta-externa/ato"
# The API host's WAF/CORS returns 403 (empty) without a same-site Referer/Origin.
SITE_REFERER = API_HOST + "/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# View slugs to try, in order. ``original`` is the as-published text and was the
# available view for the test act; ``vigente``/``multivigente`` are the documented
# 406 fallbacks (the 406 message explicitly redirects to another view).
DEFAULT_VIEW_CHAIN = ("original", "vigente", "multivigente")

# ``link.action?idAto=NNNN`` and the ``?antigo=1&idAto=NNNN`` variant.
_IDATO_RE = re.compile(r"link\.action\?(?:antigo=1&(?:amp;)?)?idAto=(\d+)")


@dataclass
class ActType:
    """The act-type-specific parameters of a sijut2consulta search + verify.

    Only ``tipo_code`` and ``orgao_sigla`` truly vary between act types; the rest
    are labels/derived verification keys kept here so the fetcher stays generic.
    """
    type_slug: str        # canonical type_slug, e.g. "instrucao_normativa_srf"
    tipo_code: str        # "Tipo do ato" checkbox value, e.g. "42" (Instrução Normativa)
    tipo_label: str       # human label submitted as lblTiposAtosSelecionados
    tipo_sigla: str       # epigrafe.tipoAto.siglaTipoAto to verify, e.g. "IN"
    orgao_sigla: str      # epigrafe.orgaos[].siglaOrgao to verify, e.g. "SRF"
    file_prefix: str      # output filename stem prefix, e.g. "in_srf"


# Registry of supported act types. IN Conjunta uses code 79; RFB shares code 42.
ACT_TYPES: Dict[str, ActType] = {
    "instrucao_normativa_srf": ActType(
        type_slug="instrucao_normativa_srf", tipo_code="42",
        tipo_label="Instrução Normativa", tipo_sigla="IN",
        orgao_sigla="SRF", file_prefix="in_srf",
    ),
    "instrucao_normativa_rfb": ActType(
        type_slug="instrucao_normativa_rfb", tipo_code="42",
        tipo_label="Instrução Normativa", tipo_sigla="IN",
        orgao_sigla="RFB", file_prefix="in_rfb",
    ),
}


@dataclass
class ReceitaFetchResult:
    number: str
    date: Optional[str]
    success: bool
    id_ato: Optional[str] = None
    view: Optional[str] = None
    url: Optional[str] = None
    json_filename: str = ""
    text_filename: str = ""
    docx_filename: str = ""
    error_message: Optional[str] = None
    needs_review: bool = False
    review_reason: Optional[str] = None
    # Other idAtos that are republications (DOU retificações) of the chosen act,
    # kept for provenance when a republication group is collapsed to one file.
    alternate_id_atos: List[str] = field(default_factory=list)


def _norm_number(raw: str) -> str:
    """Digits only, dots/spaces stripped (e.g. '1.234' -> '1234')."""
    return re.sub(r"[.\s]", "", raw or "")


def extract_id_atos(html: str) -> List[str]:
    """Return the unique ``idAto`` values found in a consulta.action result page.

    Pure function (no network) so it can be unit-tested against a fixture. Order
    is preserved (first-seen), so the first search hit is tried first.
    """
    seen: "Dict[str, None]" = {}
    for m in _IDATO_RE.finditer(html or ""):
        seen.setdefault(m.group(1), None)
    return list(seen.keys())


def build_search_params(act: ActType, numero: str, year: Optional[int],
                        tipo_data: str = "1", page: int = 1) -> Dict[str, str]:
    """Build the full consulta.action GET field set.

    The search returns an empty body unless the *entire* field set is submitted;
    most fields are hidden and left empty. ``tipo_data`` selects which date the
    ``ano_ato`` filter applies to: "1" = data do ato (act date), "2" = publicação.
    """
    return {
        "facetsExistentes": "",
        "orgaosSelecionados": "",
        "tiposAtosSelecionados": act.tipo_code,
        "lblTiposAtosSelecionados": act.tipo_label,
        "ordemColuna": "",
        "ordemDirecao": "",
        "tipoConsulta": "formulario",
        "tipoAtoFacet": "",
        "siglaOrgaoFacet": "",
        "anoAtoFacet": "",
        "termoBusca": "",
        "numero_ato": _norm_number(numero),
        "tipoData": tipo_data,
        "ano_ato": str(year) if year else "",
        "p": str(page),
    }


class ReceitaNormaFetcher:
    """Search + verify + fetch Receita Federal acts from sijut2consulta."""

    def __init__(self, act: ActType, output_dir: str = "./output_instrucoes_normativas",
                 delay_between_requests: float = 1.5, save_docx: bool = True):
        self.act = act
        self.output_dir = Path(output_dir)
        self.documents_dir = self.output_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay_between_requests
        self.save_docx = save_docx
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self._warmed_up = False
        self.doc_builder = WordDocumentBuilder() if save_docx else None
        # idAto -> parsed JSON, to avoid refetching across retries/records.
        self._json_cache: Dict[str, dict] = {}

    # -- stage 1: search -----------------------------------------------------
    def _warm_up(self) -> None:
        """One GET to obtain the JSESSIONID cookie for /sijut2consulta."""
        if self._warmed_up:
            return
        try:
            self.session.get(CONSULTA_URL, timeout=40)
            self._warmed_up = True
        except requests.RequestException as e:
            logger.warning(f"Warm-up request failed: {e}")

    def search_ato(self, numero: str, year: Optional[int],
                   tipo_data: str = "1", page: int = 1) -> List[str]:
        """Run the search form and return candidate ``idAto`` values."""
        self._warm_up()
        params = build_search_params(self.act, numero, year, tipo_data, page)
        resp = self.session.get(
            CONSULTA_URL, params=params, timeout=40,
            headers={"Referer": CONSULTA_URL},
        )
        resp.raise_for_status()
        return extract_id_atos(resp.text)

    # -- stage 2: content ----------------------------------------------------
    def fetch_ato_json(self, id_ato: str,
                       view_chain=DEFAULT_VIEW_CHAIN) -> Optional[dict]:
        """Fetch the act JSON, trying each view in ``view_chain`` on 406.

        Returns the first available view's JSON (with the resolved ``_view`` slug
        recorded on it), or None if no view was available / access failed.
        """
        if id_ato in self._json_cache:
            return self._json_cache[id_ato]
        for view in view_chain:
            url = f"{API_ATO}/{id_ato}/visao/{view}"
            try:
                resp = self.session.get(
                    url, timeout=40,
                    headers={"Referer": SITE_REFERER, "Origin": API_HOST},
                )
            except requests.RequestException as e:
                logger.warning(f"idAto {id_ato} view {view}: request error {e}")
                return None
            if resp.status_code == 200:
                data = resp.json()
                data["_view"] = view
                data["_url"] = url
                self._json_cache[id_ato] = data
                return data
            if resp.status_code == 406:
                # This view is unavailable; the message directs to another view.
                logger.info(f"idAto {id_ato} view {view}: 406, trying next view")
                continue
            # 403 (WAF/invalid slug) or other — stop trying further views.
            logger.warning(f"idAto {id_ato} view {view}: HTTP {resp.status_code}")
            return None
        logger.warning(f"idAto {id_ato}: no view available in {view_chain}")
        return None

    # -- verification --------------------------------------------------------
    def verify(self, data: dict, number: str, expected_iso: Optional[str]) -> bool:
        """True iff the JSON matches the canonical (type, number, órgão, date).

        Requires all of: tipoAto.siglaTipoAto == act.tipo_sigla,
        numeroAto == number, some orgaos[].siglaOrgao == act.orgao_sigla, and
        dataAto == expected_iso (when a date is available to match on).
        """
        epi = (data or {}).get("epigrafe") or {}
        if (epi.get("tipoAto") or {}).get("siglaTipoAto") != self.act.tipo_sigla:
            return False
        if _norm_number(epi.get("numeroAto", "")) != _norm_number(number):
            return False
        orgaos = {o.get("siglaOrgao") for o in (epi.get("orgaos") or [])}
        if self.act.orgao_sigla not in orgaos:
            return False
        if expected_iso and epi.get("dataAto") != expected_iso:
            return False
        return True

    # -- republication selection ---------------------------------------------
    @staticmethod
    def _epigrafe_key(data: dict) -> tuple:
        """Identity key of an act: (tipo sigla, number, act date, órgão set).

        Two verified candidates that share this key are the *same act* published
        more than once in the DOU (an original followed by retificações), not
        distinct documents.
        """
        epi = (data or {}).get("epigrafe") or {}
        orgs = frozenset(o.get("siglaOrgao") for o in (epi.get("orgaos") or []))
        return (
            (epi.get("tipoAto") or {}).get("siglaTipoAto"),
            _norm_number(epi.get("numeroAto", "")),
            epi.get("dataAto"),
            orgs,
        )

    def _select_primary(self, matched: List[tuple]):
        """Choose the act to persist from the verified candidates.

        Returns ``(primary, alternates, ambiguous)``:
          * If all candidates are the same act (one épigrafe key), they are DOU
            republications; the **earliest published** one carries the full text
            (later ones are retificação excerpts), so it is chosen as primary and
            the rest returned as alternates. ``ambiguous`` is False.
          * If candidates carry different épigrafe keys (only possible for an
            undated canonical entry that matched several dates/órgãos), it is a
            genuine ambiguity: ``primary`` is None and ``ambiguous`` is True.
        """
        if len({self._epigrafe_key(d) for _, d in matched}) > 1:
            return None, [], True
        ordered = sorted(
            matched,
            key=lambda md: (md[1].get("dataPublicacao") or "9999-99-99", int(md[0])),
        )
        return ordered[0], ordered[1:], False

    # -- text reconstruction -------------------------------------------------
    @staticmethod
    def _segments_html(data: dict) -> str:
        """Concatenate épigrafe + ementa + body segments into an HTML fragment.

        Segments flagged ``omitir`` are skipped; the rest are emitted in
        ``ordemSegmentoAto`` order (falling back to list order). Each segment's
        ``textoIntegra`` may itself contain markup (e.g. <br>), preserved here so
        the docx builder renders structure; plain text is derived from this.
        """
        parts: List[str] = []
        completa = data.get("epigrafeCompleta")
        if completa:
            parts.append(f"<p><b>{completa}</b></p>")

        def emit(seglist):
            ordered = sorted(
                seglist or [],
                key=lambda s: s.get("ordemSegmentoAto") if s.get("ordemSegmentoAto") is not None else 0,
            )
            for s in ordered:
                if s.get("omitir"):
                    continue
                txt = (s.get("textoIntegra") or "").strip()
                if txt:
                    parts.append(f"<p>{txt}</p>")

        emit(data.get("ementas"))
        emit(data.get("outrosSegmentos"))
        return "\n".join(parts)

    @classmethod
    def reconstruct_text(cls, data: dict) -> str:
        """Plain-text reconstruction of the act (HTML stripped, blocks separated)."""
        soup = BeautifulSoup(cls._segments_html(data), "html.parser")
        blocks = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n\n".join(b for b in blocks if b)

    # -- persistence ---------------------------------------------------------
    def _stem(self, number: str, iso_date: Optional[str]) -> str:
        date_fmt = iso_date.replace("-", "") if iso_date else "nodate"
        return f"{self.act.file_prefix}_{_norm_number(number)}_{date_fmt}"

    def _persist(self, data: dict, number: str, iso_date: Optional[str],
                 title: str, result: ReceitaFetchResult) -> None:
        import json as _json
        stem = self._stem(number, iso_date)

        # Raw JSON (lossless) — strip our private _view/_url helper keys' echo is
        # fine to keep; they document provenance.
        json_path = self.documents_dir / f"{stem}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        result.json_filename = json_path.name

        # Plain text.
        text = self.reconstruct_text(data)
        text_path = self.documents_dir / f"{stem}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        result.text_filename = text_path.name

        # Optional docx for parity with the other pipelines.
        if self.save_docx and self.doc_builder is not None:
            soup = BeautifulSoup(self._segments_html(data), "html.parser")
            # The fragment already opens with the epígrafe as a bold line, so pass
            # the "Legal Document" sentinel to skip adding a duplicate heading.
            doc = self.doc_builder.create_document(soup, "Legal Document")
            doc.core_properties.title = (title or data.get("epigrafeCompleta") or stem)[:255]
            docx_path = self.documents_dir / f"{stem}.docx"
            self.doc_builder.save_document(doc, str(docx_path))
            result.docx_filename = docx_path.name

    # -- orchestration per record --------------------------------------------
    def fetch_one(self, number: str, iso_date: Optional[str], year: Optional[int],
                  title: str = "") -> ReceitaFetchResult:
        """Search, verify and persist a single canonical record."""
        result = ReceitaFetchResult(number=number, date=iso_date, success=False)
        try:
            # Collect candidate idAtos: by act date, then publicação date, then
            # number-only (last resort; verification still guards the match).
            candidates: List[str] = []
            attempts = []
            if year:
                attempts.append(("1", year))   # data do ato
                attempts.append(("2", year))   # data de publicação
            attempts.append(("1", None))       # number-only
            for tipo_data, yr in attempts:
                for cid in self.search_ato(number, yr, tipo_data=tipo_data):
                    if cid not in candidates:
                        candidates.append(cid)
                if candidates and yr is not None:
                    # Got hits for a year-scoped search; no need to widen further.
                    break

            if not candidates:
                result.needs_review = True
                result.review_reason = "not_found"
                result.error_message = "No idAto returned by search"
                return result

            # Verify each candidate; accept the first fully-matching act.
            matched: List[tuple] = []  # (id_ato, data)
            resolved_any = False       # at least one candidate returned a view
            for cid in candidates:
                data = self.fetch_ato_json(cid)
                if data is None:
                    continue
                resolved_any = True
                if self.verify(data, number, iso_date):
                    matched.append((cid, data))

            if matched:
                primary, alternates, ambiguous = self._select_primary(matched)
                if not ambiguous:
                    cid, data = primary
                    result.id_ato = cid
                    result.view = data.get("_view")
                    result.url = data.get("_url")
                    result.alternate_id_atos = [c for c, _ in alternates]
                    self._persist(data, number, iso_date, title, result)
                    result.success = True
                    if alternates:
                        # Same act, extra DOU republications collapsed to one file.
                        result.review_reason = "republication_selected"
                    # Undated canonical entries matched by number only stay flagged.
                    result.needs_review = iso_date is None
                    if result.needs_review:
                        result.review_reason = "matched_without_date"
                    return result

                # Genuine ambiguity (distinct acts) -> do not save; route to review.
                result.needs_review = True
                result.review_reason = "ambiguous"
                result.error_message = (
                    f"{len(matched)} distinct acts verified: "
                    f"{[c for c, _ in matched]}"
                )
                return result

            # Zero survivors -> do not save; route to review.
            result.needs_review = True
            if not resolved_any:
                result.review_reason = "only_view_unavailable"
                result.error_message = "No requested view available for any candidate"
            else:
                result.review_reason = "date_mismatch"
                result.error_message = (
                    f"{len(candidates)} candidate(s) found, none matched "
                    f"órgão={self.act.orgao_sigla}/number={number}/date={iso_date}"
                )
            return result

        except requests.RequestException as e:
            result.error_message = f"HTTP error: {e}"
            result.needs_review = True
            result.review_reason = "http_error"
            return result
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error fetching {self.act.type_slug} {number}: {e}")
            result.error_message = str(e)
            result.needs_review = True
            result.review_reason = "error"
            return result

    def fetch_many(self, docs, show_progress: bool = True) -> List[ReceitaFetchResult]:
        """Fetch a list of CanonicalDoc objects (number/date/year/canonical_name)."""
        results: List[ReceitaFetchResult] = []
        try:
            from tqdm import tqdm
            iterator = tqdm(docs, desc=f"Fetching {self.act.type_slug}") if show_progress else docs
        except ImportError:
            iterator = docs
        for i, d in enumerate(iterator):
            year = int(d.year) if getattr(d, "year", None) else None
            res = self.fetch_one(d.number, d.date, year, d.canonical_name)
            if res.success:
                logger.info(f"✓ {self.act.type_slug} {d.number} (idAto={res.id_ato}) "
                            f"-> {res.text_filename}")
            else:
                logger.error(f"✗ {self.act.type_slug} {d.number} - "
                             f"{res.review_reason}: {res.error_message}")
            results.append(res)
            if i < len(docs) - 1:
                time.sleep(self.delay)
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    # Quick self-test against the known IN SRF nº 107/1988 (idAto=14681).
    f = ReceitaNormaFetcher(ACT_TYPES["instrucao_normativa_srf"])
    r = f.fetch_one("107", "1988-07-14", 1988,
                    "Instrução Normativa SRF nº 107, de 14 de julho de 1988")
    print(r)
