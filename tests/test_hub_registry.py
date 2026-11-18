"""Hub dataset registry (P13-01): the committed registry is valid and the checks catch bad entries."""

from __future__ import annotations

import copy

from fidetype.benchmark import hub
from fidetype.benchmark.tracks import TRACKS


def test_committed_registry_is_valid():
    reg = hub.load_registry()
    assert hub.check_registry(reg) == []
    roles = {d["hub_role"] for d in reg["datasets"]}
    assert {"meg", "implant", "emg"} <= roles  # P13 exit criterion: three tracks (MEG, implant, EMG)


def test_registry_tracks_and_licences_match_the_track_specs():
    for d in hub.load_registry()["datasets"]:
        for t in d["tracks"]:
            spec = TRACKS[t["track"]]
            assert spec.dataset == d["id"]
            assert spec.research_only == d["licence"]["research_only"]
            assert spec.url == d["url"]


def test_checks_catch_bad_entries():
    good = hub.get_dataset("spanishbcbl")
    bad = copy.deepcopy(good)
    bad["licence"]["research_only"] = False          # NC licence must be research-only
    bad["personal_data"]["rehost"] = True             # the hub never re-hosts data
    bad["adapters"][0]["module"] = "brain2qwerty.x"   # only our own adapters
    bad["tracks"][0]["split_version"] = "v2"
    errs = " | ".join(hub.check_dataset(bad))
    for part in ("research_only must be true", "rehost", "fidetype module", "split_version"):
        assert part in errs
    assert hub.check_dataset(good) == []
