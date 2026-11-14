//! Command line of the Fidetype Rust SDK.
//!
//! ```text
//! fidetype-rs conformance [--profile NAME|all] [--vectors DIR] [--json OUT|-]
//! fidetype-rs validate FILE [--level core|trust-ready|provenance] [--json]
//! fidetype-rs consume [--profile NAME] FILE     exit 0 = accept (prints the summary as JSON), 1 = reject
//! fidetype-rs decisions FILE                    print what a consumer does with each trust_decision
//! ```
//!
//! `consume` follows the external-consumer contract of the Python suite, so
//! `python -m fidetype.conformance consumer --cmd "fidetype-rs consume {path}"`
//! runs the Python suite against this SDK.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use fidetype::checks::{Level, Status};
use fidetype::conformance::consumer_for;
use fidetype::io;
use fidetype::json::{repr, Map, Value};
use fidetype::trust::DecisionKind;

fn take_opt(args: &mut Vec<String>, name: &str) -> Option<String> {
    let i = args.iter().position(|a| a == name)?;
    if i + 1 >= args.len() {
        args.remove(i);
        return None;
    }
    let v = args.remove(i + 1);
    args.remove(i);
    Some(v)
}

fn take_flag(args: &mut Vec<String>, name: &str) -> bool {
    match args.iter().position(|a| a == name) {
        Some(i) => {
            args.remove(i);
            true
        }
        None => false,
    }
}

fn default_vectors() -> PathBuf {
    // sdk/rust -> repo root -> spec/conformance
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..").join("spec").join("conformance")
}

fn conformance(mut args: Vec<String>) -> Result<u8, String> {
    let profile = take_opt(&mut args, "--profile").unwrap_or_else(|| "all".into());
    let vectors = take_opt(&mut args, "--vectors").map(PathBuf::from).unwrap_or_else(default_vectors);
    let json_out = take_opt(&mut args, "--json");
    let profiles = if profile == "all" { io::list_profiles(&vectors) } else { vec![profile.clone()] };
    let mut reports = Vec::new();
    let mut all_ok = true;
    for p in &profiles {
        let dir = if profile == "all" || vectors.join(p).join("manifest.json").is_file() { vectors.join(p) } else { vectors.clone() };
        let r = io::run_profile_dir(p, &dir).map_err(|e| e.to_string())?;
        for o in &r.vectors {
            if !o.ok {
                eprintln!("  FAIL {} {}: expected {}, got {}. {}", p, o.id, o.expect, o.actual, o.detail);
            }
        }
        if json_out.as_deref() == Some("-") {
            eprintln!("{}", r.line());
        } else {
            println!("{}", r.line());
        }
        all_ok &= r.ok;
        reports.push(r.to_value());
    }
    if let Some(out) = json_out {
        let doc = Value::Obj(Map::from_pairs([
            ("schema", Value::str("fidetype.sdk-rs.conformance/1")),
            ("sdk_version", Value::str(fidetype::SDK_VERSION)),
            ("reports", Value::Arr(reports)),
        ]));
        let text = repr(&doc) + "\n";
        if out == "-" {
            print!("{}", text);
        } else {
            std::fs::write(&out, text).map_err(|e| e.to_string())?;
        }
    }
    Ok(if all_ok { 0 } else { 1 })
}

fn validate(mut args: Vec<String>) -> Result<u8, String> {
    let level_s = take_opt(&mut args, "--level").unwrap_or_else(|| "core".into());
    let level = Level::parse(&level_s).filter(|l| *l != Level::Advisory).ok_or("--level must be core, trust-ready or provenance")?;
    let as_json = take_flag(&mut args, "--json");
    let file = args.first().ok_or("usage: fidetype-rs validate FILE [--level L] [--json]")?;
    let rep = io::check_stream_file(file, level).map_err(|e| e.to_string())?;
    if as_json {
        let doc = Value::Obj(Map::from_pairs([
            ("target", Value::str(file)),
            ("level_reached", rep.level.map_or(Value::Null, |l| Value::str(l.name()))),
            ("ok", Value::Bool(rep.ok)),
            ("checks", Value::Arr(rep.results.iter().map(|r| r.to_value()).collect())),
        ]));
        println!("{}", repr(&doc));
    } else {
        for r in rep.results.iter().filter(|r| r.status == Status::Fail) {
            let tag = if r.level == Level::Advisory { "WARN" } else { "FAIL" };
            println!("  {} {:<22} [{} {}] {}", tag, r.id, r.keyword, r.clause, r.message);
        }
        println!(
            "{}: {} (level {}; highest level reached: {})",
            file,
            if rep.ok { "PASS" } else { "FAIL" },
            level_s,
            rep.level.map_or("none", |l| l.name())
        );
    }
    Ok(if rep.ok { 0 } else { 1 })
}

fn consume(mut args: Vec<String>) -> Result<u8, String> {
    let profile = take_opt(&mut args, "--profile").unwrap_or_else(|| "v0.1".into());
    let consumer = consumer_for(&profile).ok_or("usage: fidetype-rs consume [--profile NAME] FILE")?;
    let file = args.first().ok_or("usage: fidetype-rs consume [--profile NAME] FILE")?;
    let p = Path::new(file);
    let name = p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let bytes = io::read_bytes(p).map_err(|e| e.to_string())?;
    match consumer(&name, &bytes) {
        Ok(v) => {
            println!("{}", repr(&v));
            Ok(0)
        }
        Err(e) => {
            eprintln!("{}", e);
            Ok(1)
        }
    }
}

fn decisions(args: Vec<String>) -> Result<u8, String> {
    let file = args.first().ok_or("usage: fidetype-rs decisions FILE")?;
    let mut bad = 0;
    for d in io::handle_decision_file(file).map_err(|e| e.to_string())? {
        let e = &d.event;
        let seq = match e.get("seq") {
            Value::Null => "?".to_string(),
            v => repr(v),
        };
        let who = format!("{}#{}", e.get("session").as_str().unwrap_or(""), seq);
        let action = repr(e.get("action"));
        let what = match d.kind {
            DecisionKind::Commit => format!("COMMIT {}", d.committed.as_deref().map_or("null".to_string(), |c| format!("{:?}", c))),
            DecisionKind::Preview => format!("preview {} (not final: do not act)", action),
            _ => format!("{} {}", action, if d.offered.is_empty() { String::new() } else { format!("{:?}", d.offered) }),
        };
        println!("{:<10} {}{}", who, what, if d.forward { "  -> forward" } else { "" });
        for w in &d.warnings {
            println!("           warning: {}", w);
        }
        for x in &d.errors {
            println!("           error: {}", x);
        }
        if !d.errors.is_empty() {
            bad += 1;
        }
    }
    Ok(if bad > 0 { 1 } else { 0 })
}

fn main() -> ExitCode {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: fidetype-rs <conformance|validate|consume|decisions> ...");
        return ExitCode::from(2);
    }
    let cmd = args.remove(0);
    let r = match cmd.as_str() {
        "conformance" => conformance(args),
        "validate" => validate(args),
        "consume" => consume(args),
        "decisions" => decisions(args),
        _ => {
            eprintln!("usage: fidetype-rs <conformance|validate|consume|decisions> ...");
            return ExitCode::from(2);
        }
    };
    match r {
        Ok(c) => ExitCode::from(c),
        Err(e) => {
            eprintln!("fidetype-rs: {}", e);
            ExitCode::from(2)
        }
    }
}
