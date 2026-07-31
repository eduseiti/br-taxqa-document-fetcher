# Receita Federal — Single-Folder `.docx` Aggregation via Symlinks

**Executed:** 2026-07-31 21:05:11 (local time, from `date +%Y%m%d_%H%M%S`)
**Scope:** `output_receita_federal/`

## Goal

Provide one flat directory from which every `.docx` produced by the Receita
Federal fetching pipeline can be accessed, without duplicating bytes and without
disturbing the existing per-act-type layout
(`output_receita_federal/<type_slug>/documents/`).

## What was done

Created `output_receita_federal/documents/` and populated it with **244
relative soft links**, one per `.docx` found under the per-type `documents/`
subfolders.

Link form (relative, so the tree stays portable / movable as a whole):

```
output_receita_federal/documents/in_rfb_1008_20100209.docx
    -> ../instrucao_normativa_rfb/documents/in_rfb_1008_20100209.docx
```

### Command executed

```bash
R=output_receita_federal
mkdir -p "$R/documents"
while IFS= read -r f; do
  rel="${f#./}"
  ln -sfn "../$rel" "$R/documents/$(basename "$rel")"
done < <(cd "$R" && find . -mindepth 3 -name "*.docx" -not -path "./documents/*" | sort)
```

Notes on the traversal:

- `-mindepth 3` plus `-not -path "./documents/*"` keeps the new aggregation
  folder out of its own source set (it sits at depth 2), so re-running is safe.
- `ln -sfn` makes the operation **idempotent**: re-running after a new fetch
  refreshes existing links and adds the new ones. Stale links pointing at
  deleted acts are *not* removed by a re-run — see "Maintenance" below.
- `documents/attachments/` holds raw annexes (pdf/doc/htm/ods/jpg) and contains
  no `.docx`; verified: `find . -path "*attachments*" -name "*.docx"` → 0 hits.
  So no annex file is shadowed by, or competes with, an act `.docx`.

## Verification

| Check | Result |
| --- | --- |
| `.docx` files under per-type folders | 244 |
| Entries created in `output_receita_federal/documents/` | 244 |
| Links resolving to an existing regular file (`find -type l -xtype f`) | 244 |
| Duplicate basenames across type folders (`uniq -d`) | 0 |

The zero-collision result is what makes a flat folder viable: the fetcher's
filename convention already encodes act type, órgão, number and date
(e.g. `ad_cosar_47_20001127.docx`, `in_rfb_1008_20100209.docx`), so basenames
are globally unique across the corpus.

## Source distribution (244 files)

| Act type folder | Files |
| --- | ---: |
| `solucao_de_consulta_cosit` | 109 |
| `instrucao_normativa_rfb` | 22 |
| `parecer_normativo_cst` | 15 |
| `instrucao_normativa_srf` | 14 |
| `ato_declaratorio_comum_pgfn` | 14 |
| `solucao_de_consulta_interna_cosit` | 12 |
| `ato_declaratorio_interpretativo_srf` | 9 |
| `parecer_normativo_cosit` | 7 |
| `ato_declaratorio_comum_srf` | 7 |
| `ato_declaratorio_normativo_cosit` | 6 |
| `ato_declaratorio_normativo_cst` | 5 |
| `solucao_de_divergencia_cosit` | 3 |
| `portaria_mf` | 3 |
| `ato_declaratorio_interpretativo_rfb` | 3 |
| `solucao_de_consulta` | 2 |
| `nota_pgfn` | 2 |
| `ato_declaratorio_executivo_rfb` | 2 |
| `resolucao_cgsn` | 1 |
| `parecer_pgfn` | 1 |
| `parecer_cosit` | 1 |
| `despacho` | 1 |
| `ato_declaratorio_executivo_srf` | 1 |
| `ato_declaratorio_executivo_cosit` | 1 |
| `ato_declaratorio_executivo_codac` | 1 |
| `ato_declaratorio_comum_cosit` | 1 |
| `ato_declaratorio_comum_cosar` | 1 |
| **Total** | **244** |

Five act-type folders contributed zero files — no act was successfully fetched
for them (entries deferred to `needs_review.json`): `nota_sei`, `parecer`,
`parecer_normativo`, `parecer_pgfncat`, `parecer_sei`.

## Maintenance

- **After a new fetch run:** re-run the command above; it adds links for new
  `.docx` and refreshes existing ones.
- **After deleting/renaming acts:** prune broken links first, then re-run:

  ```bash
  find output_receita_federal/documents -type l ! -xtype f -delete
  ```

- **Git:** symlinks are committed as links (mode `120000`) if this folder is
  staged. Consider adding `output_receita_federal/documents/` to `.gitignore`
  if the aggregation is meant to be a purely local convenience view, since it is
  fully reproducible from the one-liner above.
- **Windows note:** the links are POSIX symlinks created under WSL2. Accessing
  the folder from native Windows tooling may or may not follow them depending on
  the tool; on Linux/WSL they behave as ordinary files for reading.
