"""Tests of the offer null control (P5-31, fidetype.trust.dropin.offer_control)."""

from __future__ import annotations

import math

import numpy as np
import pytest

import fidetype.trust as ft
from fidetype.trust import dropin as D
from fidetype.trust.guarantee_sheet import policy_sheets

from test_trust_dropin import nbest_data, noise_nbest


def _c(name: str, n: int, n_offer: int | None) -> D.ControlResult:
    return D.ControlResult(name, "test", n, 0, int(math.floor(0.05 * n + 1e-9)), n_offer)


def test_fisher_p_equals_scipy():
    stats = pytest.importorskip("scipy.stats")
    for k0, n0, k1, n1 in [(77, 80, 77, 80), (13, 80, 77, 80), (0, 300, 33, 112), (60, 60, 33, 112),
                           (5, 40, 0, 40), (3, 10, 9, 10), (0, 1, 0, 1)]:
        want = stats.fisher_exact([[k0, n0 - k0], [k1, n1 - k1]], alternative="less")[1]
        assert D._fisher_less_p(k0, n0, k1, n1) == pytest.approx(want, rel=1e-9, abs=1e-15)


@pytest.mark.parametrize("null,real,ok", [
    ((77, 80), (77, 80), False),   # P14-41 frame-shuffled: as often as on real input
    ((13, 80), (77, 80), True),    # P14-48 time-shuffled: clearly below
    ((0, 300), (77, 80), True),    # never offers on null input
    ((0, 300), (0, 40), True),     # a guard that never offers passes (0 <= 0)
    ((5, 300), (0, 40), False),    # offers on null input only
    ((60, 100), (90, 100), False),  # significant, but not a clear drop (ratio 0.67 > 0.5)
    ((10, 20), (39, 40), False),   # ratio 0.5 / 0.975 = 0.513 > 0.5: just above the line
    ((9, 20), (39, 40), True),     # ratio 0.45 / 0.975 = 0.46, Fisher p < 0.05
])
def test_rule(null, real, ok):
    o = D.offer_control(real[1], real[0], [_c("shuffled", null[1], null[0])], rate=0.05)
    r = o["controls"][0]
    assert r["passed"] is ok and o["passed"] is ok
    assert o["real"] == {"n": real[1], "n_offer": real[0], "offer_rate": round(real[0] / real[1], 6)}


def test_few_null_offers_pass_without_a_test():
    # 2 of 60 null offers (<= floor(0.05 x 60) = 3) and real 2 / 10 (ratio 0.17): no test is needed.
    o = D.offer_control(10, 2, [_c("uniform", 60, 2)], rate=0.05)
    assert o["controls"][0]["p_value"] > 0.05 and o["passed"]


def test_bad_arguments():
    with pytest.raises(ValueError):
        D.offer_control(10, 5, [_c("uniform", 10, None)], rate=0.05)
    with pytest.raises(ValueError):
        D.offer_control(10, 5, [_c("uniform", 10, 1)], rate=0.05, mode="off")


@pytest.fixture(scope="module")
def data():
    xs, ts = nbest_data(240, 0)
    rng = np.random.default_rng(1)
    return xs, ts, [noise_nbest(rng) for _ in range(40)]


@pytest.fixture(scope="module")
def guards(data):
    xs, ts, nulls = data
    kw = dict(null_inputs=nulls, null_trials=40, decoder_name="test-nbest", modality="emg")
    return {m: ft.calibrate(xs, ts, offer_control=m, **kw) for m in ("warn", "off")}


def test_default_is_warn_and_the_sheet_reports_offers(data, guards):
    g, off = guards["warn"], guards["off"]
    sh = g.sheet
    assert sh.offers is not None and sh.offers["mode"] == "warn"
    assert all(c.n_offer is not None for c in sh.controls)
    assert [r["n_offer"] for r in sh.offers["controls"]] == [c.n_offer for c in sh.controls]
    assert sh.offers["real"]["n"] == sh.n_ltt
    # This n-best guard offers on every no-evidence input: it fails, as a warning only.
    assert not sh.offers["passed"]
    assert any(w.startswith("offer null control (P5-31) FAILED") for w in sh.warnings)
    assert "offer null control" in str(sh)
    # The status does not change: same config, same commit controls, same threshold.
    assert g.config_id == off.config_id
    assert sh.feasible == off.sheet.feasible and sh.commit_threshold == off.sheet.commit_threshold
    assert [(c.name, c.n, c.n_commit, c.passed) for c in sh.controls] == \
        [(c.name, c.n, c.n_commit, c.passed) for c in off.sheet.controls]
    ps = policy_sheets(g)[0]
    assert ps.status["offer_null_control"]["passed"] is False
    assert "offers" in str(ps)


def test_off_keeps_the_old_sheet_bytes(guards):
    d = guards["off"].sheet.to_dict()
    assert "offers" not in d
    assert all("n_offer" not in c for c in d["controls"])
    assert not any(w.startswith("offer null control") for w in d["warnings"])


def test_sheet_round_trip(guards, tmp_path):
    g = guards["warn"]
    back = D.GuaranteeSheet.from_dict(g.sheet.to_dict())
    assert back == g.sheet
    p = g.save(tmp_path / "g.json")
    assert ft.load(p).sheet.offers == g.sheet.offers
    old = D.GuaranteeSheet.from_dict(guards["off"].sheet.to_dict())
    assert old.offers is None and all(c.n_offer is None for c in old.controls)


def test_refuse_mode_raises(data):
    xs, ts, nulls = data
    with pytest.raises(ft.NullControlError, match="offer_control='refuse'"):
        ft.calibrate(xs, ts, null_inputs=nulls, null_trials=40, offer_control="refuse")
    with pytest.raises(ValueError):
        ft.calibrate(xs, ts, null_inputs=nulls, null_trials=40, offer_control="yes")


def test_recheck_reproduces_the_calibration(data, guards):
    xs, _, nulls = data
    for m in ("warn", "off"):
        g = guards[m]
        got = ft.recheck_offer_control(g, xs, null_inputs=nulls)
        assert got["commits_match_sheet"] is True
        if m == "warn":
            for k in ("real", "controls", "passed"):
                assert got[k] == g.sheet.offers[k]
    with pytest.raises(ValueError):
        ft.recheck_offer_control(guards["warn"], xs[:-1], null_inputs=nulls)
