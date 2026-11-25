"""Print the B1 aggregate tables (Markdown) from results/summary.json and results/gate.json.

    python b1report.py > tables.md

Aggregates only: no subject code, no per-word or per-channel value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def f(x, d=4):
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    return f"{x:.{d}f}"


def iv(a):
    return "-" if a is None or a[0] is None else f"[{f(a[0])}, {f(a[1])}]"


def gate_rows(name: str, m: dict) -> list[str]:
    out = []
    for g in ("g_plus", "g_minus"):
        x = m[g]
        out.append(f"| {name} | {'G+' if g == 'g_plus' else 'G-'} | {x['words']} | {x['flags']} | {f(x['flag_rate'])} "
                   f"{iv(x['boot']['flag_rate'])} | {f(x['wrong_rate'])} {iv(x['boot']['wrong_rate'])} | "
                   f"{f(x['precision_minus_base'])} {iv(x['boot']['precision_minus_base'])} | {f(x['base_rate'])} |")
    return out


def main() -> int:
    res = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    s = json.loads((res / "summary.json").read_text(encoding="utf-8"))
    g = json.loads((res / "gate.json").read_text(encoding="utf-8"))
    p = print
    p(f"Outcome: **{s['outcome']}**\n")
    p("| rule | numbers | pass |\n|---|---|---|")
    for k, v in s["rules"].items():
        if isinstance(v, dict):
            nums = ", ".join(f"{a} = {f(b) if not isinstance(b, (list, dict)) else b}" for a, b in v.items() if a != "pass")
            p(f"| {k} | {nums} | {f(v.get('pass'))} |")
        else:
            p(f"| {k} | | {f(v)} |")
    p("\n| input | AUC mean | SD | n | t | p (two-sided) |\n|---|---|---|---|---|---|")
    for k in ("neural", "b0", "b0n", "p0", "n2", "n3a", "n3b"):
        a = s[k]["auc"]
        p(f"| {k} | {f(a['mean'])} | {f(a['sd'])} | {a['n']} | {f(a['t'], 2)} | {f(a['p_two_sided'], 6)} |")
    p("\n| input | gate | test words | flags | flag rate [boot 95 %] | wrong-flag rate [boot 95 %] | "
      "precision - base [boot 95 %] | base rate |\n|---|---|---|---|---|---|---|---|")
    for k in ("neural", "b0", "b0n", "p0", "n2", "n3a", "n3b", "n4", "n5"):
        for r in gate_rows(k, s[k]):
            p(r)
    p("\n| input | lambda+ | tau+ | lambda- | tau- | b_order |\n|---|---|---|---|---|---|")
    for k in ("neural", "b0", "b0n", "p0"):
        x = g["gates"][k]
        p(f"| {k} | {f(x['g_plus']['lambda'], 2)} | {f(x['tau_plus'])} | {f(x['g_minus']['lambda'], 2)} | "
          f"{f(x['tau_minus'])} | {f(x['b_order'])} |")
    p("\n| input | OFFER q | singleton share | coverage |\n|---|---|---|---|")
    for k in ("neural", "b0", "b0n", "p0"):
        o = s[k]["offer"]
        p(f"| {k} | {f(o['q'])} | {f(o['singleton_share'])} | {f(o['coverage'])} |")
    n1 = s["n1"]
    p(f"\nN1: G+ certified in {n1['n_g_plus_certified']} of {len(n1['runs'])} runs; "
      f"G- certified in {n1['n_g_minus_certified']} of {len(n1['runs'])} runs.")
    for k in ("n2", "n3a"):
        p(f"{k}: G+ flag agreement with real input {f(s[k].get('g_plus_flag_agreement_with_real'))}, "
          f"mean score correlation {f(s[k].get('score_corr_with_real'))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
