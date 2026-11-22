"""Adapter registry and catalogue (P14-42): valid metadata, fresh docs, a working template.

CI runs this file in the normal pytest job, so a stale docs/adapters.md,
docs/adapters.json or docs/device-support.md (P4-15) fails CI.
"""

from __future__ import annotations

import importlib
import shutil
import sys

import pytest

from fidetype.adapters import registry as R


def test_registry_is_valid():
    entries = R.collect()
    assert R.validate(entries) == []
    ids = {e["id"] for e in entries}
    assert {"edf", "openbci-gui", "lsl", "brainflow", "kt-semg", "ctc-logits"} <= ids
    for e in entries:
        if e["status"] == "planned":
            assert e["module"] is None and e["tests"] == []
        else:
            assert importlib.import_module(e["module"])


def test_catalogue_is_fresh():
    """Fails when an ADAPTER_INFO or planned.py changed but the docs were not regenerated."""
    assert R.check() == [], "run: python -m fidetype.adapters.registry"


def test_validate_catches_errors():
    good = [e for e in R.collect()]
    bad = [dict(good[0], status="supported"), dict(good[1], tests=["tests/no_such_file.py"]),
           {"id": "Bad_Id", "kind": "x", "status": "planned", "tests": ["t"], "module": "m"}]
    errs = "\n".join(R.validate(bad))
    for frag in ("status 'supported'", "no_such_file.py", "kebab-case", "missing field", "planned entry",
                 "declares no ADAPTER_INFO"):
        assert frag in errs


def test_planned_is_never_claimed():
    md = R.render_md(R.collect())
    impl, planned = md.split("## Planned (not supported)")
    for e in R.collect():
        if e["status"] == "planned":
            assert f"`{e['id']}`" not in impl and f"`{e['id']}`" in planned


def test_template_scaffold_passes_conformance(tmp_path, monkeypatch):
    """`registry new` copies the template; the copy passes its own conformance test unchanged."""
    root = tmp_path / "repo"
    shutil.copytree(R.ROOT / R.TEMPLATE_DIR, root / R.TEMPLATE_DIR)
    (root / "src/fidetype/adapters").mkdir(parents=True)
    (root / "tests").mkdir()
    mod_path, test_path = R.scaffold("demo-format", root)
    with pytest.raises(ValueError):
        R.scaffold("demo-format", root)  # never overwrite
    text = mod_path.read_text(encoding="utf-8")
    assert '"id": "demo-format"' in text and "my_format" not in text and "my-format" not in text
    # Import the new module as fidetype.adapters.demo_format and run the generated test.
    import fidetype.adapters as pkg

    monkeypatch.setattr(pkg, "__path__", [*pkg.__path__, str(mod_path.parent)])
    monkeypatch.syspath_prepend(str(test_path.parent))
    sys.modules.pop("fidetype.adapters.demo_format", None)
    t = importlib.import_module("test_adapter_demo_format")
    try:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        t.test_demo_format_conforms(tmp_path / "a")
        t.test_demo_format_values(tmp_path / "b")
    finally:
        sys.modules.pop("test_adapter_demo_format", None)
        sys.modules.pop("fidetype.adapters.demo_format", None)


# --- P4-15: device support matrix ------------------------------------------------------------------


def test_device_support_page_is_generated_and_checked():
    out = R.outputs()
    assert R.DOC_DEVICES in out
    page = (R.ROOT / R.DOC_DEVICES).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert page == out[R.DOC_DEVICES], "run: python -m fidetype.adapters.registry"
    assert "GENERATED FILE. DO NOT EDIT" in page


