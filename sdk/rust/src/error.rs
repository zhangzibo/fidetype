//! The error type of the SDK.

use alloc::string::{String, ToString};
use core::fmt;

/// What kind of failure an [`Error`] is. The names follow the Python
/// exceptions of the reference, so reports read the same.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorKind {
    /// A consumer rejects the stream (`StreamRejected`).
    Rejected,
    /// A live event breaks a rule (`StreamEventError`).
    StreamEvent,
    /// Text that is not JSON (`JSONDecodeError`).
    Json,
    /// A value has the wrong type (`TypeError`).
    Type,
    /// A value is out of range or not allowed (`ValueError`).
    Value,
    /// Bad ZIP / NPY / XML data.
    Format,
    /// The writer was used in a wrong way.
    Usage,
    /// File or stream I/O (feature `std`).
    Io,
}

impl ErrorKind {
    /// The Python-like name of the kind.
    pub fn name(self) -> &'static str {
        match self {
            ErrorKind::Rejected => "StreamRejected",
            ErrorKind::StreamEvent => "StreamEventError",
            ErrorKind::Json => "JSONDecodeError",
            ErrorKind::Type => "TypeError",
            ErrorKind::Value => "ValueError",
            ErrorKind::Format => "FormatError",
            ErrorKind::Usage => "UsageError",
            ErrorKind::Io => "IOError",
        }
    }
}

/// An SDK error: a kind, a message and, for a rejection, the spec clause and check id.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Error {
    pub kind: ErrorKind,
    pub message: String,
    /// The spec clause (for example `5.2.1`), or empty.
    pub clause: String,
    /// The check id (for example `NTS-NORM`), or empty.
    pub check_id: String,
}

impl Error {
    pub fn new(kind: ErrorKind, message: impl Into<String>) -> Self {
        Error { kind, message: message.into(), clause: String::new(), check_id: String::new() }
    }
    /// A consumer rejection with its clause and check id.
    pub fn rejected(message: impl Into<String>, clause: &str, check_id: &str) -> Self {
        Error { kind: ErrorKind::Rejected, message: message.into(), clause: clause.to_string(), check_id: check_id.to_string() }
    }
    pub fn event(message: impl Into<String>) -> Self {
        Error::new(ErrorKind::StreamEvent, message)
    }
    pub fn type_err(message: impl Into<String>) -> Self {
        Error::new(ErrorKind::Type, message)
    }
    pub fn value(message: impl Into<String>) -> Self {
        Error::new(ErrorKind::Value, message)
    }
    pub fn format(message: impl Into<String>) -> Self {
        Error::new(ErrorKind::Format, message)
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.kind.name(), self.message)
    }
}

#[cfg(feature = "std")]
impl std::error::Error for Error {}
