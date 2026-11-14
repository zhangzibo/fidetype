//! Writer, readers, checks and the decision tracker.

use fidetype::checks::{load_stream, Level};
use fidetype::json::{parse_json, Map, Value};
use fidetype::npz::{write_npz, NpyData};
use fidetype::reader::{parse_nts_text, EventReader, LineSplitter};
use fidetype::trust::{empty_commit_warning, handle_decisions, DecisionKind, DecisionTracker};
use fidetype::validate::{PushResult, StreamValidator};
use fidetype::writer::{to_jsonl, NbestItem, NtsWriter, WriterOptions};
use fidetype::{check_stream, ErrorKind};

fn opts() -> WriterOptions {
    let mut o = WriterOptions::new("acme-decoder");
    o.frame_period = Some(0.04);
    o.meta = Map::from_pairs([
        ("device.modality", Value::str("emg")),
        ("decoder.causal", Value::Bool(true)),
        ("data.derived", Value::Bool(true)),
        ("language", Value::str("en")),
    ]);
    o
}

fn row(hot: usize) -> Vec<f64> {
    let mut p = vec![0.1 / 27.0; 28];
    p[hot] = 0.9;
    p.into_iter().map(f64::ln).collect()
}

fn sample_stream() -> String {
    to_jsonl(opts(), |w| {
        for (k, hot) in [8usize, 0, 9, 0].iter().enumerate() {
            w.frame_log_probs(k as f64 * 0.04, &row(*hot))?;
        }
        let mut it = NbestItem::new("hi", -1.2);
        it.char_confidences = Some(vec![0.9, 0.7]);
        w.hypothesis(&[it], true, None, "none", Some((0.0, 0.16)))?;
        w.segment_end(Some(0.16), Some("utterance"))?;
        Ok(())
    })
    .unwrap()
}

#[test]
fn writer_output_is_accepted_and_trust_ready() {
    let text = sample_stream();
    let s = load_stream("w.jsonl", text.as_bytes()).unwrap();
    assert_eq!(s.summary.get("n_frames").as_f64(), Some(4.0));
    assert_eq!(s.summary.get("events").as_f64(), Some(1.0)); // the hypothesis
    let rep = check_stream("w.jsonl", text.as_bytes(), Level::TrustReady).unwrap();
    assert!(rep.ok, "{:?}", rep.failures);
    assert_eq!(rep.level, Some(Level::TrustReady));
    // FEP-0001 consumer too (segment_end, evidence fields)
    let v = fidetype::profiles::fep0001::consume("w.jsonl", text.as_bytes()).unwrap();
    assert_eq!(v.get("segments").as_f64(), Some(1.0));
    assert_eq!(v.get("evidence_items").as_f64(), Some(1.0));
}

#[test]
fn writer_refuses_bad_input() {
    let mut lines = Vec::new();
    let mut w = NtsWriter::new(|l: &str| lines.push(l.to_string()), opts()).unwrap();
    assert_eq!(w.frame_log_probs(0.0, &[0.0; 3]).unwrap_err().kind, ErrorKind::Usage); // wrong width
    assert!(w.frame_probs(0.0, &[0.5; 28]).is_err()); // not normalised
    w.frame_logits(0.0, &[1.0; 28]).unwrap(); // log-softmax applied
    assert!(w.frame_logits(0.0, &[1.0; 28]).is_err()); // time does not increase
    assert!(w.hypothesis(&[NbestItem::new("a", f64::NAN)], true, None, "none", None).is_err());
    w.end().unwrap();
    assert!(w.segment_end(None, None).is_err());
    drop(w);
    assert_eq!(lines.len(), 3); // header, frame, end
    let mut bad = WriterOptions::new("x");
    bad.vocab = Some(vec!["a".into(), "a".into()]);
    assert!(NtsWriter::new(|_: &str| {}, bad).is_err());
}

#[test]
fn writer_floats_stay_floats() {
    let text = sample_stream();
    let first = parse_nts_text(&text).unwrap();
    // frame t = 0.0 is written as a float literal, as Python json.dumps writes it
    assert!(text.lines().nth(1).unwrap().contains("\"t\":0.0"));
    assert_eq!(first[0].get("type").as_str(), Some("header"));
}

