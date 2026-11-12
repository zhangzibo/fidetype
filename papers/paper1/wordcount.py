"""Approximate word count of Paper 1 (texcount-like; texcount itself is not installed).

Counts words in the LaTeX sources after removing comments, citations, references,
labels, math and command names (command arguments that hold text are kept).
Text inside figure / table / algorithm floats (captions and cells) is counted
separately. Usage (repo root): .venv/Scripts/python -I papers/paper1/wordcount.py
"""

from __future__ import annotations

import re
from pathlib import Path

SEC = Path(__file__).resolve().parent / "latex" / "sections"
MAIN = ["abstract", "introduction", "related", "setting", "trust", "protocol", "results", "discussion", "limitations",
        "conclusion", "ethics"]
FLOAT = re.compile(r"\\begin\{(figure|table|algorithm)\*?\}.*?\\end\{\1\*?\}", re.S)
DROP_ARG = re.compile(r"\\(cite[tp]?|citep|citet|cref|Cref|ref|label|eqref|url|includegraphics|input|inputrows|graphicspath)\*?(\[[^\]]*\])?\{[^}]*\}")
MATH = re.compile(r"\$[^$]*\$|\\\[.*?\\\]|\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}", re.S)
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-\.,%/]*")


def clean(t: str) -> str:
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = MATH.sub(" ", t)
    t = DROP_ARG.sub(" ", t)
    t = re.sub(r"\\begin\{[^}]*\}(\{[^}]*\})*|\\end\{[^}]*\}", " ", t)
    t = re.sub(r"\\[A-Za-z@]+\*?(\[[^\]]*\])?", " ", t)
    t = re.sub(r"[{}&\\~]", " ", t)
    return t


def count(t: str) -> int:
    return len(WORD.findall(clean(t)))


def file_counts(name: str) -> tuple[int, int]:
    t = (SEC / f"{name}.tex").read_text(encoding="utf-8")
    floats = "".join(m.group(0) for m in FLOAT.finditer(t))
    body = FLOAT.sub(" ", t)
    return count(body), count(floats)


def main() -> None:
    tot_b = tot_f = 0
    print(f"{'section':<16}{'text':>8}{'floats':>8}")
    for n in MAIN:
        b, f = file_counts(n)
        tot_b += b
        tot_f += f
        print(f"{n:<16}{b:>8}{f:>8}")
    print(f"{'MAIN TOTAL':<16}{tot_b:>8}{tot_f:>8}   (text + floats = {tot_b + tot_f})")
    ab, _ = file_counts("abstract")
    print(f"abstract: {ab} words")
    for n in ("appendix-main", "supplement-body"):
        b, f = file_counts(n)
        print(f"{n:<16}{b:>8}{f:>8}")


if __name__ == "__main__":
    main()
