//! NeuralTextStream over WebSocket (FEP-0004, binding `nts-ws/0.1`,
//! subprotocol `nts-ws.0.1`): a port of the sans-IO parts of
//! `fidetype.adapters.ws` (and of `sdk/typescript/src/ws.ts`).
//!
//! - [`IngestCore`]: the server side of `/nts` without I/O (handshake,
//!   header, `ws_seq` order, reorder hold, gaps, batches, resume, take-over,
//!   acks, refusals).
//! - [`SubscriberCore`]: the checks of a `/decisions` subscriber (welcome,
//!   `ws_seq` gaps, duplicates, FEP-0001 rules).
//!
//! No networking: the caller feeds connection events and messages and
//! applies the returned [`Effects`]. `no_std` + `alloc`.
//!
//! Connection ids and `ws_seq` values are `f64`, as in the JSON model of
//! this SDK (the reference accepts any JSON integer).

use alloc::boxed::Box;
use alloc::format;
use alloc::string::{String, ToString};
use alloc::vec::Vec;

use crate::error::Error;
use crate::json::{cp_len, parse_json, py_eq, py_strip, repr, Map, Value};
use crate::profiles::fep0001::{acted_texts, td_final_errors, td_format_errors};

pub const WS_BINDING_VERSION: &str = "nts-ws/0.1";
pub const WS_SUBPROTOCOL: &str = "nts-ws.0.1";
pub const WS_KNOWN_BINDINGS: &[&str] = &[WS_BINDING_VERSION];
pub const WS_PATH_INGEST: &str = "/nts";
pub const WS_PATH_DECISIONS: &str = "/decisions";
pub const WS_PATH_EVENTS: &str = "/events";
/// Close codes that refuse a connection (section 9).
pub const WS_REFUSAL_CODES: &[u32] = &[1002, 1003, 1007, 1008, 1009, 4000];
/// Close code of a connection that a newer connection took over (section 8).
pub const WS_TAKEN_OVER: u32 = 4001;
const MAX_MESSAGE_BYTES: usize = 1 << 20;
const MAX_STREAM_ID: usize = 128;
const SPEC: &str = "0.1";

/// Python `json.loads(text, parse_constant=reject)` + "a JSON object with a string type".
pub fn parse_ws_message(text: &str) -> Result<Map, Error> {
    match parse_json(text)? {
        Value::Obj(m) if m.get("type").is_str() => Ok(m),
        _ => Err(Error::value("a message must be a JSON object with a string type")),
    }
}

// --- input side ------------------------------------------------------------------------------

/// The settings of [`IngestCore`] (section 6 and 8 defaults).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct IngestSettings {
    pub reorder_window: f64,
    pub reorder_timeout_s: f64,
    pub resume_timeout_s: f64,
    pub max_batch: f64,
    pub ack_every: f64,
    pub window: f64,
    pub ack_interval_s: f64,
}

impl Default for IngestSettings {
    fn default() -> Self {
        IngestSettings {
            reorder_window: 16.0,
            reorder_timeout_s: 0.25,
            resume_timeout_s: 10.0,
            max_batch: 1024.0,
            ack_every: 64.0,
            window: 4096.0,
            ack_interval_s: 0.1,
        }
    }
}

const SETTING_NAMES: &[&str] = &["reorder_window", "reorder_timeout_s", "resume_timeout_s", "max_batch", "ack_every", "window", "ack_interval_s"];

