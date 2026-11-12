#!/usr/bin/env bash
# Paper 1 (draft v4): build the main paper and the supplement with Tectonic.
# Cross-references between the two files use xr-hyper, so the files are built in turn twice.
# Usage (Git Bash, repo root or anywhere):  bash papers/paper1/build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="${TECTONIC:-/c/Users/zhang/tools/tectonic/tectonic.exe}"
cd "$HERE/latex"
mkdir -p build
for pass in 1 2; do
  for doc in supplement main; do
    "$T" -X compile "$doc.tex" --outdir build --keep-intermediates --keep-logs > "build/$doc-pass$pass.out" 2>&1 \
      || { echo "build failed: $doc pass $pass (see latex/build/$doc-pass$pass.out)"; tail -20 "build/$doc-pass$pass.out"; exit 1; }
  done
done
for doc in main supplement; do
  n=$(grep -ciE "Citation .* undefined|Reference .* undefined|There were undefined" "build/$doc.log" || true)
  echo "$doc: undefined references/citations: $n"
done