#[test]
fn streaming_validator_rules() {
    let text = sample_stream();
    let mut v = StreamValidator::new();
    let mut kinds = Vec::new();
    for line in text.lines() {
        kinds.push(v.push_text(line).unwrap().kind());
    }
    assert_eq!(kinds, ["header", "frame", "frame", "frame", "frame", "hypothesis", "segment_end", "end"]);
    assert!(matches!(v.push_text(r#"{"type":"frame","t":9}"#).unwrap(), PushResult::Ignored { .. }));

    let mut v = StreamValidator::new();
    assert!(v.push_text(r#"{"type":"frame","t":0}"#).is_err()); // before the header
    let head = text.lines().next().unwrap();
    v.push_text(head).unwrap();
    let frame = |t: &str| format!(r#"{{"type":"frame","t":{},"top_ids":[1],"top_log_probs":[0.0],"rest_log_prob":null}}"#, t);
    v.push_text(&frame("0.5")).unwrap();
    assert!(v.push_text(&frame("0.5")).is_err()); // t does not increase
    assert!(v.push_text(r#"{"type":"hypothesis","id":"h","is_final":true,"nbest":[{"text":"ab","score":0,"char_confidences":[1]}]}"#).is_err());
    assert!(v.push_text(r#"{"type":"hypothesis","id":"h","is_final":1.0,"nbest":[]}"#).is_err());
}

#[test]
fn event_reader_across_chunks() {
    let text = sample_stream().replace('\n', "\r\n");
    let bytes = text.as_bytes();
    let mut r = EventReader::new();
    let mut n = 0;
    for chunk in bytes.chunks(7) {
        n += r.push(chunk).unwrap().len();
    }
    n += r.finish().unwrap().len();
    assert_eq!(n, 8);
    // UTF-8 split across chunks
    let mut s = LineSplitter::new();
    let e = "é\n".as_bytes();
    assert!(s.push(&e[..1]).unwrap().is_empty());
    assert_eq!(s.push(&e[1..]).unwrap(), ["é"]);
    assert!(LineSplitter::new().push(&[0xff, b'\n']).is_err());
}

#[test]
fn npz_writer_roundtrip_through_the_consumer() {
    let lp: Vec<f32> = [row(1), row(2)].concat().into_iter().map(|x| x as f32).collect();
    let vocab: Vec<String> = fidetype::constants::VOCAB.iter().map(|s| s.to_string()).collect();
    let z = write_npz(&[
        ("version", NpyData::Str { shape: vec![], data: vec!["0.1".into()] }),
        ("log_probs", NpyData::F32 { shape: vec![2, 28], data: lp }),
        ("frame_times", NpyData::F64 { shape: vec![2], data: vec![0.0, 0.04] }),
        ("vocab", NpyData::Str { shape: vec![28], data: vocab }),
        ("vocab_type", NpyData::Str { shape: vec![], data: vec!["char".into()] }),
        ("blank_id", NpyData::I64 { shape: vec![], data: vec![0] }),
        ("source", NpyData::Str { shape: vec![], data: vec!["acme".into()] }),
        ("meta_json", NpyData::Str { shape: vec![], data: vec![r#"{"data.derived": true}"#.into()] }),
    ]);
    let s = load_stream("s.npz", &z).unwrap();
    assert_eq!(s.summary.get("n_frames").as_f64(), Some(2.0));
    assert_eq!(s.summary.get("vocab_size").as_f64(), Some(28.0));
    assert_eq!(s.header.get("blank_id").as_f64(), Some(0.0));
}

#[test]
fn rejections_carry_the_clause() {
    let bad = sample_stream().replacen("\"spec_version\":\"0.1\"", "\"spec_version\":\"9.9\"", 1);
    let e = load_stream("x.jsonl", bad.as_bytes()).unwrap_err();
    assert_eq!(e.kind, ErrorKind::Rejected);
    assert_eq!(e.check_id, "NTS-VERSION");
    assert_eq!(e.clause, "5.1.4");
    assert!(load_stream("x.txt", b"").is_err());
}

fn td(extra: &str) -> Map {
    let base = r#"{"type":"trust_decision","session":"s","p_top1":0.9,"score_semantics":"calibrated_prob""#;
    match parse_json(&format!("{},{}}}", base, extra)).unwrap() {
        Value::Obj(m) => m,
        _ => unreachable!(),
    }
}

#[test]
fn decision_tracker_rules() {
    let evs = vec![
        td(r#""seq":0,"utterance":0,"is_final":false,"action":"COMMIT","shown":["he"]"#),
        td(r#""seq":1,"utterance":0,"is_final":true,"action":"COMMIT","shown":["hello"]"#),
        td(r#""seq":2,"utterance":0,"is_final":true,"action":"COMMIT","shown":["again"]"#), // after the final one
        td(r#""seq":2,"utterance":1,"is_final":true,"action":"OFFER","shown":["a","b"]"#), // seq does not increase
        td(r#""seq":4,"utterance":2,"is_final":true,"action":"COMMIT","shown":["  "]"#), // rule 9
        td(r#""seq":5.0,"utterance":3,"is_final":true,"action":"ABSTAIN""#), // 5.0 is not an integer
    ];
    let d = handle_decisions(&evs);
    assert_eq!(d[0].kind, DecisionKind::Preview);
    assert!(!d[0].forward);
    assert_eq!(d[1].kind, DecisionKind::Commit);
    assert!(d[1].forward);
    assert_eq!(d[1].committed.as_deref(), Some("hello"));
    assert_eq!(d[2].kind, DecisionKind::Invalid);
    assert!(d[2].errors[0].contains("after its final one"));
    assert!(d[3].errors.iter().any(|e| e.contains("does not increase")));
    assert_eq!(d[4].kind, DecisionKind::Commit);
    assert!(!d[4].forward);
    assert!(d[4].warnings[0].contains("rule 9"));
    assert!(empty_commit_warning(&evs[4]).is_some());
    assert!(d[5].errors.iter().any(|e| e.contains("seq must be an integer")));

    let mut t = DecisionTracker::new();
    let x = t.push_text("not json");
    assert_eq!(x.kind, DecisionKind::Invalid);
    let i = t.push(&td(r#""profile":"intent","seq":0,"unit":0,"is_final":true,"action":"COMMIT","intent":"open","risk_class":"safe""#));
    assert_eq!(i.kind, DecisionKind::Commit);
    assert_eq!(i.committed.as_deref(), Some("open"));
    assert!(i.forward);
}

#[test]
fn json_python_semantics() {
    let v = parse_json(r#"{"seq": 1.0, "n": 1}"#).unwrap();
    assert!(!v.get("seq").is_int());
    assert!(v.get("n").is_int());
    assert!(parse_json("[NaN]").is_err());
    assert!(fidetype::json::py_eq(&parse_json("[1, true]").unwrap(), &parse_json("[1.0, 1]").unwrap()));
}
