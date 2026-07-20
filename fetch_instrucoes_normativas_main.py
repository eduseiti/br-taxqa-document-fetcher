#!/usr/bin/env python3
"""
DEPRECATED shim — use ``fetch_receita_normas_main.py``.

The Instrução Normativa fetcher has been generalized to all Receita Federal
portal act types (Solução de Consulta, Ato Declaratório, Parecer Normativo, …),
each written to its own output folder. This shim preserves the old command line:

    python fetch_instrucoes_normativas_main.py                       # IN SRF
    python fetch_instrucoes_normativas_main.py --only instrucao_normativa_rfb

It forwards to ``fetch_receita_normas_main.main`` but defaults to the Instrução
Normativa types and the legacy ``output_instrucoes_normativas/`` output root when
no type/output flags are supplied, so existing docs/tests keep working.
"""

import sys

import fetch_receita_normas_main as new_main

LEGACY_OUTPUT = "./output_instrucoes_normativas"
DEFAULT_ONLY = "instrucao_normativa_srf"


def main():
    argv = sys.argv[1:]
    has_type_flag = any(a == "--only" or a == "--types" or a.startswith("--only=")
                        or a.startswith("--types=") for a in argv)
    has_output = any(a == "--output-dir" or a.startswith("--output-dir=") for a in argv)

    injected = []
    if not has_type_flag:
        injected += ["--only", DEFAULT_ONLY]
    if not has_output:
        injected += ["--output-dir", LEGACY_OUTPUT]

    print("[deprecated] fetch_instrucoes_normativas_main.py -> "
          "fetch_receita_normas_main.py", file=sys.stderr)
    sys.argv = [sys.argv[0]] + injected + argv
    return new_main.main()


if __name__ == "__main__":
    sys.exit(main())
