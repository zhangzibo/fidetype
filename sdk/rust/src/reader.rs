//! NeuralTextStream JSON Lines readers: from a complete text, or
//! incrementally from byte chunks (a serial port, a socket, a file read in
//! blocks). No operating system needed.

use alloc::string::String;
use alloc::vec::Vec;
use alloc::format;

use crate::error::Error;
use crate::json::{decode_utf8, is_blank, parse_json, py_lines, Map};
use crate::validate::{check_event_object, PushResult, StreamValidator};

/// Parse a complete JSON Lines text into events (each must be an object with a string `type`).
pub fn parse_nts_text(text: &str) -> Result<Vec<Map>, Error> {
    let mut out = Vec::new();
    for (k, line) in py_lines(text).into_iter().enumerate() {
        if is_blank(line) {
            continue;
        }
        let v = parse_json(line).map_err(|e| Error::event(format!("line {}: not JSON: {}", k + 1, e.message)))?;
        let ev = check_event_object(v).map_err(|_| Error::event(format!("line {}: not an object with a string type", k + 1)))?;
        out.push(ev);
    }
    Ok(out)
}

/// Parse complete JSON Lines bytes (strict UTF-8).
pub fn parse_nts_bytes(bytes: &[u8]) -> Result<Vec<Map>, Error> {
    parse_nts_text(decode_utf8(bytes)?)
}

/// Split a byte stream into lines (`\n`, `\r\n` or `\r`). UTF-8 is decoded
/// strictly across chunk borders.
///
/// ```
/// use fidetype::reader::LineSplitter;
/// let mut s = LineSplitter::new();
/// let mut lines = s.push(b"{\"type\":\"hea").unwrap();
/// lines.extend(s.push(b"der\"}\r\n{\"type\":\"end\"}").unwrap());
/// lines.extend(s.finish().unwrap());
/// assert_eq!(lines, ["{\"type\":\"header\"}", "{\"type\":\"end\"}"]);
/// ```
#[derive(Debug, Default, Clone)]
pub struct LineSplitter {
    pending: Vec<u8>,
    /// The last chunk ended with `\r`: a `\n` at the start of the next chunk belongs to it.
    after_cr: bool,
}

impl LineSplitter {
    pub fn new() -> Self {
        Self::default()
    }

    fn take_line(&mut self, end: usize) -> Result<String, Error> {
        let line: Vec<u8> = self.pending.drain(..end).collect();
        String::from_utf8(line).map_err(|e| Error::value(format!("'utf-8' codec can't decode bytes: {}", e)))
    }

    /// Add a chunk; return the complete lines it closes.
    pub fn push(&mut self, chunk: &[u8]) -> Result<Vec<String>, Error> {
        let mut out = Vec::new();
        let mut chunk = chunk;
        if self.after_cr {
            if let Some((&b'\n', rest)) = chunk.split_first() {
                chunk = rest;
            }
            self.after_cr = false;
        }
        for &b in chunk {
            self.pending.push(b);
            let n = self.pending.len();
            if b == b'\n' {
                let cr = n >= 2 && self.pending[n - 2] == b'\r';
                let line = self.take_line(n - 1 - cr as usize)?;
                self.pending.clear();
                out.push(line);
            } else if n >= 2 && self.pending[n - 2] == b'\r' {
                // a lone \r ended the previous line
                let line = self.take_line(n - 2)?;
                self.pending.drain(..1);
                out.push(line);
            }
        }
        if self.pending.last() == Some(&b'\r') {
            let n = self.pending.len();
            let line = self.take_line(n - 1)?;
            self.pending.clear();
            self.after_cr = true;
            out.push(line);
        }
        Ok(out)
    }

    /// End of input: return the last line, if any.
    pub fn finish(&mut self) -> Result<Option<String>, Error> {
        if self.pending.is_empty() {
            return Ok(None);
        }
        let n = self.pending.len();
        let line = self.take_line(n)?;
        Ok(Some(line))
    }
}

/// Read and validate events from byte chunks (header first, increasing frame
/// times, normalised rows, valid hypotheses). Each call returns the events
/// that the chunk completes, with the validator result. Stops at the first
/// bad event with an error.
#[derive(Debug, Default, Clone)]
pub struct EventReader {
    lines: LineSplitter,
    n: usize,
    pub validator: StreamValidator,
}

impl EventReader {
    pub fn new() -> Self {
        Self::default()
    }

    fn line(&mut self, line: &str, out: &mut Vec<(Map, PushResult)>) -> Result<(), Error> {
        self.n += 1;
        if is_blank(line) {
            return Ok(());
        }
        let v = parse_json(line).map_err(|e| Error::event(format!("line {}: not JSON: {}", self.n, e.message)))?;
        let ev = check_event_object(v).map_err(|_| Error::event(format!("line {}: not an object with a string type", self.n)))?;
        let r = self.validator.push(&ev).map_err(|e| Error::event(format!("line {}: {}", self.n, e.message)))?;
        out.push((ev, r));
        Ok(())
    }

    /// Add a chunk of bytes.
    pub fn push(&mut self, chunk: &[u8]) -> Result<Vec<(Map, PushResult)>, Error> {
        let mut out = Vec::new();
        for l in self.lines.push(chunk)? {
            self.line(&l, &mut out)?;
        }
        Ok(out)
    }

    /// End of input.
    pub fn finish(&mut self) -> Result<Vec<(Map, PushResult)>, Error> {
        let mut out = Vec::new();
        if let Some(l) = self.lines.finish()? {
            self.line(&l, &mut out)?;
        }
        Ok(out)
    }
}