def test_check_reports_a_stale_device_page(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "validate", lambda entries, root=R.ROOT: [])
    for rel, text in R.outputs().items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8", newline="\n")
    assert R.check(tmp_path) == []
    p = tmp_path / R.DOC_DEVICES
    p.write_text(p.read_text(encoding="utf-8").replace("`replay-only`", "`real-device`", 1), encoding="utf-8")
    assert R.check(tmp_path) == [f"{R.DOC_DEVICES} is stale; run: python -m fidetype.adapters.registry"]
    p.unlink()
    assert "missing" in R.check(tmp_path)[0]


def test_every_row_has_support_fields_and_evidence():
    for e in R.collect():
        assert e["support"] in R.SUPPORT_TEXT
        if e["status"] == "planned":
            assert e["support"] == "untested" and e["real_data_evidence"] == []
            continue
        assert e["transport"] and all(t in R.TRANSPORTS for t in e["transport"])
        assert e["test_covers"].strip() and e["limits"].strip()
        if e["support"] in ("real-device", "replay-only"):
            assert e["real_data_evidence"], e["id"]
            assert all((R.ROOT / p).exists() for p in e["real_data_evidence"]), e["id"]
        if e["status"] == "tested" and e["support"] == "synthetic-only":
            assert e["kind"] in R.SYNTHETIC_TESTED_KINDS, e["id"]
        assert (e["support"] == "real-device") == bool(e["hardware_tested"])


def _impl(**kw):
    base = {"id": "demo-dev", "kind": "device-source", "target": "Demo board", "signal": "eeg", "status": "tested",
            "licence": "x", "tests": ["tests/test_adapter_registry.py"], "docs": "docs/adapters.md",
            "support": "replay-only", "transport": ["lsl"], "real_data_evidence": ["tests/test_adapter_registry.py"],
            "test_covers": "x", "limits": "x", "hardware_tested": [], "module": None}
    return {**base, **kw}


@pytest.mark.parametrize("kw, frag", [
    ({"support": "synthetic-only", "real_data_evidence": []}, "status 'tested' with synthetic-only tests"),
    ({"real_data_evidence": []}, "needs real_data_evidence"),
    ({"support": "real-device"}, "needs hardware_tested"),
    ({"hardware_tested": ["Cyton"]}, "needs hardware_tested"),
    ({"status": "experimental"}, "status 'experimental' means synthetic-only"),
    ({"support": "synthetic-only"}, "cannot list real_data_evidence"),
    ({"support": "untested", "real_data_evidence": []}, "planned rows only"),
    ({"support": "supported"}, "support 'supported'"),
    ({"transport": ["carrier-pigeon"]}, "transport must be"),
    ({"limits": " "}, "limits must be"),
    ({"real_data_evidence": ["tests/no_such_evidence.py"]}, "no_such_evidence.py"),
])
def test_support_rules_refuse_unbacked_claims(kw, frag):
    e = _impl(**kw)
    errs = "\n".join(x for x in R.validate([e]) if "declares no ADAPTER_INFO" not in x)
    assert frag in errs, errs


def test_support_rules_accept_honest_rows():
    ok = [_impl(),
          _impl(id="demo-a", status="experimental", support="synthetic-only", real_data_evidence=[]),
          _impl(id="demo-b", kind="transport", support="synthetic-only", real_data_evidence=[]),
          _impl(id="demo-c", support="real-device", hardware_tested=["Demo board rev 1"])]
    errs = [x for x in R.validate(ok) if "declares no ADAPTER_INFO" not in x]
    assert errs == []
    page = R.render_devices_md(ok)
    assert "Real devices: Demo board rev 1." in page and "1 real device" in page
    missing = {k: v for k, v in _impl(id="demo-d").items() if k != "limits"}
    assert any("missing field 'limits'" in x for x in R.validate([missing]))


def test_template_declares_honest_support():
    import ast

    tree = ast.parse((R.ROOT / R.TEMPLATE_DIR / "my_format.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "ADAPTER_INFO")
    info = ast.literal_eval(node.value)
    assert info["status"] == "experimental" and info["support"] == "synthetic-only"
    assert R._support_errors({**info, "module": None}) == []
