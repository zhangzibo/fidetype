//! File helpers (feature `std`).

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::string::{String, ToString};
use std::vec::Vec;
use std::format;

use crate::checks::{load_stream, ConsumedStream, Level};
use crate::conformance::{run_vectors, ProfileReport, PROFILES};
use crate::error::{Error, ErrorKind};
use crate::json::Map;
use crate::reader::{parse_nts_bytes, EventReader};
use crate::trust::{handle_decisions, HandledDecision};
use crate::validate::PushResult;
use crate::{check_stream, StreamReport};

fn io_err(path: &Path, e: std::io::Error) -> Error {
    Error::new(ErrorKind::Io, format!("{}: {}", path.display(), e))
}

/// Read a whole file.
pub fn read_bytes(path: impl AsRef<Path>) -> Result<Vec<u8>, Error> {
    let p = path.as_ref();
    fs::read(p).map_err(|e| io_err(p, e))
}

fn base_name(p: &Path) -> String {
    p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()
}

/// The reference consumer on a file (`.npz` or `.jsonl`).
pub fn load_stream_file(path: impl AsRef<Path>) -> Result<ConsumedStream, Error> {
    let p = path.as_ref();
    load_stream(&base_name(p), &read_bytes(p)?)
}

/// Run the v0.1 checks on a file.
pub fn check_stream_file(path: impl AsRef<Path>, level: Level) -> Result<StreamReport, Error> {
    let p = path.as_ref();
    check_stream(&base_name(p), &read_bytes(p)?, level)
}

/// Read a JSON Lines file in blocks and validate it event by event (constant memory per event).
pub fn validate_file_streaming(path: impl AsRef<Path>, mut on_event: impl FnMut(&Map, &PushResult)) -> Result<usize, Error> {
    let p = path.as_ref();
    let mut f = fs::File::open(p).map_err(|e| io_err(p, e))?;
    let mut r = EventReader::new();
    let mut buf = [0u8; 64 * 1024];
    let mut n = 0;
    loop {
        let k = f.read(&mut buf).map_err(|e| io_err(p, e))?;
        let evs = if k == 0 { r.finish()? } else { r.push(&buf[..k])? };
        for (ev, res) in &evs {
            on_event(ev, res);
            n += 1;
        }
        if k == 0 {
            return Ok(n);
        }
    }
}

/// Read a decision log and handle every decision.
pub fn handle_decision_file(path: impl AsRef<Path>) -> Result<Vec<HandledDecision>, Error> {
    Ok(handle_decisions(&parse_nts_bytes(&read_bytes(path)?)?))
}

/// Profiles present under a conformance folder (`spec/conformance`), v0.1 first.
pub fn list_profiles(conformance_dir: impl AsRef<Path>) -> Vec<String> {
    let d = conformance_dir.as_ref();
    PROFILES.iter().filter(|p| d.join(p).join("manifest.json").is_file()).map(|p| p.to_string()).collect()
}

/// Run one profile over the vectors in `dir` (a folder with manifest.json).
pub fn run_profile_dir(profile: &str, dir: impl AsRef<Path>) -> Result<ProfileReport, Error> {
    let dir: PathBuf = dir.as_ref().to_path_buf();
    let mut read = |f: &str| read_bytes(dir.join(f));
    run_vectors(profile, &mut read, None)
}
