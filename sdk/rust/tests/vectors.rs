//! The golden vectors of spec/conformance (the same files as the Python suite).

use std::path::PathBuf;

use fidetype::io;

fn vectors() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../spec/conformance")
}

fn run(profile: &str, expected_total: usize) {
    let r = io::run_profile_dir(profile, vectors().join(profile)).unwrap();
    let fails: Vec<_> = r.vectors.iter().filter(|o| !o.ok).map(|o| format!("{} {} {}", o.id, o.actual, o.detail)).collect();
    assert!(fails.is_empty(), "{} failures: {:#?}", profile, fails);
    assert_eq!(r.total, expected_total, "{}: vector count changed", profile);
}

#[test]
fn v01_vectors() {
    run("v0.1", 92);
}

#[test]
fn fep0001_vectors() {
    run("fep-0001", 66);
}

#[test]
fn fep0002_vectors() {
    run("fep-0002", 35);
}

#[test]
fn fep0003_vectors() {
    run("fep-0003", 51);
}

#[test]
fn fep0004_vectors() {
    run("fep-0004", 44);
}

#[test]
fn fep0005_vectors() {
    run("fep-0005", 53);
}

#[test]
fn profiles_listed_in_order() {
    assert_eq!(io::list_profiles(vectors()), ["v0.1", "fep-0001", "fep-0002", "fep-0003", "fep-0004", "fep-0005"]);
}

#[test]
fn accepted_vectors_pass_the_streaming_validator() {
    // Every accepted v0.1 JSON Lines vector is also valid event by event.
    let dir = vectors().join("v0.1");
    let manifest = fidetype::parse_json(&std::fs::read_to_string(dir.join("manifest.json")).unwrap()).unwrap();
    let mut n = 0;
    for v in manifest.get("vectors").as_arr().unwrap() {
        let file = v.get("file").as_str().unwrap();
        if !file.ends_with(".jsonl") || v.get("expect").as_str() != Some("accept") {
            continue;
        }
        // NTS 1.0 RC3, VER-8 / VER-10: V66 is 1.1 data with an unknown vocab_type. The streaming header check is
        // the one of the trust layer, which refuses it (a trust layer that cannot apply a fallback stops).
        if v.get("id").as_str() == Some("V66") {
            assert!(io::validate_file_streaming(dir.join(file), |_, _| {}).is_err(), "V66: the trust-layer header check refuses it");
            continue;
        }
        let r = io::validate_file_streaming(dir.join(file), |_, _| {});
        assert!(r.is_ok(), "{}: {:?}", file, r);
        n += 1;
    }
    assert!(n >= 5);
}

#[test]
fn fep0005_reject_vectors_fail_their_named_check() {
    use fidetype::profiles::fep0005;
    let dir = vectors().join("fep-0005");
    let manifest = fidetype::parse_json(&std::fs::read_to_string(dir.join("manifest.json")).unwrap()).unwrap();
    for v in manifest.get("vectors").as_arr().unwrap() {
        let file = v.get("file").as_str().unwrap();
        let bytes = std::fs::read(dir.join(file)).unwrap();
        let rep = fep0005::check_file(file, &bytes);
        let fails: Vec<&str> = rep.checks.iter().filter(|c| c.status == fidetype::checks::Status::Fail).map(|c| c.id.as_str()).collect();
        if v.get("expect").as_str() == Some("reject") {
            let want = v.get("failing_check").as_str().unwrap();
            assert!(fails.contains(&want), "{}: {:?} lacks {}", file, fails, want);
        } else {
            assert!(fails.is_empty(), "{}: {:?}", file, fails);
        }
        if let Some(want) = v.get("expected").get("moving_ticks").as_arr() {
            let got = fep0005::consume(file, &bytes).unwrap();
            let got = got.get("moving_ticks").as_arr().unwrap().clone();
            assert!(fidetype::json::py_eq(&fidetype::Value::Arr(got), &fidetype::Value::Arr(want.clone())), "{}", file);
        }
    }
}

#[test]
fn fep0005_decision_tracker_matches_the_decision_log_vectors() {
    use fidetype::trust::{DecisionKind, DecisionTracker};
    let dir = vectors().join("fep-0005");
    let manifest = fidetype::parse_json(&std::fs::read_to_string(dir.join("manifest.json")).unwrap()).unwrap();
    let mut n = 0;
    for v in manifest.get("vectors").as_arr().unwrap() {
        let file = v.get("file").as_str().unwrap();
        if !file.starts_with('e') {
            continue;
        }
        n += 1;
        let text = std::fs::read_to_string(dir.join(file)).unwrap();
        let mut t = DecisionTracker::new();
        let out: Vec<_> = text.lines().filter(|l| !l.trim().is_empty()).map(|l| t.push_text(l)).collect();
        let errs: Vec<&String> = out.iter().flat_map(|d| d.errors.iter()).collect();
        if v.get("expect").as_str() == Some("accept") {
            assert!(errs.is_empty(), "{}: {:?}", file, errs);
            if let Some(want) = v.get("expected").get("moving_ticks").as_arr() {
                let got: Vec<f64> = out.iter().filter(|d| d.profile == "control" && d.forward).map(|d| d.tick.unwrap()).collect();
                let want: Vec<f64> = want.iter().map(|x| x.as_f64().unwrap()).collect();
                assert_eq!(got, want, "{}", file);
                assert!(out.iter().filter(|d| d.profile == "control" && d.forward).all(|d| d.kind == DecisionKind::Commit));
            }
        } else {
            assert!(!errs.is_empty(), "{}: the tracker found no error", file);
        }
    }
    assert!(n >= 21);
}

/// P7-01: the conformance kit (spec/conformance/kit/<profile>/manifest.json) gives the expected verdict.
#[test]
fn conformance_kit() {
    let kit = vectors().join("kit");
    let counts = [("v0.1", 14), ("fep-0001", 4), ("fep-0002", 3), ("fep-0003", 4), ("fep-0004", 3), ("fep-0005", 3)];
    assert_eq!(io::list_profiles(&kit), counts.iter().map(|c| c.0).collect::<Vec<_>>());
    for (profile, n) in counts {
        let r = io::run_profile_dir(profile, kit.join(profile)).unwrap();
        let fails: Vec<_> = r.vectors.iter().filter(|o| !o.ok).map(|o| format!("{} {} {}", o.id, o.actual, o.detail)).collect();
        assert!(fails.is_empty(), "kit {}: {:#?}", profile, fails);
        assert_eq!(r.total, n, "kit {}: entry count changed", profile);
    }
}
