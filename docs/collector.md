# Collector

The Collector is one service. It reads NeuralTextStream (NTS) input from several sources, runs processors on it, and writes the results to several targets. One TOML or JSON file wires it. The design copies the structure of the OpenTelemetry Collector (receivers → processors → exporters). The text and the code are our own.

Status: reference v0 in the Python package. The design is the draft [FEP-0006](../spec/feps/0006-collector.md). It is not part of NTS 1.0, because it does not change the format.

```
 file  ----> receiver --\                                          /--> jsonl (decision log)
 ws /nts --> receiver ---+--> validate --> trust --> thin --> redact --+--> stdout
 LSL -----> receiver --/                                            +--> ws /decisions
                                                                    \--> LSL decisions outlet
```

## Run it

```sh
fidetype collector --config examples/collector/collector.toml --check   # check the file, print the pipelines
fidetype collector --config examples/collector/collector.toml           # run it
```

`fidetype-collector` is the same command. Run the example from the repository root. Relative paths in a configuration resolve against the folder of the configuration file. The example reads a synthetic conformance vector and uses a toy trust configuration. Fit a real one with `fidetype.calibrate(...)`.

## Components

| Kind | Types | Job |
|---|---|---|
| Receiver | `file` (JSON Lines, also tail mode), `websocket` (FEP-0004 `/nts`), `lsl` (FEP-0002) | Read a source. Turn every loss into a `gap` or `lost` status |
| Processor | `validate`, `trust`, `thin`, `redact` | Check events, make trust decisions, drop previews, remove or hash decoded text |
| Exporter | `jsonl`, `stdout`, `websocket` (`/decisions`), `lsl` | Write items out. Never change them |
| Pipeline | any number | Connect named receivers, processors and exporters |
| Service | `[service]` | Log level, metrics file, health endpoint (`/healthz`, `/metrics`, localhost by default) |

Examples: [`collector.toml`](../examples/collector/collector.toml) (file input) and [`collector-lsl.toml`](../examples/collector/collector-lsl.toml) (LSL input; needs the `lsl` extra). Each key is explained in comments in the files.

## Safety and privacy rules

| Rule | What the Collector does |
|---|---|
| No final decision on a cut segment | A gap or a lost input drops the open utterance without a decision |
| No silent drop | An unreadable line or an invalid event becomes a `gap` status |
| Decoded text is personal data | The `redact` processor removes `shown` or replaces it with an HMAC (key from an environment variable) |
| No secrets in files | Tokens and keys come only from environment variables. A key in the file is a configuration error |
| No blank final COMMIT | The `trust` processor adds a commit gate if the configuration has none (rule TD-9) |

Full rule list and design notes: [wiki/concepts/collector.md](../wiki/concepts/collector.md).
