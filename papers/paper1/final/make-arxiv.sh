#!/usr/bin/env bash
# Paper 1: build the arXiv source package (one combined document: main text + supplement).
#  1. copy sections/, generated/ and the figures into final/arxiv/
#  2. build final/arxiv/main.tex with Tectonic (bibtex runs on a copy of latex/refs.bib) -> main.bbl
#  3. zip main.tex, main.bbl, sections/, generated/, figures/ -> final/arxiv-source.zip
#  4. unzip into an empty temp folder and build again from scratch, WITHOUT the .bib (as arXiv does)
# Usage (Git Bash): bash papers/paper1/final/make-arxiv.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P1="$(cd "$HERE/.." && pwd)"
T="${TECTONIC:-/c/Users/zhang/tools/tectonic/tectonic.exe}"
A="$HERE/arxiv"

# 1. sync sources
rm -rf "$A/sections" "$A/generated" "$A/figures" "$A/main.bbl"
mkdir -p "$A/sections" "$A/generated" "$A/figures"
cp "$P1"/latex/sections/*.tex "$A/sections/"
rm -f "$A/sections/supplement-body.tex.bak"
cp "$P1"/latex/generated/*.tex "$A/generated/"
cp "$P1"/figures/*.pdf "$P1"/figures/tikz-*.tex "$A/figures/"

# 2. build with bibtex
B="$(mktemp -d)"
cp -r "$A"/main.tex "$A"/sections "$A"/generated "$A"/figures "$B/"
cp "$P1/latex/refs.bib" "$B/main.bib"
( cd "$B" && "$T" -X compile main.tex --keep-intermediates --keep-logs > build.out 2>&1 ) \
  || { echo "build failed"; tail -30 "$B/build.out"; exit 1; }
cp "$B/main.bbl" "$A/main.bbl"
cp "$B/main.pdf" "$HERE/fidetype-paper1-arxiv.pdf"

# 3. zip (Windows bsdtar writes a standard zip with forward-slash paths)
rm -f "$HERE/arxiv-source.zip"
( cd "$A" && /c/Windows/System32/tar.exe -a -c -f ../arxiv-source.zip main.tex main.bbl sections generated figures )

# 4. clean rebuild from the zip, no .bib
V="$(mktemp -d)"
( cd "$V" && unzip -q "$HERE/arxiv-source.zip" )
echo "zip contents:"; unzip -l "$HERE/arxiv-source.zip" | tail -n +4 | head -n -2 | awk '{print "  " $4}'
# arXiv runs pdflatex only and reads the shipped main.bbl. Tectonic always runs BibTeX when the .aux
# names a bibliography, so the check file reads main.bbl directly instead (same effect, no BibTeX).
sed 's/\\bibliography{main}/\\input{main.bbl}/' "$V/main.tex" > "$V/verify.tex"
grep -q 'input{main.bbl}' "$V/verify.tex" || { echo "verify: bibliography line not found"; exit 1; }
( cd "$V" && "$T" -X compile verify.tex --untrusted --keep-logs > verify.out 2>&1 ) \
  || { echo "verify build failed"; tail -30 "$V/verify.out"; exit 1; }
mv "$V/verify.pdf" "$V/main.pdf"; mv "$V/verify.log" "$V/main.log"
echo "verify: undefined refs/citations: $(grep -ciE 'Citation .* undefined|Reference .* undefined|There were undefined' "$V/main.log" || true)"
echo "verify: multiply defined: $(grep -ciE 'multiply defined' "$V/main.log" || true)"
echo "verify: overfull boxes: $(grep -ciE 'Overfull' "$V/main.log" || true)"
echo "verify: '??' in text: $(pdftotext "$V/main.pdf" - | grep -c '??' || true)"
echo "verify: identical bytes to local build PDF (size): $(wc -c < "$V/main.pdf") vs $(wc -c < "$HERE/fidetype-paper1-arxiv.pdf")"
echo "verify folder: $V"
rm -rf "$B"