impl IngestSettings {
    /// Settings from a JSON object (unknown keys and bad values are errors, as the Python dataclass).
    pub fn from_map(o: &Map) -> Result<Self, Error> {
        let mut s = IngestSettings::default();
        if let Some(k) = o.keys().find(|k| !SETTING_NAMES.contains(k)) {
            return Err(Error::type_err(format!("unknown setting {}", k)));
        }
        let num = |k: &str, d: f64| -> Value { o.get_opt(k).cloned().unwrap_or(Value::int(d)) };
        let rw = num("reorder_window", s.reorder_window);
        if !(rw.is_int() && rw.as_f64().unwrap_or(-1.0) >= 0.0) {
            return Err(Error::value("reorder_window must be an integer >= 0"));
        }
        s.reorder_window = rw.as_f64().unwrap_or(0.0);
        for (k, slot) in [
            ("reorder_timeout_s", &mut s.reorder_timeout_s),
            ("resume_timeout_s", &mut s.resume_timeout_s),
            ("ack_interval_s", &mut s.ack_interval_s),
        ] {
            let v = o.get_opt(k).cloned().unwrap_or(Value::float(*slot));
            match v {
                Value::Num(x, _) if x.is_finite() && x >= 0.0 => *slot = x,
                _ => return Err(Error::value(format!("{} must be a number >= 0", k))),
            }
        }
        for (k, slot) in [("max_batch", &mut s.max_batch), ("ack_every", &mut s.ack_every), ("window", &mut s.window)] {
            let v = o.get_opt(k).cloned().unwrap_or(Value::int(*slot));
            if !(v.is_int() && v.as_f64().unwrap_or(0.0) >= 1.0) {
                return Err(Error::value(format!("{} must be an integer >= 1", k)));
            }
            *slot = v.as_f64().unwrap_or(1.0);
        }
        Ok(s)
    }
}

/// A message to the core.
#[derive(Debug, Clone)]
pub enum WsData {
    /// A text message.
    Text(String),
    /// A binary message (always refused).
    Binary,
    /// An already parsed JSON value (a string value is read as a text message).
    Value(Value),
}

/// What the caller must do after a call: send messages, hand items to the trust layer, close connections.
#[derive(Debug, Clone, Default)]
pub struct Effects {
    /// (connection, message)
    pub sends: Vec<(f64, Map)>,
    /// (stream id, NTS event or `ws_status` item)
    pub items: Vec<(String, Map)>,
    /// (connection, close code, reason)
    pub closes: Vec<(f64, u32, String)>,
}

impl Effects {
    fn extend(&mut self, b: Effects) {
        self.sends.extend(b.sends);
        self.items.extend(b.items);
        self.closes.extend(b.closes);
    }
}

/// The counters of [`IngestCore`].
#[derive(Debug, Clone, Default, PartialEq)]
pub struct IngestStats {
    pub streams: usize,
    pub messages: usize,
    pub events: usize,
    pub duplicates: usize,
    pub reordered: usize,
    pub gaps: usize,
    /// Missing `ws_seq` values (JSON integers, so `f64`).
    pub missing_events: f64,
    pub resumes: usize,
    pub takeovers: usize,
    pub lost_streams: usize,
    pub ignored_controls: usize,
    pub refused: usize,
}

#[derive(Debug, Clone)]
struct Conn {
    cid: f64,
    authed: bool,
    stream_id: Option<String>,
    open: bool,
}

#[derive(Debug, Clone)]
struct Stream {
    sid: String,
    header: Map,
    conn: Option<f64>,
    expected: f64,
    /// (ws_seq, event, arrival time)
    held: Vec<(f64, Map, f64)>,
    since_ack: f64,
    last_ack_at: f64,
    ended: bool,
    disconnected_at: Option<f64>,
}

impl Stream {
    fn held_has(&self, seq: f64) -> bool {
        self.held.iter().any(|h| h.0 == seq)
    }
    fn take_held(&mut self, seq: f64) -> Option<Map> {
        let i = self.held.iter().position(|h| h.0 == seq)?;
        Some(self.held.remove(i).1)
    }
}

/// The token check of the auth hook: `Some(token)` or `None` -> accept?
pub type AuthFn = Box<dyn Fn(Option<&str>) -> bool>;

