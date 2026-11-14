//! Example: validate a replay file and print what a consumer does with it.
//!
//! ```text
//! cargo run --example validate_replay [FILE]
//! ```
//!
//! FILE is a JSON Lines file:
//! - a decision log (only trust_decision lines, FEP-0001 section 3 / FEP-0003
//!   section 5): each decision is printed with what a consumer does with it
//!   (act only on a final COMMIT);
//! - or a NeuralTextStream input stream (header first): it is validated event
//!   by event (in 64 KiB blocks) and then checked as a whole file (the v0.1
//!   reference consumer).
//!
//! Default: a decision log from the FEP-0001 golden vectors. Exit code 0 =
//! valid, 1 = invalid.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::process::ExitCode;

use fidetype::io;
use fidetype::json::{repr, Value};
use fidetype::reader::parse_nts_bytes;
use fidetype::trust::{DecisionKind, DecisionTracker};

fn main() -> ExitCode {
    let file = std::env::args().nth(1).map(PathBuf::from).unwrap_or_else(|| {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../spec/conformance/fep-0001/f25-log-two-sessions.jsonl")
    });
    let bytes = match io::read_bytes(&file) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("{}", e);
            return ExitCode::from(2);
        }
    };
    let first_type = parse_nts_bytes(&bytes).ok().and_then(|evs| evs.first().map(|e| e.get("type").clone()));
    if first_type.as_ref().and_then(|t| t.as_str()) == Some("trust_decision") {
        return decisions(&bytes);
    }
    // An input stream: event-by-event validation, then the whole-file consumer.
    let mut counts: BTreeMap<&'static str, usize> = BTreeMap::new();
    match io::validate_file_streaming(&file, |_, r| *counts.entry(r.kind()).or_insert(0) += 1) {
        Ok(n) => println!("{} events valid event by event: {:?}", n, counts),
        Err(e) => {
            println!("INVALID (streaming): {}", e);
            return ExitCode::from(1);
        }
    }
    match io::load_stream_file(&file) {
        Ok(s) => {
            println!("accepted by the v0.1 reference consumer: {}", repr(&Value::Obj(s.summary)));
            ExitCode::SUCCESS
        }
        Err(e) => {
            println!("REJECTED: {}", e);
            ExitCode::from(1)
        }
    }
}

fn decisions(bytes: &[u8]) -> ExitCode {
    let events = match parse_nts_bytes(bytes) {
        Ok(e) => e,
        Err(e) => {
            println!("INVALID: {}", e);
            return ExitCode::from(1);
        }
    };
    let mut tracker = DecisionTracker::new();
    let mut bad = 0;
    for ev in &events {
        let d = tracker.push(ev);
        let unit = if ev.get("profile").as_str() == Some("intent") {
            format!("unit {}", repr(ev.get("unit")))
        } else {
            format!("utt {}", if ev.has("utterance") { repr(ev.get("utterance")) } else { "-".into() })
        };
        let who = format!("{}/{}", ev.get("session").as_str().unwrap_or("-"), unit);
        let line = match d.kind {
            DecisionKind::Commit => format!(
                "COMMIT  {:?}{}",
                d.committed.as_deref().unwrap_or("<omitted>"),
                if d.forward { "  -> send to the output" } else { "" }
            ),
            DecisionKind::Preview => format!("preview {} (is_final = false: show only, never act)", repr(ev.get("action"))),
            DecisionKind::Invalid => "INVALID".to_string(),
            _ => format!("{:<7} {}", repr(ev.get("action")), if d.offered.is_empty() { String::new() } else { format!("offer {:?}", d.offered) }),
        };
        println!("{:<14} seq {:>3}  {}", who, repr(ev.get("seq")), line);
        for w in &d.warnings {
            println!("{:24}warning: {}", "", w);
        }
        for e in &d.errors {
            println!("{:24}error: {}", "", e);
        }
        if !d.errors.is_empty() {
            bad += 1;
        }
    }
    if bad > 0 {
        ExitCode::from(1)
    } else {
        ExitCode::SUCCESS
    }
}
