#!/usr/bin/env python3
"""
Typographic normalization for Receita Federal act text (ordinals, <strike>).

The sijut2consulta API returns ``textoIntegra`` exactly as it was keyed in over
the decades, so the same ordinal indicator appears in four encodings:

    art. 1o        bare 'o'  (pre-Unicode typing)         -> art. 1º
    Lei No 9.250   'No' as the abbreviation of "número"   -> Lei nº 9.250
    art. 3°        DEGREE SIGN U+00B0 instead of U+00BA   -> art. 3º
    art. 1<strike>º</strike>  the portal's own underline hack -> art. 1º

Only the rendered ``.txt``/``.docx`` are normalized; the saved ``.json`` stays a
byte-faithful mirror of the API, so any rule here can be revisited without
re-fetching.

Two facts measured over the 245-act corpus drive the rules:

  * **The digit look-ahead is a complete discriminator for ``No``.** All 78
    ``No``+digit occurrences are the abbreviation (``Lei No 9.250``,
    ``Portaria MF No 227``); all 336 ``No``+word occurrences are the preposition
    (``No caso de …``), which must never be touched.
  * **Every bare ``<digit>o`` / ``<digit>a`` in the corpus is a genuine ordinal**
    (157 occurrences, no counter-example). An earlier design gated the rewrite on
    a preceding context token (``art``/``§``/``inciso``/…); measured against the
    corpus that gate *missed* 16 real ordinals whose left neighbour is a
    conjunction or preposition (``arts. 5o e 6o``, ``1o de janeiro``,
    ``§§ 2o e 3o``, ``13a Edição``, ``1a) - realizá-las``) while rejecting
    nothing. So the anchoring is purely lexical, and every rewrite is instead
    *logged* — ``--audit-ordinals`` prints them with context, so a future
    non-ordinal use surfaces in review rather than silently changing text.

``<strike>`` is **always unwrapped, never rendered as strikethrough**: all 366
occurrences in this corpus wrap an ordinal indicator (``<strike>º</strike>``),
and the target rendering (the portal's ``vigente`` view) contains no struck text
at all. This rule is deliberately Receita-side only — planalto *does* use
``<strike>`` for genuinely revoked provisions, so it must not leak into the
shared ``WordDocumentBuilder``.

Usage:
    python receita_text_normalize.py --audit-ordinals            # whole corpus
    python receita_text_normalize.py --audit-ordinals --only instrucao_normativa_srf
"""

import re
import warnings
from dataclasses import dataclass
from typing import Iterator, List, Tuple

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning, NavigableString

# Segment fragments are often a bare sentence; bs4 mistakes short tag-free
# strings containing a path-like token for filenames and warns on every one.
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

__all__ = [
    "normalize_text",
    "normalize_fragment",
    "iter_rewrites",
    "xml_safe",
    "Rewrite",
    "ORDINAL_CHARS",
]

# Characters that are illegal in XML 1.0 and therefore rejected outright by
# python-docx/lxml ("All strings must be XML compatible"). They reach us from
# PDF annexes: PyMuPDF maps a glyph it cannot resolve to a code point in this
# range — a list bullet in a symbol font typically arrives as U+0001. One such
# character used to abort an entire act, so it is stripped at assembly time.
_XML_ILLEGAL = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f﷐-﷯￾￿]"
)


def xml_safe(text: str) -> str:
    """Drop characters that XML 1.0 forbids, leaving all real content intact.

    The removed code points carry no textual meaning (they are unmapped glyphs,
    not letters), so dropping them loses nothing a reader would see — whereas
    keeping even one makes the ``.docx`` unwritable.
    """
    if not text:
        return text
    return _XML_ILLEGAL.sub("", text)

# Characters a <strike> may legitimately wrap in this corpus: the ordinal
# indicators themselves. Anything else is unwrapped *and* reported.
ORDINAL_CHARS = {"º", "ª", "o", "a", "°"}

# --- rules ------------------------------------------------------------------
# Each rule is (name, compiled pattern, replacement). Order matters: the "n°"
# rule must run before the degree-sign rule so that "Lei n° 8.864" becomes
# "Lei nº 8.864" rather than being left with a bare degree sign.

_RULES: List[Tuple[str, "re.Pattern", str]] = [
    # 1. "No"/"Nos"/"N°" as the abbreviation of "número". The digit look-ahead is
    #    what separates it from the preposition "No caso de …" (336 corpus hits
    #    that must survive untouched). Trailing whitespace before the number is
    #    preserved by the look-ahead so "Lei No8.864" is not reflowed.
    ("num_abbrev_plural", re.compile(r"(?<![\w])N[oO][sS](?=\s*\d)"), "nºs"),
    ("num_abbrev", re.compile(r"(?<![\w])N[oO]\.?(?=\s*\d)"), "nº"),
    # 2. "n°" / "N°" — degree sign standing in for the ordinal indicator after
    #    the "número" abbreviation ("IN SRF n°93", "Leis n°s9.317").
    ("num_degree_plural", re.compile(r"(?<![\w])[nN]\s*°\s*[sS](?=\s*\d)"), "nºs"),
    ("num_degree", re.compile(r"(?<![\w])[nN]\s*°(?=\s*\d)"), "nº"),
    # 3. Bare ASCII ordinals. Two digits max: the corpus tops out at "19a.Seção"
    #    and Brazilian legal usage only writes ordinal indicators up to 9º/10º.
    #    The (?<![\w.]) look-behind keeps the rule out of years, monetary values
    #    ("R$ 20.000,00") and identifiers.
    ("ordinal_masc", re.compile(r"(?<![\w.])(\d{1,2})o\b"), r"\1º"),
    ("ordinal_fem", re.compile(r"(?<![\w.])(\d{1,2})a\b"), r"\1ª"),
    # 4. Remaining degree signs directly after a digit ("art. 3°", "13° salário").
    ("degree_after_digit", re.compile(r"(?<=\d)\s*°"), "º"),
]