/// The server side of `/nts` without I/O (port of `fidetype.adapters.ws.IngestCore`).
pub struct IngestCore {
    pub settings: IngestSettings,
    pub stats: IngestStats,
    auth: Option<AuthFn>,
    conns: Vec<Conn>,
    /// Insertion order (Python `dict`): a replaced stream keeps its place.
    streams: Vec<Stream>,
    anon: u64,
}

fn status(sid: &str, st: &str) -> Map {
    Map::from_pairs([("type", Value::str("ws_status")), ("status", Value::str(st)), ("stream", Value::str(sid))])
}

impl IngestCore {
    pub fn new(settings: IngestSettings, auth: Option<AuthFn>) -> Self {
        IngestCore { settings, stats: IngestStats::default(), auth, conns: Vec::new(), streams: Vec::new(), anon: 1 }
    }

    fn conn_idx(&self, cid: f64) -> Option<usize> {
        self.conns.iter().position(|c| c.cid == cid)
    }
    fn stream_idx(&self, sid: &str) -> Option<usize> {
        self.streams.iter().position(|s| s.sid == sid)
    }
    fn check_auth(&self, tok: Option<&str>) -> bool {
        match &self.auth {
            Some(f) => f(tok),
            None => true,
        }
    }

    /// A new connection with its offered subprotocols and `Authorization` header.
    pub fn open(&mut self, cid: f64, subprotocols: &[&str], authorization: Option<&str>) -> Effects {
        let mut eff = Effects::default();
        let ok = subprotocols.contains(&WS_SUBPROTOCOL);
        let authed = ok && (self.auth.is_none() || bearer_token(authorization).map_or(false, |t| self.check_auth(Some(t))));
        let conn = Conn { cid, authed, stream_id: None, open: ok };
        match self.conn_idx(cid) {
            Some(i) => self.conns[i] = conn,
            None => self.conns.push(conn),
        }
        if !ok {
            self.stats.refused += 1;
            eff.closes.push((cid, 1002, format!("subprotocol {} not offered", WS_SUBPROTOCOL)));
        }
        eff
    }

    fn refuse(&mut self, cid: f64, close: u32, code: &str, detail: &str, now: f64) -> Effects {
        let mut eff = Effects::default();
        eff.sends.push((cid, Map::from_pairs([("type", Value::str("ws_error")), ("code", Value::str(code)), ("detail", Value::str(detail))])));
        eff.closes.push((cid, close, code.to_string()));
        self.stats.refused += 1;
        eff.extend(self.disconnect(cid, now));
        eff
    }

    /// One message on connection `cid` at time `now`.
    pub fn message(&mut self, cid: f64, data: WsData, now: f64) -> Effects {
        let ci = match self.conn_idx(cid) {
            Some(i) if self.conns[i].open => i,
            _ => return Effects::default(),
        };
        self.stats.messages += 1;
        let text: Option<String> = match &data {
            WsData::Binary => return self.refuse(cid, 1003, "binary", "binary messages are not allowed (section 3 rule 1)", now),
            WsData::Text(t) => Some(t.clone()),
            WsData::Value(Value::Str(t)) => Some(t.clone()),
            WsData::Value(_) => None,
        };
        let m: Map = match text {
            Some(t) => {
                if t.len() > MAX_MESSAGE_BYTES {
                    return self.refuse(cid, 1009, "too_big", "message larger than 1 MiB", now);
                }
                match parse_ws_message(&t) {
                    Ok(m) => m,
                    Err(e) => {
                        let d: String = e.message.chars().take(200).collect();
                        return self.refuse(cid, 1007, "bad_message", &d, now);
                    }
                }
            }
            None => match data {
                WsData::Value(Value::Obj(m)) if m.get("type").is_str() => m,
                _ => return self.refuse(cid, 1007, "bad_message", "a message must be a JSON object with a string type", now),
            },
        };
        let typ = m.get("type").as_str().unwrap_or("").to_string();
        if !self.conns[ci].authed {
            if typ == "ws_auth" && self.auth.is_some() && self.check_auth(m.get("token").as_str()) {
                self.conns[ci].authed = true;
                return Effects::default();
            }
            return self.refuse(cid, 1008, "auth", "authentication failed or missing (section 8)", now);
        }
        if typ == "ws_auth" {
            if self.conns[ci].stream_id.is_some() {
                self.stats.ignored_controls += 1;
            }
            return Effects::default();
        }
        let sid = match &self.conns[ci].stream_id {
            None => {
                if typ != "header" {
                    return self.refuse(cid, 1007, "bad_header", "the first message must be the NTS header (section 5 rule 1)", now);
                }
                return self.open_stream(ci, m, now);
            }
            Some(s) => s.clone(),
        };
        let si = match self.stream_idx(&sid) {
            Some(i) if self.streams[i].conn == Some(cid) => i,
            _ => return Effects::default(),
        };
        if typ == "ws_batch" {
            return self.batch(cid, si, &m, now);
        }
        if typ.starts_with("ws_") {
            self.stats.ignored_controls += 1;
            return Effects::default();
        }
        if let Some(err) = seq_error(&Value::Obj(m.clone())) {
            return self.refuse(cid, 1007, "bad_seq", &err, now);
        }
        let mut eff = Effects::default();
        let (s, stats) = (self.settings, &mut self.stats);
        sequence(&mut self.streams[si], m, now, &mut eff, stats, &s);
        eff
    }

