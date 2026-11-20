"""Adapter registry and catalogue (P14-42): valid metadata, fresh docs, a working template.

CI runs this file in the normal pytest job, so a stale docs/adapters.md
or docs/adapters.json fails CI.
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
