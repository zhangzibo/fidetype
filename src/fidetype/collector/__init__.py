"""The Fidetype collector v0 (P3, FEP-0006 Draft): receivers -> processors -> exporters.

The collector is one service that takes NeuralTextStream (NTS) input from
several sources, runs processors on it (validate, trust layer, redact,
thin) and sends the results to several targets. The design follows the
idea of the OpenTelemetry Collector: named components, pipelines that
connect them, one configuration file, a health and metrics endpoint.

::

    fidetype collector --config examples/collector/collector.toml
    fidetype collector --config collector.toml --check      # check the configuration only

v0 components
-------------
Receivers   ``file`` (JSON Lines, optional tail mode), ``websocket`` (FEP-0004 ``/nts``)
Processors  ``validate`` (conformance checks), ``trust`` (streaming trust layer, optional
            provenance ledger), ``redact`` (remove or HMAC decoded text, SEC-7), ``thin``
            (drop provisional decisions without news)
Exporters   ``jsonl`` (decision log), ``stdout``, ``websocket`` (FEP-0004 ``/decisions``)

Not in v0 (FEP-0006 section 10): LSL receiver and exporter, gRPC, OS
input-method exporters, YAML configuration, hot reload, several
processes, per-user calibration, LM rescoring.

The collector wraps existing code: :mod:`fidetype.adapters.ws` (server,
loss rules of the trust runner), :mod:`fidetype.trust.streaming`,
:mod:`fidetype.trust.provenance` and :mod:`fidetype.conformance`.
"""

from __future__ import annotations

from fidetype.collector.config import CollectorConfig, ConfigError, load, parse
from fidetype.collector.service import Collector, run_file

__all__ = ["Collector", "CollectorConfig", "ConfigError", "load", "parse", "run_file"]