    fn batch(&mut self, cid: f64, si: usize, msg: &Map, now: f64) -> Effects {
        let evs = match msg.get("events") {
            Value::Arr(a) if !a.is_empty() => a.clone(),
            _ => return self.refuse(cid, 1007, "bad_batch", "ws_batch needs a non-empty events list", now),
        };
        if evs.len() as f64 > self.settings.max_batch {
            let d = format!("ws_batch of {} events > {}", evs.len(), crate::json::num_text(self.settings.max_batch));
            return self.refuse(cid, 1009, "too_big", &d, now);
        }
        for k in 0..evs.len() {
            if let Some(err) = seq_error(&evs[k]) {
                return self.refuse(cid, 1007, "bad_seq", &err, now);
            }
            if k > 0 && evs[k].get("ws_seq").as_f64() != evs[k - 1].get("ws_seq").as_f64().map(|x| x + 1.0) {
                return self.refuse(cid, 1007, "bad_batch", "the events of a batch must have consecutive ws_seq (section 6 rule 4)", now);
            }
        }
        let mut eff = Effects::default();
        let (s, stats) = (self.settings, &mut self.stats);
        for ev in evs {
            if let Value::Obj(m) = ev {
                sequence(&mut self.streams[si], m, now, &mut eff, stats, &s);
            }
        }
        eff
    }

