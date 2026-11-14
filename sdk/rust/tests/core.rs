//! Writer, readers, checks and the decision tracker.

use fidetype::checks::{load_stream, Level};
use fidetype::json::{parse_json, Map, Value};
use fidetype::npz::{write_npz, NpyData};
use fidetype::reader::{parse_nts_text, EventReader, LineSplitter};
use fidetype::trust::{blank_candidate_warning, empty_commit_warning, handle_decisions, DecisionKind, DecisionTracker};
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

#[test]
fn spec_versions_of_1x_are_accepted() {
    use fidetype::constants::is_supported_spec_version;
    for v in ["0.1", "1.0", "1.3", "1.10"] {
        assert!(is_supported_spec_version(v), "{}", v);
    }
    for v in ["2.0", "1.0.0", "01.0", "1.01", "0.2", "1.", "1", ""] {
        assert!(!is_supported_spec_version(v), "{}", v);
    }
    let ok = sample_stream().replacen("\"spec_version\":\"0.1\"", "\"spec_version\":\"1.0\"", 1);
    assert!(load_stream("x.jsonl", ok.as_bytes()).is_ok());
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
fn decision_tracker_blank_candidates_td12() {
    let evs = vec![
        td(r#""seq":0,"utterance":0,"is_final":true,"action":"OFFER","shown":["","ab"," \u00a0"],"spec_version":"1.0""#),
        td(r#""seq":1,"utterance":1,"is_final":true,"action":"ASK","shown":["\t"],"spec_version":"1.0""#),
        td(r#""seq":2,"utterance":2,"is_final":true,"action":"OFFER","shown":["","cd"]"#), // 0.1 rules: no warning, still dropped
        td(r#""seq":3,"utterance":3,"is_final":true,"action":"OFFER_WORDS","shown":["ef"],"spec_version":"1.0""#),
    ];
    let d = handle_decisions(&evs);
    let offered: Vec<Vec<String>> = d.iter().map(|x| x.offered.clone()).collect();
    assert_eq!(offered, vec![vec!["ab".to_string()], vec![], vec!["cd".to_string()], vec!["ef".to_string()]]);
    assert_eq!(d.iter().map(|x| x.warnings.len()).collect::<Vec<_>>(), vec![1, 1, 0, 0]);
    assert!(d[0].warnings[0].contains("TD-12") && d[0].warnings[0].contains("2 blank candidate"));
    assert!(d.iter().all(|x| x.errors.is_empty() && !x.forward));
    assert!(blank_candidate_warning(&evs[2]).is_none());
    assert!(blank_candidate_warning(&evs[3]).is_none());
    // the fep-0001 consumer accepts with a warning (advisory FEP1-TD-SHOWN) and drops the blank texts
    let log = r#"{"type":"trust_decision","seq":0,"utterance":0,"is_final":true,"action":"OFFER","shown":["ab",""],"p_top1":0.9,"score_semantics":"calibrated_prob","spec_version":"1.0"}"#;
    let rep = fidetype::profiles::fep0001::check_file("x.jsonl", log.as_bytes());
    let c = rep.checks.iter().find(|c| c.id == "FEP1-TD-SHOWN").unwrap();
    assert_eq!(c.level, Level::Advisory);
    let v = fidetype::profiles::fep0001::consume("x.jsonl", log.as_bytes()).unwrap();
    assert_eq!(v.get("advisories").as_f64(), Some(1.0));
    match v.get("offered") {
        Value::Arr(a) => match a.as_slice() {
            [Value::Arr(b)] => assert!(b.len() == 1 && b[0].as_str() == Some("ab")),
            _ => panic!("offered: one list expected"),
        },
        _ => panic!("offered: a list expected"),
    }
}

#[test]
fn json_python_semantics() {
    let v = parse_json(r#"{"seq": 1.0, "n": 1}"#).unwrap();
    assert!(!v.get("seq").is_int());
    assert!(v.get("n").is_int());
    assert!(parse_json("[NaN]").is_err());
    assert!(fidetype::json::py_eq(&parse_json("[1, true]").unwrap(), &parse_json("[1.0, 1]").unwrap()));
}

#[test]
fn ws_ingest_core_order_gap_resume() {
    use fidetype::ws::{IngestCore, IngestSettings, WsData, WS_SUBPROTOCOL};
    let mut core = IngestCore::new(IngestSettings::default(), None);
    let txt = |s: &str| WsData::Text(s.to_string());
    assert!(core.open(1.0, &[WS_SUBPROTOCOL], None).closes.is_empty());
    let hdr = r#"{"type":"header","spec_version":"0.1","source":"x","vocab":["_","a"],"blank_id":0,"ws":{"stream_id":"s1"}}"#;
    let eff = core.message(1.0, txt(hdr), 0.0);
    assert_eq!(eff.sends[0].1.get("type").as_str(), Some("ws_welcome"));
    // ws_seq 2 arrives before 1: held, then released in order.
    core.message(1.0, txt(r#"{"type":"frame","t":0.04,"log_probs":[0,-9],"ws_seq":2}"#), 0.01);
    let eff = core.message(1.0, txt(r#"{"type":"frame","t":0.0,"log_probs":[0,-9],"ws_seq":1}"#), 0.02);
    assert_eq!(eff.items.len(), 2);
    assert_eq!(core.stats.reordered, 1);
    // A duplicate is dropped; a hole times out after reorder_timeout_s (0.25 s) and becomes a gap.
    core.message(1.0, txt(r#"{"type":"frame","t":0.0,"log_probs":[0,-9],"ws_seq":1}"#), 0.03);
    assert_eq!(core.stats.duplicates, 1);
    core.message(1.0, txt(r#"{"type":"frame","t":0.2,"log_probs":[0,-9],"ws_seq":5}"#), 0.04);
    assert!(core.tick(0.2).items.is_empty());
    let eff = core.tick(0.3);
    assert_eq!(eff.items[0].1.get("status").as_str(), Some("gap"));
    assert_eq!(core.stats.missing_events, 2.0);
    // Break, resume on a new connection with the same header.
    core.disconnect(1.0, 0.4);
    core.open(2.0, &[WS_SUBPROTOCOL], None);
    let resume = hdr.replace(r#""stream_id":"s1""#, r#""stream_id":"s1","resume":true"#);
    let eff = core.message(2.0, txt(&resume), 0.5);
    assert_eq!(eff.sends[0].1.get("resumed").as_bool(), Some(true));
    assert_eq!(eff.sends[0].1.get("seq").as_f64(), Some(5.0));
    // A binary message is refused with 1003.
    assert_eq!(core.message(2.0, WsData::Binary, 0.6).closes[0].1, 1003);
}

fn obj(s: &str) -> Map {
    match parse_json(s).unwrap() {
        Value::Obj(m) => m,
        _ => unreachable!(),
    }
}

/// A control decision: a COMMIT (attenuate) on `tick` with `extra` fields replacing the defaults.
fn cd(seq: u32, tick: u32, extra: &str) -> Map {
    let mut m = obj(&format!(
        r#"{{"type":"trust_decision","profile":"control","session":"c","seq":{},"tick":{},"is_final":true,"action":"COMMIT","state":"attenuate","velocity":[30,-9],"raw":[40,-12],"gain":0.75,"units":"mm/s","reasons":["shrunk"],"p_top1":null,"score_semantics":"none","engagement":1,"v_max":400,"ttl_s":0.06}}"#,
        seq, tick
    ));
    if !extra.is_empty() {
        for (k, v) in obj(&format!("{{{}}}", extra)).iter() {
            m.insert(k, v.clone());
        }
    }
    m
}

fn hold(seq: u32, tick: u32, extra: &str) -> Map {
    let base = r#""action":"ABSTAIN","state":"hold","velocity":[0,0],"gain":0,"reasons":["uncertain"]"#;
    let mut m = cd(seq, tick, base);
    if !extra.is_empty() {
        for (k, v) in obj(&format!("{{{}}}", extra)).iter() {
            m.insert(k, v.clone());
        }
    }
    m
}

fn click(seq: u32, session: &str) -> Map {
    obj(&format!(
        r#"{{"type":"trust_decision","profile":"intent","session":"{}","seq":{},"unit":0,"is_final":true,"action":"COMMIT","intent":"intent.click","risk_class":"undoable","p_top1":0.97,"score_semantics":"calibrated_prob"}}"#,
        session, seq
    ))
}

const STOP: &str = r#""state":"stop","reasons":["disengaged"]"#;
const NOT_ENGAGED: &str = r#""reasons":["not_engaged"],"engagement":0"#;

#[test]
fn decision_tracker_control_decisions() {
    let d = handle_decisions(&[
        hold(0, 0, NOT_ENGAGED),
        cd(1, 1, ""),
        hold(2, 1, r#""reasons":["stale_input"]"#), // a HOLD may repeat the last tick
        cd(3, 2, r#""state":"act","gain":1,"velocity":[40,-12],"reasons":["ok"]"#),
        hold(4, 2, STOP),
    ]);
    assert!(d.iter().all(|x| x.errors.is_empty()), "{:?}", d.iter().map(|x| &x.errors).collect::<Vec<_>>());
    let kinds: Vec<_> = d.iter().map(|x| x.kind).collect();
    use DecisionKind::*;
    assert_eq!(kinds, [Abstain, Commit, Abstain, Commit, Abstain]);
    assert!(d.iter().all(|x| x.profile == "control" && x.committed.is_none() && x.offered.is_empty()));
    let moving: Vec<f64> = d.iter().filter(|x| x.forward).map(|x| x.tick.unwrap()).collect();
    assert_eq!(moving, [1.0, 2.0]);
}

#[test]
fn decision_tracker_control_order() {
    let mut t = DecisionTracker::new();
    assert!(t.push(&cd(0, 4, "")).errors.is_empty());
    let twice = t.push(&cd(1, 4, ""));
    assert_eq!(twice.kind, DecisionKind::Invalid);
    assert!(!twice.forward);
    assert!(twice.errors.iter().any(|e| e.contains("second moving decision for tick 4")));
    assert!(t.push(&hold(2, 3, "")).errors.iter().any(|e| e.contains("tick 3 goes back")));
    // seq is shared with the intent profile
    assert!(t.push(&click(2, "c")).errors.iter().any(|e| e.contains("seq 2 does not increase")));
    let p = handle_decisions(&[cd(0, 0, r#""is_final":false"#)]);
    assert_eq!(p[0].kind, DecisionKind::Invalid);
    assert!(p[0].errors.iter().any(|e| e.contains("MUST be final")));
}

#[test]
fn decision_tracker_control_safety() {
    let d = handle_decisions(&[
        hold(0, 0, r#""velocity":[3,0]"#),
        cd(1, 1, r#""velocity":[400,300],"raw":[400,300],"gain":1,"state":"act""#),
        hold(2, 1, STOP),
        cd(3, 2, ""),
        cd(4, 3, r#""engagement":2"#),
    ]);
    assert!(d[0].errors.iter().any(|e| e.contains("non-zero velocity")));
    assert!(d[1].errors.iter().any(|e| e.contains("above v_max")));
    assert!(d[3].errors.iter().any(|e| e.contains("motion after a stop without a new engagement")));
    assert!(d[4].errors.is_empty());
    assert!(d[4].forward);
}

#[test]
fn decision_tracker_ctl_s7_intent_commit_needs_an_engaged_control() {
    let before = handle_decisions(&[hold(0, 0, NOT_ENGAGED), click(1, "c")]);
    assert_eq!(before[1].kind, DecisionKind::Invalid);
    assert!(!before[1].forward);
    assert!(before[1].errors.iter().any(|e| e.contains("not engaged (rule 7)")));
    let stopped = handle_decisions(&[cd(0, 0, ""), hold(1, 0, STOP), click(2, "c")]);
    assert!(stopped[2].errors.iter().any(|e| e.contains("not engaged")));
    let engaged = handle_decisions(&[cd(0, 0, ""), click(1, "c")]);
    assert!(engaged[1].errors.is_empty());
    assert_eq!(engaged[1].committed.as_deref(), Some("intent.click"));
    let reengaged = handle_decisions(&[hold(0, 0, STOP), hold(1, 1, r#""engagement":2"#), click(2, "c")]);
    assert!(reengaged[2].errors.is_empty(), "{:?}", reengaged[2].errors);
    // Only past decisions count: no control decision yet in the session, no CTL-S7 check.
    assert!(handle_decisions(&[click(0, "c"), hold(1, 0, NOT_ENGAGED)])[0].errors.is_empty());
    // Another session is not affected.
    assert!(handle_decisions(&[hold(0, 0, NOT_ENGAGED), click(1, "other")])[1].errors.is_empty());
}

#[test]
fn fep0005_safety_ctl_s7_and_engaged_after() {
    use fidetype::profiles::fep0005::{engaged_after, safety_errors};
    assert!(safety_errors(&[hold(0, 0, NOT_ENGAGED), click(1, "c")]).iter().any(|e| e.contains("not engaged (rule 7)")));
    assert!(safety_errors(&[cd(0, 0, ""), click(1, "c")]).is_empty());
    assert_eq!(engaged_after(&hold(0, 0, r#""state":"stop","engagement":3"#), None), (false, Some(3.0)));
    assert_eq!(engaged_after(&hold(0, 0, r#""engagement":3"#), Some(3.0)), (false, Some(3.0)));
    assert_eq!(engaged_after(&hold(0, 0, r#""engagement":4"#), Some(3.0)), (true, None));
    assert_eq!(engaged_after(&hold(0, 0, r#""engagement":1,"reasons":["disengaged"]"#), None), (false, None));
}
