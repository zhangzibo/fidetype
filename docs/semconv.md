# Semantic conventions

NTS streams carry metadata as named keys, for example `device.modality` in the header `meta`. The **semantic-convention registry** lists every key that the spec defines. Each entry gives the name, the type, the unit, the requirement level, the stability and the spec rules.

The registry belongs to NTS 1.0 RC4 (draft). Since RC4 it is normative for the key names, types, value lists and validators (MET-10). The spec tables are informative copies, and the rules about the keys stay in the spec text.

## Where it is

| File | What it is |
|---|---|
| [`spec/semconv/manifest.yaml`](../spec/semconv/manifest.yaml) | Containers, namespaces, the words of the registry, open and resolved questions |
| [`spec/semconv/attributes/*.yaml`](../spec/semconv/attributes/) | One file per namespace (`device`, `decoder`, ...) and one per `trust_decision` object |
| [`spec/semconv/registry.md`](../spec/semconv/registry.md) | The reference page. **Generated**: do not edit it by hand |
| [`tools/semconv/semconv.py`](../tools/semconv/semconv.py) | The generator and the agreement check |

## What it covers

| Container | Keys | Spec |
|---|---|---|
| Header `meta` | 24 keys in 12 reserved namespaces | [3.4](../spec/nts-1.0-rc4.md#34-semantic-conventions-for-meta), [12.5](../spec/nts-1.0-rc4.md#125-semantic-convention-namespaces-policy-spec-for-the-listed-keys-first-come-outside) |
| `trust_decision.input` | 14 recommended keys (audit data) | [6.1.1](../spec/nts-1.0-rc4.md#611-input-keys-recommended) |
| `trust_decision.declaration` | 5 recommended keys (audit data) | [6.1.2](../spec/nts-1.0-rc4.md#612-declaration-keys-recommended) |

The modality namespaces `emg.*`, `eeg.*`, `meg.*`, `fnirs.*` and `implant.*` are **planned** and, since RC4, reserved (MET-3: a custom key in them gets a warning). They have no keys yet. A key gets into the registry only after a FEP defines it (SC-1).

## Use it as a producer

1. Look up each key in [registry.md](../spec/semconv/registry.md). Use the given type.
2. Check the "Requirement" column for the conformance level that you claim. For example, level `trust-ready` needs `device.modality`, `decoder.causal` and `data.derived = true`.
3. Put your own keys in your own namespace, for example `acme.gain`. Do not add keys to a reserved namespace (MET-3).
4. Run the conformance check on your stream:

```bash
fidetype conformance check my_stream.jsonl --level provenance
```

## Change the registry

1. Change the spec first (through a FEP). The registry follows the spec.
2. Edit the YAML in `spec/semconv/`.
3. Regenerate the page and run the check. Both need PyYAML:

```bash
uv run --no-project --with pyyaml==6.0.3 python tools/semconv/semconv.py           # write registry.md
uv run --no-project --with pyyaml==6.0.3 python tools/semconv/semconv.py --check   # exit 1 on an error
uv run --no-project --with pyyaml==6.0.3 --with pytest python -m pytest -q tests/test_semconv.py
```

The CI job `semconv` runs the check and the tests.

## What the check compares

| Check | It makes sure that |
|---|---|
| structure | Every entry uses the words of `manifest.yaml`; keys are unique; a `meta` key is in its namespace |
| spec | The spec tables (3.4, 6.1.1, 6.1.2) have the same keys, types and values; rule ids exist; namespaces equal 12.5; enumerations and fallbacks equal 12.3 |
| proto | Each container is a `google.protobuf.Struct` field; related fields exist |
| schema | Each container is an `object` in the generated JSON Schema |
| sdks | The key tables of the Python, TypeScript and Rust validators have the same keys, validators and modality list |
| checks | Each conformance check id exists, at the level of its requirement |
| vectors | The `meta` values of the accept vectors pass the registry validators |
| docs | `registry.md` is up to date |

## Open questions

The registry found gaps that needed a spec change. NTS 1.0 RC4 answered SC-2 … SC-8 (for example: the registry is normative, MET-10; string keys are non-empty, MET-7; open and closed value lists, MET-8). One question stays open: modality keys (SC-1), deferred to a FEP with evidence from real producers. The list is at the end of [registry.md](../spec/semconv/registry.md#open-questions).