    fn open_stream(&mut self, ci: usize, hdr: Map, now: f64) -> Effects {
        let cid = self.conns[ci].cid;
        let ws = match hdr.get_opt("ws") {
            None => Map::new(),
            Some(Value::Obj(m)) => m.clone(),
            Some(_) => return self.refuse(cid, 1007, "bad_header", "header ws must be an object", now),
        };
        let binding = ws.get_opt("binding").cloned().unwrap_or(Value::str(WS_BINDING_VERSION));
        if !matches!(&binding, Value::Str(b) if WS_KNOWN_BINDINGS.contains(&b.as_str())) {
            return self.refuse(cid, 4000, "binding", &format!("unknown binding {} (section 10)", repr(&binding)), now);
        }
        let id = match ws.get("stream_id") {
            Value::Null => {
                let s = format!("anon-{}", self.anon);
                self.anon += 1;
                s
            }
            Value::Str(s) if (1..=MAX_STREAM_ID).contains(&cp_len(s)) => s.clone(),
            _ => return self.refuse(cid, 1007, "bad_header", "ws.stream_id must be a string of 1-128 characters", now),
        };
        let resume = match ws.get_opt("resume") {
            None => false,
            Some(Value::Bool(b)) => *b,
            Some(_) => return self.refuse(cid, 1007, "bad_header", "ws.resume must be a boolean", now),
        };
        if hdr.get("spec_version").as_str() != Some(SPEC) {
            return self.refuse(cid, 1007, "bad_header", "spec_version is not '0.1'", now);
        }
        if hdr.has("ws_seq") {
            return self.refuse(cid, 1007, "bad_header", "the header has no ws_seq (section 6 rule 1)", now);
        }
        let mut core = hdr;
        core.remove("ws");
        let mut eff = Effects::default();
        let old = self.stream_idx(&id);
        if let (Some(oi), true) = (old, resume) {
            if !py_eq(&Value::Obj(self.streams[oi].header.clone()), &Value::Obj(core)) {
                return self.refuse(cid, 1007, "bad_header", "the resume header differs from the first header", now);
            }
            if let Some(oc) = self.streams[oi].conn {
                if oc != cid {
                    eff.extend(self.take_over(oc));
                }
            }
            let st = &mut self.streams[oi];
            st.conn = Some(cid);
            st.disconnected_at = None;
            st.last_ack_at = now;
            self.conns[ci].stream_id = Some(id.clone());
            self.stats.resumes += 1;
            let mut s = status(&id, "resumed");
            s.insert("seq", Value::int(st.expected - 1.0));
            eff.items.push((id.clone(), s));
            let w = self.welcome(oi, true);
            eff.sends.push((cid, w));
            return eff;
        }
        if let Some(oi) = old {
            if let Some(oc) = self.streams[oi].conn {
                if oc != cid {
                    eff.extend(self.take_over(oc));
                }
            }
            if !self.streams[oi].ended {
                eff.items.push((id.clone(), status(&id, "replaced")));
            }
        }
        let st = Stream {
            sid: id.clone(),
            header: core.clone(),
            conn: Some(cid),
            expected: 1.0,
            held: Vec::new(),
            since_ack: 0.0,
            last_ack_at: now,
            ended: false,
            disconnected_at: None,
        };
        let si = match old {
            Some(oi) => {
                self.streams[oi] = st;
                oi
            }
            None => {
                self.streams.push(st);
                self.streams.len() - 1
            }
        };
        self.conns[ci].stream_id = Some(id.clone());
        self.stats.streams += 1;
        eff.items.push((id.clone(), status(&id, "connected")));
        eff.items.push((id.clone(), core));
        let w = self.welcome(si, false);
        eff.sends.push((cid, w));
        eff
    }

    fn take_over(&mut self, old_cid: f64) -> Effects {
        let mut eff = Effects::default();
        if let Some(i) = self.conn_idx(old_cid) {
            if self.conns[i].open {
                self.conns[i].open = false;
                self.conns[i].stream_id = None;
                self.stats.takeovers += 1;
                eff.sends.push((
                    old_cid,
                    Map::from_pairs([
                        ("type", Value::str("ws_error")),
                        ("code", Value::str("taken_over")),
                        ("detail", Value::str("a newer connection resumed this stream")),
                    ]),
                ));
                eff.closes.push((old_cid, WS_TAKEN_OVER, "taken_over".to_string()));
            }
        }
        eff
    }

    fn welcome(&self, si: usize, resumed: bool) -> Map {
        let st = &self.streams[si];
        Map::from_pairs([
            ("type", Value::str("ws_welcome")),
            ("binding", Value::str(WS_BINDING_VERSION)),
            ("role", Value::str("ingest")),
            ("stream_id", Value::str(&st.sid)),
            ("seq", Value::int(st.expected - 1.0)),
            ("resumed", Value::Bool(resumed)),
            ("ack_every", Value::int(self.settings.ack_every)),
            ("window", Value::int(self.settings.window)),
        ])
    }

