"""P5-19 / FEP-0010 LIC-2: the advisory check NTS-LICENCE-MATCH (MET-12, NTS 1.0 RC4 amendment 7).

Synthetic data only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fidetype.conformance import check_file
from fidetype.conformance.rules import load_rule_map
from fidetype.trust import licence as L

ROOT = Path(__file__).resolve().parents[1]
V01 = ROOT / "spec" / "conformance" / "v0.1"

# The same lists as the TypeScript test (sdk/typescript/test/vectors.test.mjs) and the Rust test licence_table.
NON_COMMERCIAL = ["CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-ND-3.0-IGO", "cc-by-nc-2.5", "CC-BY-SA-NC-4.0",
                  "LicenseRef-unknown", "licenseref-UNKNOWN"]
OTHER = ["CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-ND-4.0", "CC0-1.0", "MIT", "LicenseRef-fidetype-consented",
         "CC BY-NC 4.0", "CC-BY-NC-4.0\n", "CC-BY-NC-4.0-IGOX", "CC-BY-NC-40", "CC-BY-NCX-4.0", "CC-BY-NC-4.0-I",
         "CC-BY-NC-4.0-1G", "", "CC-BY-NC-4.٠", 4, None]


def test_licence_table():
    for x in NON_COMMERCIAL:
        assert L.no_commercial_id(x), x
    for x in OTHER:
        assert not L.no_commercial_id(x), x


@pytest.mark.parametrize("spdx", ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-ND-4.0", "CC-BY-NC-4.0",
                                  "CC-BY-NC-SA-4.0", "CC-BY-NC-ND-4.0", "CC-BY-NC-3.0-IGO", "MIT", "Apache-2.0",
                                  "ODbL-1.0", L.OWN, L.UNKNOWN])
def test_table_agrees_with_the_licence_terms(spdx):
    """Every id that the table flags has no commercial use in fidetype.trust.licence (the reverse holds except
    for consented data, whose product use depends on its consent scope)."""
    assert L.no_commercial_id(spdx) == (not L.terms(spdx).commercial)
    assert L.no_commercial_id(spdx) == bool(L.licence_meta(spdx)["data.research_only"])


def test_sdk_tables_mirror_the_python_pattern():
    ts = (ROOT / "sdk" / "typescript" / "src" / "checks.ts").read_text(encoding="utf-8")
    rs = (ROOT / "sdk" / "rust" / "src" / "checks.rs").read_text(encoding="utf-8")
    assert f"/{L._CC.pattern}/" in ts  # the same regular expression
    assert L._CC.pattern in rs  # named in the Rust doc comment next to the hand-written parser
    for src in (ts, rs):
        assert '"LicenseRef-unknown"' in src and "NTS-LICENCE-MATCH" in src


@pytest.mark.parametrize("vid, warns", [("V98", False), ("V101", True), ("V102", True), ("V103", True),
                                        ("V104", False)])
def test_vectors_warn_never_reject(vid, warns):
    f = next(V01.glob(f"{vid.lower()}-*"))
    rep = check_file(f)
    r = next(x for x in rep.results if x.check_id == "NTS-LICENCE-MATCH")
    assert (r.outcome == "warn") is warns, (vid, r.outcome, r.message)
    assert rep.passes("core"), vid
    m = json.loads((V01 / "manifest.json").read_text(encoding="utf-8"))
    v = next(x for x in m["vectors"] if x["id"] == vid)
    assert v["expect"] == "accept" and v["expected"]["warnings"] == (["NTS-LICENCE-MATCH"] if warns else [])


@pytest.mark.parametrize("meta, status", [
    ({"data.licence": "CC-BY-NC-4.0", "data.research_only": False}, "fail"),
    ({"data.licence": "CC-BY-NC-4.0", "data.research_only": True}, "skip"),
    ({"data.licence": "CC-BY-NC-4.0"}, "skip"),  # research_only absent: a consumer reads the licence alone
    ({"data.research_only": False}, "skip"),  # no licence: not checkable
    ({"data.licence": "CC-BY-4.0", "data.research_only": False}, "pass"),
    ({"data.licence": "Proprietary-X", "data.research_only": False}, "pass"),  # unknown id: silent, not permissive
    ({"data.licence": "CC-BY-NC-4.0", "data.research_only": 0}, "skip"),  # wrong type: NTS-META-TYPES
])
def test_check_rules(tmp_path, meta, status):
    from fidetype.conformance.checks import c_licence_match
    from fidetype.conformance.io import read_raw

    src = (V01 / "v98-data-licence-keys.jsonl").read_text(encoding="utf-8").splitlines()
    head = json.loads(src[0])
    head["meta"] = {k: v for k, v in head["meta"].items() if not k.startswith("data.")} | meta
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join([json.dumps(head), *src[1:]]) + "\n", encoding="utf-8")
    assert c_licence_match(read_raw(p))[0] == status


def test_rule_map_traces_the_check_to_met_12():
    assert load_rule_map()["checks"]["NTS-LICENCE-MATCH"] == ["MET-12"]
    assert re.search(r"NTS-LICENCE-MATCH", (ROOT / "spec" / "nts-1.0-rc4.md").read_text(encoding="utf-8"))