@dataclass
class Rewrite:
    """One normalization hit, for ``--audit-ordinals`` and reporting."""
    rule: str
    before: str
    after: str
    context: str


def _apply_rules(text: str, sink: "List[Rewrite] | None" = None) -> str:
    """Run every rule over a plain-text string, optionally recording each hit."""
    for name, pattern, repl in _RULES:
        if sink is None:
            text = pattern.sub(repl, text)
            continue

        # Recording variant: capture 40 chars of context around each rewrite.
        def _record(m: "re.Match") -> str:
            new = m.expand(repl)
            start, end = m.start(), m.end()
            sink.append(Rewrite(
                rule=name,
                before=m.group(0),
                after=new,
                context=" ".join(text[max(0, start - 40):end + 20].split()),
            ))
            return new

        text = pattern.sub(_record, text)
    return text


def normalize_text(text: str, sink: "List[Rewrite] | None" = None) -> str:
    """Normalize ordinals in a plain-text (already tag-free) string."""
    if not text:
        return text
    return _apply_rules(text, sink)


def _unwrap_strikes(soup: BeautifulSoup, sink: "List[Rewrite] | None" = None) -> None:
    """Replace every <strike>/<s>/<del> with its plain text content.

    Never emits strikethrough. Content that is not an ordinal indicator is
    unwrapped too, but recorded as a ``strike_non_ordinal`` rewrite so a future
    genuine use of the tag shows up in the audit instead of vanishing silently.
    """
    for tag in soup.find_all(["strike", "s", "del"]):
        inner = tag.get_text()
        if sink is not None and inner.strip() not in ORDINAL_CHARS:
            sink.append(Rewrite(
                rule="strike_non_ordinal",
                before=str(tag)[:80],
                after=inner[:80],
                context=" ".join(inner.split())[:80],
            ))
        tag.unwrap()


def normalize_fragment(html: str, sink: "List[Rewrite] | None" = None) -> str:
    """Normalize an HTML fragment: unwrap <strike>, then fix ordinals in text.

    Rules are applied to **text nodes only**, so tag names, ``href`` targets and
    other attribute values can never be rewritten. ``<strike>`` unwrapping runs
    first, so ``1<strike>º</strike>`` is already ``1º`` and no ordinal rule sees
    a split token.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    _unwrap_strikes(soup, sink)
    # Merge adjacent text nodes left behind by unwrap() so a rewrite is never
    # split across two NavigableStrings (e.g. "art. 1" + "º" + " Fica…").
    soup.smooth()
    for node in list(soup.find_all(string=True)):
        new = _apply_rules(str(node), sink)
        if new != str(node):
            node.replace_with(NavigableString(new))
    return str(soup)


def iter_rewrites(html: str) -> Iterator[Rewrite]:
    """Yield every rewrite ``normalize_fragment`` would make (audit helper)."""
    sink: List[Rewrite] = []
    normalize_fragment(html, sink)
    return iter(sink)


# --- audit CLI --------------------------------------------------------------
def _audit(corpus_glob: str, only: "str | None") -> int:
    """Print every rewrite the rules make over the saved corpus, with context."""
    import collections
    import glob
    import json

    pattern = corpus_glob if not only else corpus_glob.replace("*/documents", f"{only}/documents")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No corpus files matched {pattern}")
        return 1

    by_rule: "collections.Counter[str]" = collections.Counter()
    files_by_rule: "collections.defaultdict[str, set]" = collections.defaultdict(set)
    samples: "collections.defaultdict[str, list]" = collections.defaultdict(list)

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("ementas", "outrosSegmentos"):
            for seg in data.get(key) or []:
                for rw in iter_rewrites(seg.get("textoIntegra") or ""):
                    by_rule[rw.rule] += 1
                    files_by_rule[rw.rule].add(path)
                    samples[rw.rule].append((path.split("/")[-1], rw))

    print(f"Audited {len(files)} act(s)\n")
    print(f"{'rule':<22} {'hits':>6} {'files':>6}")
    print("-" * 36)
    for rule, n in by_rule.most_common():
        print(f"{rule:<22} {n:>6} {len(files_by_rule[rule]):>6}")

    for rule, _ in by_rule.most_common():
        print(f"\n=== {rule} ===")
        seen = set()
        for name, rw in samples[rule]:
            key = rw.context
            if key in seen:
                continue
            seen.add(key)
            print(f"  {name[:30]:<32} {rw.before!r} -> {rw.after!r}   | {rw.context}")
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--audit-ordinals", action="store_true",
                        help="Print every rewrite over the saved corpus, with context")
    parser.add_argument("--only", default=None, help="Restrict the audit to one type_slug")
    parser.add_argument("--corpus", default="output_receita_federal/*/documents/*.json",
                        help="Glob of saved act JSONs to audit")
    args = parser.parse_args()

    if args.audit_ordinals:
        return _audit(args.corpus, args.only)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