    /// Advance the clock: reorder time-outs (gaps), timed acks, resume time-outs.
    pub fn tick(&mut self, now: f64) -> Effects {
        let mut eff = Effects::default();
        let s = self.settings;
        let mut i = 0;
        while i < self.streams.len() {
            {
                let stats = &mut self.stats;
                let st = &mut self.streams[i];
                while !st.held.is_empty() && now - st.held.iter().map(|h| h.2).fold(f64::INFINITY, f64::min) >= s.reorder_timeout_s {
                    gap(st, &mut eff, stats, &s);
                }
                maybe_ack(st, &mut eff, Some(now), &s);
            }
            let st = &self.streams[i];
            if st.conn.is_none() && st.disconnected_at.map_or(false, |d| now - d >= s.resume_timeout_s) {
                self.lose(i, &mut eff, "resume time-out");
            } else {
                i += 1;
            }
        }
        eff
    }

    fn lose(&mut self, si: usize, eff: &mut Effects, why: &str) {
        self.stats.lost_streams += 1;
        let sid = self.streams[si].sid.clone();
        let mut s = status(&sid, "lost");
        s.insert("detail", Value::str(why));
        eff.items.push((sid, s));
        self.streams.remove(si);
    }

    /// The connection `cid` closed or broke at time `now`.
    pub fn disconnect(&mut self, cid: f64, now: f64) -> Effects {
        let mut eff = Effects::default();
        let conn = match self.conn_idx(cid) {
            Some(i) => self.conns.remove(i),
            None => return eff,
        };
        let sid = match conn.stream_id {
            Some(s) => s,
            None => return eff,
        };
        let si = match self.stream_idx(&sid) {
            Some(i) if self.streams[i].conn == Some(cid) => i,
            _ => return eff,
        };
        self.streams[si].conn = None;
        if self.streams[si].ended {
            eff.items.push((sid.clone(), status(&sid, "closed")));
            self.streams.remove(si);
        } else {
            self.streams[si].disconnected_at = Some(now);
            let mut s = status(&sid, "disconnected");
            s.insert("seq", Value::int(self.streams[si].expected - 1.0));
            eff.items.push((sid, s));
        }
        eff
    }

    /// Shut down: streams without a connection that did not end are lost.
    pub fn finish(&mut self) -> Effects {
        let mut eff = Effects::default();
        let mut i = 0;
        while i < self.streams.len() {
            if self.streams[i].conn.is_none() && !self.streams[i].ended {
                self.lose(i, &mut eff, "shutdown");
            } else {
                i += 1;
            }
        }
        eff
    }

    /// The ids of the streams with a live connection, in insertion order.
    pub fn live_streams(&self) -> Vec<String> {
        self.streams.iter().filter(|s| s.conn.is_some()).map(|s| s.sid.clone()).collect()
    }
}

fn sequence(st: &mut Stream, ev: Map, now: f64, eff: &mut Effects, stats: &mut IngestStats, s: &IngestSettings) {
    let seq = ev.get("ws_seq").as_f64().unwrap_or(0.0);
    if seq < st.expected || st.held_has(seq) {
        stats.duplicates += 1;
        return;
    }
    if seq == st.expected {
        release(st, ev, eff, stats, s);
        drain(st, eff, true, stats, s);
    } else {
        st.held.push((seq, ev, now));
        if st.held.len() as f64 > s.reorder_window {
            gap(st, eff, stats, s);
        }
    }
    maybe_ack(st, eff, None, s);
    if st.since_ack == 0.0 {
        st.last_ack_at = now;
    }
}

fn release(st: &mut Stream, ev: Map, eff: &mut Effects, stats: &mut IngestStats, s: &IngestSettings) {
    let end = ev.get("type").as_str() == Some("end");
    eff.items.push((st.sid.clone(), ev));
    st.expected += 1.0;
    st.since_ack += 1.0;
    stats.events += 1;
    if end {
        st.ended = true;
        st.since_ack = st.since_ack.max(s.ack_every);
    }
}

