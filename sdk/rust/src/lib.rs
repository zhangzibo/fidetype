//! Fidetype Rust SDK: NeuralTextStream (NTS) v0.1 and the FEP-0001 / FEP-0002 /
//! FEP-0003 / FEP-0004 profiles (FEP-0004: the sans-IO WebSocket logic in [`ws`]).
//!
//! The core is `no_std` + `alloc`: parse, check, write and decide need no
//! operating system. The `std` feature (on by default) adds file helpers
//! ([`io`]), the CLI `fidetype-rs` and the example program.
//!
//! | Task | Items |
//! |---|---|
//! | Produce a stream | [`writer::NtsWriter`], [`npz::write_npz`] |
//! | Read a stream | [`reader::parse_nts_text`], [`reader::LineSplitter`], [`checks::load_stream`] |
//! | Check a stream | [`check_stream`], [`validate::StreamValidator`] |
//! | Act on decisions | [`trust::DecisionTracker`], [`trust::is_final_commit`], [`trust::empty_commit_warning`] |
//! | Conformance | [`conformance::run_vectors`], [`conformance::consumer_for`] |
//!
//! The verdicts equal the Python reference (`fidetype.conformance`) on every
//! golden vector in `spec/conformance/` (see the README for the parity table).

#![no_std]
#![forbid(unsafe_code)]
// `!(a > b)` is deliberate: NaN must fail a check, as in the Python reference.
#![allow(clippy::neg_cmp_op_on_partial_ord)]

extern crate alloc;
#[cfg(feature = "std")]
extern crate std;

pub mod checks;
pub mod conformance;
pub mod constants;
pub mod error;
pub mod json;
pub mod npz;
pub mod profiles;
pub mod raw;
pub mod reader;
pub mod sha256;
pub mod trust;
pub mod validate;
pub mod writer;
pub mod ws;

#[cfg(feature = "std")]
pub mod io;

pub use checks::{load_stream, ConsumedStream, Level, Status};
pub use error::{Error, ErrorKind};
pub use json::{parse_json, Map, Value};
pub use trust::{DecisionKind, DecisionTracker, HandledDecision};
pub use validate::{PushResult, StreamValidator};
pub use writer::{NbestItem, NtsWriter, WriterOptions};

/// Version of this SDK.
pub const SDK_VERSION: &str = "0.1.0";

/// The result of [`check_stream`].
#[derive(Debug, Clone)]
pub struct StreamReport {
    /// Every check result (the same 59 checks as `fidetype validate`).
    pub results: alloc::vec::Vec<checks::CheckResult>,
    /// The failures that block the requested level.
    pub failures: alloc::vec::Vec<checks::CheckResult>,
    /// The highest level reached: core, trust-ready, provenance, or `None`.
    pub level: Option<Level>,
    /// No failure blocks the requested level.
    pub ok: bool,
}

/// Check a stream file (the v0.1 suite) at `level`. `name` gives the format by
/// its extension (`.npz`, `.jsonl`, `.ndjson`, `.json`).
pub fn check_stream(name: &str, bytes: &[u8], level: Level) -> Result<StreamReport, Error> {
    let raw = raw::read_raw(name, bytes)?;
    let results = checks::run_checks(&raw);
    let failures: alloc::vec::Vec<_> = results
        .iter()
        .filter(|r| r.status == Status::Fail && checks::blocks(r.level, level))
        .cloned()
        .collect();
    let reached = checks::level_reached(&results);
    let ok = failures.is_empty();
    Ok(StreamReport { results, failures, level: reached, ok })
}
