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
    run("v0.1", 52);
}

#[test]
fn fep0001_vectors() {
    run("fep-0001", 40);
}

#[test]
fn fep0002_vectors() {
    run("fep-0002", 32);
}

#[test]
fn fep0003_vectors() {
    run("fep-0003", 44);
}

#[test]
fn profiles_listed_in_order() {
    assert_eq!(io::list_profiles(vectors()), ["v0.1", "fep-0001", "fep-0002", "fep-0003"]);
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
        let r = io::validate_file_streaming(dir.join(file), |_, _| {});
        assert!(r.is_ok(), "{}: {:?}", file, r);
        n += 1;
    }
    assert!(n >= 5);
}