fn drain(st: &mut Stream, eff: &mut Effects, reordered: bool, stats: &mut IngestStats, s: &IngestSettings) {
    while let Some(ev) = st.take_held(st.expected) {
        if reordered {
            stats.reordered += 1;
        }
        release(st, ev, eff, stats, s);
    }
}

fn gap(st: &mut Stream, eff: &mut Effects, stats: &mut IngestStats, s: &IngestSettings) {
    let first = st.held.iter().map(|h| h.0).fold(f64::INFINITY, f64::min);
    let missing = first - st.expected;
    stats.gaps += 1;
    stats.missing_events += missing;
    let mut m = status(&st.sid, "gap");
    m.insert("seq_from", Value::int(st.expected));
    m.insert("seq_to", Value::int(first - 1.0));
    m.insert("missing", Value::int(missing));
    eff.items.push((st.sid.clone(), m));
    st.expected = first;
    drain(st, eff, false, stats, s);
}

fn maybe_ack(st: &mut Stream, eff: &mut Effects, now: Option<f64>, s: &IngestSettings) {
    let due = st.since_ack >= s.ack_every || now.map_or(false, |n| st.since_ack > 0.0 && n - st.last_ack_at >= s.ack_interval_s);
    if let (true, Some(c)) = (due, st.conn) {
        eff.sends.push((
            c,
            Map::from_pairs([("type", Value::str("ws_ack")), ("stream_id", Value::str(&st.sid)), ("seq", Value::int(st.expected - 1.0))]),
        ));
        st.since_ack = 0.0;
        if let Some(n) = now {
            st.last_ack_at = n;
        }
    }
}

fn seq_error(ev: &Value) -> Option<String> {
    let typ = match ev {
        Value::Obj(m) => match m.get("type") {
            Value::Str(t) => t,
            _ => return Some("a batch event must be a JSON object with a string type".to_string()),
        },
        _ => return Some("a batch event must be a JSON object with a string type".to_string()),
    };
    if typ.starts_with("ws_") {
        return Some(format!("control message {} inside a batch (section 6 rule 4)", repr(&Value::str(typ))));
    }
    let seq = ev.get("ws_seq");
    if !(seq.is_int() && seq.as_f64().unwrap_or(0.0) >= 1.0) {
        return Some("ws_seq must be an integer >= 1 (section 6 rule 1)".to_string());
    }
    None
}

/// The token of an `Authorization: Bearer <token>` value, or `None`.
pub fn bearer_token(authorization: Option<&str>) -> Option<&str> {
    let a = authorization?;
    let head: String = a.chars().take(7).collect();
    if head.to_lowercase() != "bearer " {
        return None;
    }
    let tok = py_strip(&a[head.len()..]);
    if tok.is_empty() {
        None
    } else {
        Some(tok)
    }
}

// --- subscriber side ---------------------------------------------------------------------------

/// The checks of a `/decisions` subscriber (port of `fidetype.adapters.ws.SubscriberCore`).
#[derive(Debug, Clone)]
pub struct SubscriberCore {
    pub from_seq: Option<f64>,
    pub last: f64,
    pub welcomed: bool,
    pub waiting: bool,
    pub events: Vec<Map>,
    pub duplicates: usize,
    pub gaps: Vec<f64>,
    pub missed: f64,
    pub errors: Vec<String>,
    pub ignored: usize,
}

fn sub_err(msg: impl Into<String>) -> Error {
    Error::value(msg)
}

impl SubscriberCore {
    /// `from_seq`: the `from_seq` of the first `ws_subscribe` (`None`: new decisions only).
    pub fn new(from_seq: Option<f64>) -> Self {
        SubscriberCore {
            from_seq,
            last: from_seq.map_or(0.0, |f| f - 1.0),
            welcomed: false,
            waiting: false,
            events: Vec::new(),
            duplicates: 0,
            gaps: Vec::new(),
            missed: 0.0,
            errors: Vec::new(),
            ignored: 0,
        }
    }

