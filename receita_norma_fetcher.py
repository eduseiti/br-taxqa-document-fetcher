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

Generalization: only the ``(tipo_code, orgao)`` pair is act-type-specific.
``ActType`` + the ``ACT_TYPES`` registry capture that, so the same fetcher serves
every Receita-portal act referenced by the canonical file — IN (SRF/RFB), Solução
de Consulta (Cosit), Ato Declaratório / Executivo / Interpretativo / Normativo,
Parecer Normativo, Portaria MF, Resolução CGSN, etc. — all in ``sijut2consulta``.
"""

import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

import receita_attachments
from receita_attachments import AttachmentClient
from receita_text_normalize import normalize_fragment, xml_safe

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

# View slugs to try, in order (406 = "this view is unavailable, use another").
#
# ``vigente`` — the law **as currently in force** — is the target, not
# ``original``. The API returns the same segment list in every view and varies
# only the per-segment flags, and the difference is not cosmetic:
#
#   * ``original`` carries **no ``ancorasDestino`` at all**, so every amendment
#     and revocation annotation is missing from it.
#   * its ``omitir`` mask is *inverted* relative to ``vigente``: for the 25 acts
#     in this corpus that have masked segments, rendering ``original`` publishes
#     the **superseded** wording and drops the current one (verified on IN SRF
#     nº 208/2002 segment 815178, whose v1/v2 masks swap between the views).
#   * ``vigente`` blanks individually-revoked provisions server-side, truncating
#     them to their label stub ("II -") and attaching the revocation annotation,
#     so no revoked wording can leak into the output.
#   * ``tachado`` (strikethrough) is set **only** in ``multivigente``, whose job
#     is to show every version at once. It is never rendered here.
#
# Caveat recorded in every artifact: ``vigente`` is a moving target — it is the
# law as of the fetch instant, which is why ``_fetched_at`` is stamped into the
# saved JSON and the fetch report.
DEFAULT_VIEW_CHAIN = ("vigente", "multivigente", "original")

# ``link.action?idAto=NNNN`` and the ``?antigo=1&idAto=NNNN`` variant.
_IDATO_RE = re.compile(r"link\.action\?(?:antigo=1&(?:amp;)?)?idAto=(\d+)")


@dataclass
class ActType:
    """The act-type-specific parameters of a sijut2consulta search + verify.

    Only ``tipo_code`` (the "Tipo do ato" code) and ``orgao`` (the órgão facet /
    verification sigla) truly vary between act types; the rest are labels kept
    here so the fetcher stays generic. ``orgao`` doubles as the ``orgaosSelecionados``
    search filter (narrows same-number/same-year collisions server-side) and the
    ``epigrafe.orgaos[].siglaOrgao`` verification key (compared case-insensitively,
    since the portal mixes casing: ``SRF``/``RFB``/``CST`` but ``Cosit``/``Codac``).
    ``orgao=None`` means "don't filter/verify by órgão" — for acts whose issuing
    unit is ambiguous or regional (e.g. a generic Parecer, or ``Disit/SRRF`` SCs).
    """
    type_slug: str          # canonical type_slug, e.g. "instrucao_normativa_srf"
    tipo_code: str          # "Tipo do ato" checkbox value, e.g. "42" (Instrução Normativa)
    tipo_label: str         # human label (also submitted as lblTiposAtosSelecionados)
    orgao: Optional[str]    # órgão facet value + verify sigla, e.g. "SRF"; None = any
    file_prefix: str        # output filename stem prefix, e.g. "in_srf"


# --- registry -------------------------------------------------------------
# Compact table: (type_slug, tipo_code, tipo_label, orgao, file_prefix).
# tipo codes + órgão siglas were reverse-engineered live from consulta.action
# (input.chkTiposAtos value/sigla) and verified against epigrafe.tipoAto.idTipoAto.
# "Ato Declaratório Comum" is the plain "Ato Declaratório" (code 7); the canonical
# suffix is the órgão. Entries with orgao=None match on tipo+number+date only.
_REGISTRY_TABLE = [
    # Instrução Normativa (42)
    ("instrucao_normativa_srf",             "42", "Instrução Normativa",            "SRF",   "in_srf"),
    ("instrucao_normativa_rfb",             "42", "Instrução Normativa",            "RFB",   "in_rfb"),
    # Solução de Consulta / Interna / Divergência (72/75/73)
    ("solucao_de_consulta_cosit",           "72", "Solução de Consulta",            "Cosit", "sc_cosit"),
    ("solucao_de_consulta_interna_cosit",   "75", "Solução de Consulta Interna",    "Cosit", "sci_cosit"),
    ("solucao_de_divergencia_cosit",        "73", "Solução de Divergência",         "Cosit", "sd_cosit"),
    ("solucao_de_consulta",                 "72", "Solução de Consulta",            None,    "sc"),
    # Ato Declaratório "Comum" = AD (7)
    ("ato_declaratorio_comum_pgfn",         "7",  "Ato Declaratório",               "PGFN",  "ad_pgfn"),
    ("ato_declaratorio_comum_srf",          "7",  "Ato Declaratório",               "SRF",   "ad_srf"),
    ("ato_declaratorio_comum_cosit",        "7",  "Ato Declaratório",               "Cosit", "ad_cosit"),
    ("ato_declaratorio_comum_cosar",        "7",  "Ato Declaratório",               "Cosar", "ad_cosar"),
    # Ato Declaratório Executivo (9)
    ("ato_declaratorio_executivo_rfb",      "9",  "Ato Declaratório Executivo",     "RFB",   "ade_rfb"),
    ("ato_declaratorio_executivo_srf",      "9",  "Ato Declaratório Executivo",     "SRF",   "ade_srf"),
    ("ato_declaratorio_executivo_cosit",    "9",  "Ato Declaratório Executivo",     "Cosit", "ade_cosit"),
    ("ato_declaratorio_executivo_codac",    "9",  "Ato Declaratório Executivo",     "Codac", "ade_codac"),
    # Ato Declaratório Interpretativo (10)
    ("ato_declaratorio_interpretativo_srf", "10", "Ato Declaratório Interpretativo", "SRF",  "adi_srf"),
    ("ato_declaratorio_interpretativo_rfb", "10", "Ato Declaratório Interpretativo", "RFB",  "adi_rfb"),
    # Ato Declaratório Normativo (11)
    ("ato_declaratorio_normativo_cst",      "11", "Ato Declaratório Normativo",     "CST",   "adn_cst"),
    ("ato_declaratorio_normativo_cosit",    "11", "Ato Declaratório Normativo",     "Cosit", "adn_cosit"),
    # Parecer Normativo (59) / Parecer (61)
    ("parecer_normativo_cst",               "59", "Parecer Normativo",              "CST",   "pn_cst"),
    ("parecer_normativo_cosit",             "59", "Parecer Normativo",              "Cosit", "pn_cosit"),
    ("parecer_normativo",                   "59", "Parecer Normativo",              None,    "pn"),
    ("parecer_cosit",                       "61", "Parecer",                        "Cosit", "par_cosit"),
    ("parecer_pgfn",                        "61", "Parecer",                        "PGFN",  "par_pgfn"),
    ("parecer_pgfncat",                     "61", "Parecer",                        None,    "par_pgfncat"),
    ("parecer_sei",                         "61", "Parecer",                        None,    "par_sei"),
    ("parecer",                             "61", "Parecer",                        None,    "par"),
    # Nota (77)
    ("nota_pgfn",                           "77", "Nota",                           "PGFN",  "nota_pgfn"),
    ("nota_sei",                            "77", "Nota",                           None,    "nota_sei"),
    # Portaria (57), Resolução (67), Despacho (35)
    ("portaria_mf",                         "57", "Portaria",                       "MF",    "port_mf"),
    ("resolucao_cgsn",                      "67", "Resolução",                      "CGSN",  "resol_cgsn"),
    ("despacho",                            "35", "Despacho",                       None,    "desp"),
]

ACT_TYPES: Dict[str, ActType] = {
    slug: ActType(type_slug=slug, tipo_code=code, tipo_label=label,
                  orgao=orgao, file_prefix=prefix)
    for slug, code, label, orgao, prefix in _REGISTRY_TABLE
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
    # Provenance + rendering telemetry. ``vigente`` reflects the law as of
    # ``fetched_at``, so the corpus is only reproducible with that stamp;
    # ``exibir_visoes`` records which views the act offered, making any act that
    # fell back off ``vigente`` visible in the report.
    fetched_at: Optional[str] = None
    exibir_visoes: Optional[str] = None
    data_vigencia_inicio: Optional[str] = None
    act_revoked: bool = False
    render_stats: dict = field(default_factory=dict)
    original_json_filename: str = ""   # only with --also-save-original


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
        # Filtering by órgão narrows same-number/same-year collisions across órgãos
        # server-side (e.g. AD nº 22/1997 exists for SRF, Cosar and Cosit). Empty
        # when the act type has no fixed órgão (orgao=None).
        "orgaosSelecionados": act.orgao or "",
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
                 delay_between_requests: float = 1.5, save_docx: bool = True,
                 view_chain=DEFAULT_VIEW_CHAIN, fetch_attachments: bool = True,
                 attachment_cache_dir: str = "./.attachment_cache",
                 also_save_original: bool = False):
        self.act = act
        self.output_dir = Path(output_dir)
        self.documents_dir = self.output_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay_between_requests
        self.save_docx = save_docx
        self.view_chain = tuple(view_chain)
        self.also_save_original = also_save_original
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self._warmed_up = False
        self.doc_builder = WordDocumentBuilder() if save_docx else None
        # idAto -> parsed JSON, to avoid refetching across retries/records.
        self._json_cache: Dict[str, dict] = {}
        # Raw attachment bytes are kept next to the documents so nothing is lost
        # when a converter fails or is unavailable (e.g. legacy .doc annexes).
        self.attachments_dir = self.documents_dir / "attachments"
        self.attachment_client = (
            AttachmentClient(self.session, cache_dir=attachment_cache_dir,
                             delay=min(delay_between_requests, 1.0))
            if fetch_attachments else None
        )

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
    def fetch_ato_json(self, id_ato: str, view_chain=None) -> Optional[dict]:
        """Fetch the act JSON, trying each view in ``view_chain`` on 406.

        Returns the first available view's JSON (with the resolved ``_view`` slug
        recorded on it), or None if no view was available / access failed.
        ``verify()`` reads only the épigrafe, which is view-invariant, so the
        chosen view never affects matching or republication selection.
        """
        if id_ato in self._json_cache:
            return self._json_cache[id_ato]
        view_chain = self.view_chain if view_chain is None else tuple(view_chain)
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

    def _fetch_single_view(self, id_ato: str, view: str) -> Optional[dict]:
        """Fetch exactly one view, bypassing the chain and the cache.

        Used by ``--also-save-original``: the cache holds the rendered view, and
        a 406 here means "this act has no such view", not "try another".
        """
        url = f"{API_ATO}/{id_ato}/visao/{view}"
        try:
            resp = self.session.get(
                url, timeout=40,
                headers={"Referer": SITE_REFERER, "Origin": API_HOST},
            )
        except requests.RequestException as e:
            logger.warning(f"idAto {id_ato} view {view}: request error {e}")
            return None
        if resp.status_code != 200:
            logger.info(f"idAto {id_ato} view {view}: HTTP {resp.status_code}")
            return None
        data = resp.json()
        data["_view"] = view
        data["_url"] = url
        return data

    # -- verification --------------------------------------------------------
    def verify(self, data: dict, number: str, expected_iso: Optional[str]) -> bool:
        """True iff the JSON matches the canonical (type, number, órgão, date).

        Requires all of: tipoAto.idTipoAto == act.tipo_code (numeric — robust to
        the punctuated siglas like "Parec. Norm."), numeroAto == number, some
        orgaos[].siglaOrgao == act.orgao (case-insensitive; skipped when the act
        type has no fixed órgão), and dataAto == expected_iso (when a date is
        available to match on).
        """
        epi = (data or {}).get("epigrafe") or {}
        if str((epi.get("tipoAto") or {}).get("idTipoAto")) != str(self.act.tipo_code):
            return False
        if _norm_number(epi.get("numeroAto", "")) != _norm_number(number):
            return False
        if self.act.orgao is not None:
            orgaos = {(o.get("siglaOrgao") or "").casefold()
                      for o in (epi.get("orgaos") or [])}
            if self.act.orgao.casefold() not in orgaos:
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

    # -- rendering -----------------------------------------------------------
    @classmethod
    def _segments_html(cls, data: dict, client: Optional[AttachmentClient] = None,
                       attachments_dir: Optional[Path] = None, stem: str = "",
                       stats: Optional[dict] = None) -> str:
        """Build a **block-structured** HTML fragment for one act.

        This mirrors the portal's own Angular renderer rather than inventing a
        presentation, so the artifact matches what a human sees at
        ``sijut2consulta/link.action?idAto=…``::

            this.segmentos = visaoAto.outrosSegmentos.filter(seg => seg.omitir === false)
            ngIf(text)       = (idTipoSegmento !== 16 || !arquivoBinario) && !omitir
            ngIf(attachment) = arquivoBinario && !isAnotacao() && !omitir
            if (segmento.tachado) classes += ' tachado'      // .tachado { line-through }

        Consequences, all deliberate:

        * ``omitir`` is the view's own "do not render" mask and is honored as-is.
          Against the ``vigente`` view it masks **superseded** wording; against
          ``original`` it masks the *current* wording — which is why the view
          matters far more than the filter (see ``DEFAULT_VIEW_CHAIN``).
        * ``ancorasDestino[].texto`` carries the amendment/revocation annotation
          ("Redação dada pelo(a) …", "Revogado(a) pelo(a) …"). It is emitted as
          an italic annotation paragraph right after its segment.
        * **No strikethrough is ever emitted.** ``tachado`` is set only in
          ``multivigente``; when that view is reached as a fallback its struck
          segments are dropped instead, so no document ever mixes superseded and
          current wording.
        * An *anexo* segment carrying a binary renders the **attachment** and its
          flattened ``textoIntegra`` is dropped, exactly as the portal does. If
          conversion fails, the flattened text is kept as a fallback so content
          never regresses.

        Unlike before, output is a list of **block-level siblings** (``<p>`` and
        ``<table>``), never ``<p>``-wrapped tables — ``add_html_content`` only
        dispatches ``table`` at the top level, so the old flat-``<p>`` emission
        made a real Word table structurally unreachable.
        """
        parts: List[str] = []
        st = stats if stats is not None else {}
        st.setdefault("segments_rendered", 0)
        st.setdefault("segments_omitted", 0)
        st.setdefault("segments_struck_dropped", 0)
        st.setdefault("annotations", 0)
        st.setdefault("attachments", 0)
        st.setdefault("attachment_tables", 0)
        st.setdefault("attachments_failed", 0)
        st.setdefault("attachment_details", [])

        # ``multivigente`` is the only view that sets ``tachado``; if the chain
        # fell back to it, drop struck segments so this act does not become the
        # one document carrying superseded wording.
        drop_struck = data.get("_view") == "multivigente"

        completa = data.get("epigrafeCompleta")
        if completa:
            parts.append(f"<p><b>{normalize_fragment(completa)}</b></p>")

        # Whole-act revocation is not a segment flag: it lives in the document
        # header (``vigente: false`` + ``ancorasNoAto``). Without this banner a
        # fully revoked act reads as if it were still in force.
        if data.get("vigente") is False or data.get("ancorasNoAto"):
            for anchor in data.get("ancorasNoAto") or []:
                texto = (anchor.get("texto") or "").strip()
                if texto:
                    parts.append(f'<p class="anotacao"><i>{normalize_fragment(texto)}</i></p>')
                    st["annotations"] += 1

        def emit(seglist):
            ordered = sorted(
                seglist or [],
                key=lambda s: s.get("ordemSegmentoAto") if s.get("ordemSegmentoAto") is not None else 0,
            )
            for s in ordered:
                if s.get("omitir"):
                    st["segments_omitted"] += 1
                    continue
                if drop_struck and s.get("tachado"):
                    st["segments_struck_dropped"] += 1
                    continue

                binario = s.get("arquivoBinario")
                rendered_attachment = False
                if binario:
                    st["attachments"] += 1
                    att = receita_attachments.retrieve(
                        binario, data.get("idAto"), client, attachments_dir, stem)
                    st["attachment_details"].append({
                        "id_arquivo": att.id_arquivo, "kind": att.kind,
                        "name": att.name, "size": att.size, "saved_as": att.saved_as,
                        "n_tables": att.n_tables, "converted": att.converted,
                        "source": att.source, "error": att.error,
                    })
                    if att.html:
                        # Annex text needs the same ordinal normalization as the
                        # segment text: these are the *same* acts, typed in the
                        # same era, and a scanned PDF annex is if anything richer
                        # in legacy encodings ("Art. 3°, §§ 1° e 4°"). Normalizing
                        # only textoIntegra left 173 of them in the corpus.
                        parts.append(normalize_fragment(att.html))
                        st["attachment_tables"] += att.n_tables
                        rendered_attachment = True
                    else:
                        st["attachments_failed"] += 1

                # The portal suppresses textoIntegra for an anexo segment whose
                # attachment rendered; keep it only as a conversion fallback.
                rendered_text = False
                if not rendered_attachment:
                    txt = (s.get("textoIntegra") or "").strip()
                    if txt:
                        parts.append(f"<p>{normalize_fragment(txt)}</p>")
                        rendered_text = True

                # A segment counts as rendered when it actually produced output.
                # Segments that produce nothing at all are the future-dated ones
                # (empty text, annotation only), which are counted as annotations.
                if rendered_attachment or rendered_text:
                    st["segments_rendered"] += 1

                for anchor in s.get("ancorasDestino") or []:
                    texto = (anchor.get("texto") or "").strip()
                    if texto:
                        parts.append(
                            f'<p class="anotacao"><i>{normalize_fragment(texto)}</i></p>')
                        st["annotations"] += 1

        emit(data.get("ementas"))
        emit(data.get("outrosSegmentos"))
        # One sanitizing pass over the assembled fragment. This is the single
        # choke point every source flows through — segment text, inline HTML
        # annexes and PDF/ODS conversions alike — and it must happen: a single
        # XML-illegal character (PyMuPDF renders an unmapped PDF bullet glyph as
        # U+0001) makes python-docx refuse the whole document, which previously
        # cost the entire act rather than one stray glyph.
        return xml_safe("\n".join(parts))

    @staticmethod
    def fragment_to_text(html: str) -> str:
        """Flatten a rendered fragment to plain text, in document order.

        The previous implementation was ``soup.find_all('p')``, which silently
        dropped every ``<table>`` — the ``.txt`` is the artifact most likely to
        feed a RAG index, so a walk in document order matters more here than in
        the ``.docx``. Tables become pipe-delimited rows (one line per row) so
        the row/column association survives flattening.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        blocks: List[str] = []

        for element in soup.children:
            if element.name == "table":
                lines = []
                for row in element.find_all("tr"):
                    cells = [" ".join(c.get_text(" ", strip=True).split())
                             for c in row.find_all(["td", "th"])]
                    if any(cells):
                        lines.append(" | ".join(cells))
                if lines:
                    blocks.append("\n".join(lines))
            elif element.name is None:
                text = " ".join(str(element).split())
                if text:
                    blocks.append(text)
            else:
                if element.find("img") and not element.get_text(strip=True):
                    blocks.append("[imagem]")
                    continue
                # <br> must survive as a newline, not be squashed into a space.
                for br in element.find_all("br"):
                    br.replace_with("\n")
                text = element.get_text(" ")
                text = "\n".join(" ".join(line.split()) for line in text.split("\n"))
                text = "\n".join(line for line in text.split("\n") if line)
                if text:
                    blocks.append(text)

        return "\n\n".join(blocks)

    @classmethod
    def reconstruct_text(cls, data: dict) -> str:
        """Plain-text reconstruction of an act from its saved JSON.

        Pure (no network): by-reference attachments are skipped, inline ones are
        still converted. ``_persist`` uses the attachment-aware path instead.
        """
        return cls.fragment_to_text(cls._segments_html(data))

    # -- persistence ---------------------------------------------------------
    def _stem(self, number: str, iso_date: Optional[str]) -> str:
        date_fmt = iso_date.replace("-", "") if iso_date else "nodate"
        return f"{self.act.file_prefix}_{_norm_number(number)}_{date_fmt}"

    def _persist(self, data: dict, number: str, iso_date: Optional[str],
                 title: str, result: ReceitaFetchResult) -> None:
        import json as _json
        stem = self._stem(number, iso_date)

        # Raw JSON (lossless) — strip our private _view/_url helper keys' echo is
        # fine to keep; they document provenance. ``vigente`` is a moving target
        # (it reflects the law as of *now*), so the corpus is only reproducible
        # if the fetch instant is recorded alongside it.
        data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
        json_path = self.documents_dir / f"{stem}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        result.json_filename = json_path.name

        # Optional second GET keeping the as-published text alongside the
        # in-force one. Off by default: the switch to ``vigente`` changes the
        # legal meaning of the corpus, and some consumers still want the
        # original wording for provenance.
        if self.also_save_original and data.get("_view") != "original":
            original = self._fetch_single_view(str(data.get("idAto")), "original")
            if original is not None:
                original["_fetched_at"] = data["_fetched_at"]
                with open(self.documents_dir / f"{stem}.original.json", "w",
                          encoding="utf-8") as f:
                    _json.dump(original, f, ensure_ascii=False, indent=2)
                result.original_json_filename = f"{stem}.original.json"

        # Render once, with attachments, and derive both artifacts from it — the
        # .txt and .docx must never disagree about what the document contains.
        stats: dict = {}
        fragment = self._segments_html(
            data, client=self.attachment_client,
            attachments_dir=self.attachments_dir, stem=stem, stats=stats,
        )
        result.render_stats = stats
        result.fetched_at = data["_fetched_at"]
        result.exibir_visoes = data.get("exibirVisoes")
        result.data_vigencia_inicio = data.get("dataVigenciaInicio")
        result.act_revoked = data.get("vigente") is False

        # Plain text.
        text = self.fragment_to_text(fragment)
        text_path = self.documents_dir / f"{stem}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        result.text_filename = text_path.name

        # Optional docx for parity with the other pipelines.
        if self.save_docx and self.doc_builder is not None:
            soup = BeautifulSoup(fragment, "html.parser")
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
                    f"órgão={self.act.orgao}/number={number}/date={iso_date}"
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