    /// Read one message. `Ok(Some(from_seq))` = resubscribe from there (a gap in `ws_seq`).
    pub fn receive(&mut self, msg: &Value) -> Result<Option<f64>, Error> {
        let m = match msg {
            Value::Obj(m) if m.get("type").is_str() => m,
            _ => return Err(sub_err("a message must be a JSON object with a string type")),
        };
        let typ = m.get("type").as_str().unwrap_or("");
        if typ == "ws_welcome" {
            let b = m.get_opt("binding").cloned().unwrap_or(Value::str(WS_BINDING_VERSION));
            if !matches!(&b, Value::Str(s) if WS_KNOWN_BINDINGS.contains(&s.as_str())) {
                return Err(sub_err(format!("welcome: unknown binding {} (section 10)", repr(&b))));
            }
            if m.get_opt("role").map_or(false, |r| r.as_str() != Some("decisions")) {
                return Err(sub_err("welcome: role is not 'decisions'"));
            }
            for k in ["seq", "missed", "first_available"] {
                if let Some(v) = m.get_opt(k) {
                    if !(v.is_int() && v.as_f64().unwrap_or(-1.0) >= 0.0) {
                        return Err(sub_err(format!("welcome: {} must be an integer >= 0", k)));
                    }
                }
            }
            if !self.welcomed && self.from_seq.is_none() {
                if let Some(s) = m.get("seq").as_f64() {
                    self.last = self.last.max(s);
                }
            }
            let missed = m.get("missed").as_f64().unwrap_or(0.0);
            if missed > 0.0 {
                self.missed += missed;
                if let Some(fa) = m.get("first_available").as_f64() {
                    self.last = self.last.max(fa - 1.0);
                }
            }
            self.welcomed = true;
            self.waiting = false;
            return Ok(None);
        }
        if !self.welcomed {
            return Err(sub_err("the first message must be ws_welcome (section 7 rule 2)"));
        }
        if self.waiting || typ != "trust_decision" {
            self.ignored += 1;
            return Ok(None);
        }
        let s = m.get("ws_seq");
        if !(s.is_int() && s.as_f64().unwrap_or(0.0) >= 1.0) {
            return Err(sub_err("ws_seq must be an integer >= 1 (section 7 rule 3)"));
        }
        let seq = s.as_f64().unwrap_or(0.0);
        if seq <= self.last {
            self.duplicates += 1;
            return Ok(None);
        }
        if seq > self.last + 1.0 {
            self.gaps.push(self.last + 1.0);
            self.waiting = true;
            return Ok(Some(self.last + 1.0));
        }
        let mut ev = m.clone();
        ev.insert("_line", Value::int((self.events.len() + 1) as f64));
        self.errors.extend(td_format_errors(&ev));
        self.events.push(ev);
        self.last = seq;
        Ok(None)
    }

    /// The summary, or an error if a decision breaks a FEP-0001 rule.
    pub fn finish(&self) -> Result<Value, Error> {
        let mut errs = self.errors.clone();
        errs.extend(td_final_errors(&self.events));
        if !errs.is_empty() {
            let first: Vec<String> = errs.into_iter().take(5).collect();
            return Err(sub_err(first.join("; ")));
        }
        let fin = self.events.iter().filter(|e| matches!(e.get("is_final"), Value::Bool(true))).count();
        Ok(Value::Obj(Map::from_pairs([
            ("decisions", Value::int(self.events.len() as f64)),
            ("final", Value::int(fin as f64)),
            ("acted", Value::Arr(acted_texts(&self.events))),
            ("duplicates", Value::int(self.duplicates as f64)),
            ("gaps", Value::Arr(self.gaps.iter().map(|g| Value::int(*g)).collect())),
            ("missed", Value::int(self.missed)),
            ("last_seq", Value::int(self.last)),
        ])))
    }
}
