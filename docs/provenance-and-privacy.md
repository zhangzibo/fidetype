# Provenance, licences, consent and deletion

Record where each output came from, carry licence flags to each output, reference consent, filter personal data and delete a person's data on request.

**Status:** Alpha ([status levels](glossary.md#status-levels))

This page shows how to record where each output came from (data, weights, calibration), how licence flags travel to each output, how to reference consent, how to filter personal data in the [Collector](glossary.md#collector), and how to delete a person's data. Data with a non-commercial licence makes an output [research only](glossary.md#research-only).

> **Not legal advice.** These tools help you document consent, keep less data and delete data on request. They do not make a deployment compliant. See the [neural-data law table](../wiki/questions/neural-data-law.md) (design information only).

## 1. The ledger in one picture

```
source (dataset, licence)  ─┐
source (corpus, licence)   ─┼─> artifact (weights) ─┐
                            └─> artifact (LM)      ─┼─> artifact (calibration) ─> context ─> decision ─> correction
                                                    └────────────────────────────┘     (licence flags on each)
```

Every box is one entry of an append-only JSON Lines file. Each entry holds the hash of the entry before it (a hash chain). `python -m fidetype.trust.provenance verify` checks the chain, the references and the licence flags.

## 2. Record the lineage

```python
from fidetype.trust.provenance import ProvenanceLedger, file_sha256

led = ProvenanceLedger("ledger.jsonl", text_mode="hash", hash_key=KEY)        # KEY: from a secret store
data = led.record_track_source("b2t25-t15")                  # licence CC0 1.0 from the benchmark track
corpus = led.record_source("Tatoeba English", "CC BY 2.0 FR", url="https://tatoeba.org")
w = led.record_artifact("weights", "my-decoder", derived_from=[data], sha256=file_sha256("model.pt"))
lm = led.record_artifact("lm", "char-lm", derived_from=[corpus])
cal = led.record_artifact("calibration", "guard-2026-11", derived_from=[w, data])
led.set_lineage([w, lm, cal])                                 # every new context names these
```

Then attach the ledger as before (`TrustPipeline.attach_ledger`, `LedgeredPolicy`, `StreamingTrustLayer(ledger=)`, or the Collector `trust` processor). Each decision now carries:

```json
"licence": {"research_only": false, "commercial_ok": true, "product_ok": {"project": false, "commercial": true}}
```

You can also write the lineage as a file and load it with `record_lineage_spec(ledger, "lineage.toml")` (format in the function's docstring). The Collector reads it with `ledger.lineage = "lineage.toml"` in the `trust` processor.

### Licence rules

| Licence (SPDX id) | `research_only` | `product_ok.project` | `product_ok.commercial` |
|---|---|---|---|
| `CC0-1.0`, `LicenseRef-fidetype-own` | no | yes | yes |
| `CC-BY-4.0`, `MIT`, `Apache-2.0`, `BSD-*` | no | no | yes (attribution listed) |
| `CC-BY-ND-*` | no | no | no (no derivatives) |
| `CC-BY-NC-*` (SpanishBCBL, emg2qwerty) | **yes** | no | no |
| `LicenseRef-fidetype-consented` | yes, unless the consent scope has `train-product` | with `train-product` | with `train-product` |
| unknown text | **yes** | no | no |

An artifact inherits the most restrictive flags of all its inputs. `record_artifact(..., purpose="product")` refuses an artifact whose inputs the product policy does not allow (`LicenceError`). The default policy `project` is the project's licence rule: product weights come only from CC0 data or our own consented data.

### Keep research-only output out of a product exporter

Every trust layer writes `trust_decision.input.research_only` when it knows the licence of its input (FEP-0010, TD-15). A Collector exporter can refuse such decisions:

```toml
[exporters.typing]
type = "os_text"
backend = "stub"
refuse_research_only = true    # drop decisions with input.research_only = true
unknown_licence = "refuse"     # default; "pass" exports decisions without the key
```

| `input.research_only` of a decision | Without the option (default) | `refuse_research_only = true` |
|---|---|---|
| `true` (for example a `CC-BY-NC-4.0` stream, or an NC decoder in the ledger lineage) | exported | dropped, counter `research_only_refused` |
| `false` (for example a `CC0-1.0` stream) | exported | exported |
| absent, or not a boolean (**unknown licence**) | exported | `unknown_licence = "refuse"`: dropped, counter `licence_unknown_refused`; `"pass"`: exported |

Rules:
- The option works on every exporter type (`jsonl`, `stdout`, `websocket`, `lsl`, `os_text`). It acts on decisions (`trust_decision`, `intent_decision`, `control_decision`) and, on a `jsonl` or `stdout` exporter of input events, on whole streams (next table).
- An exporter that only writes decisions lets input events pass; it does not write them anyway.

Input-event exporters. The header of each stream decides for the whole stream (header and every event up to its `end`):

| Header `meta` of a stream | `refuse_research_only = true` |
|---|---|
| `data.research_only = true`, or a `data.licence` without commercial use (for example `CC-BY-NC-4.0`) or not known | stream dropped, counters `research_only_streams_refused`, `research_only_events_refused` |
| `data.research_only = false` without `data.licence` | dropped as research only (FEP-0010: unknown licence, research only), also with `"pass"` |
| a `data.licence` with commercial use (for example `CC0-1.0`), not restricted by `data.research_only = true` | exported unchanged |
| neither key, or an event before any header (**unknown licence**) | `"refuse"`: stream dropped, counters `licence_unknown_streams_refused`, `licence_unknown_events_refused`; `"pass"`: exported |

```toml
[exporters.store]
type = "jsonl"
path = "out/streams/{session}.jsonl"
types = ["header", "frame", "segment_end", "end"]
refuse_research_only = true    # a research-only stream writes no file
```

- The verdict is per stream key. In a pipeline with several streams, each stream is judged by its own header. A new header on the same key starts a new verdict.
- A refused stream opens no file. With a single path (no `{session}`), the file opens at the first exported item; an older file at that path stays as it is.
- An unknown licence is refused by default. Reason: the project licence rule reads an unknown licence as research only (table above).
- The exporter never changes a decision that it exports (FEP-0006 section 4 rule 1). It logs one line at the first drop of each kind; then it only counts. The log line holds no text and no session id.
- Keep a decision log without the option next to the product exporter. Then the audit trail keeps every decision.
- This is a policy of the operator, not a format rule. The stream format and the decision format do not change.

## 3. The lineage of one output

```sh
python -m fidetype.trust.provenance lineage ledger.jsonl dec-000007-461459b3 --word 0
python -m fidetype.trust.provenance lineage ledger.jsonl dec-000007-461459b3 --json
```

The report verifies the whole chain, then lists the output, its corrections, the context, the artifacts (inputs first), the data sources with their licences, and the entries with their hashes. Example: [B2T '25 lineage report](../experiments/2026-11-17-p5-03-lineage/results/lineage-report.md).

## 4. Anchor the head

The chain detects an edit, a deletion inside the file and a reorder. It cannot detect a cut at the end by itself. Keep the head in a second place:

```sh
python -m fidetype.trust.provenance anchor ledger.jsonl --out anchor.json
python -m fidetype.trust.provenance verify ledger.jsonl --anchor anchor.json
```

A plain anchor is tamper-evident, not tamper-proof. A person who can rewrite the ledger can recompute the whole chain and can also rewrite `anchor.json`. Use one of these two options (or both) to close that gap.

### 4.1 Signed anchor (Ed25519)

Install the optional extra: `pip install "fidetype[sign]"` (package `cryptography`, Apache-2.0 OR BSD-3-Clause).

```sh
# once, on the operator's machine; never commit the private key
python -m fidetype.trust.provenance keygen --private ~/secrets/anchor.pem --public anchor.pub.pem

python -m fidetype.trust.provenance anchor ledger.jsonl --out anchor.json --sign-key-file ~/secrets/anchor.pem
#   or: --sign-key-env FT_ANCHOR_KEY   (the environment variable holds the PEM text, e.g. from a secret store)

python -m fidetype.trust.provenance verify ledger.jsonl --anchor anchor.json --public-key anchor.pub.pem
python -m fidetype.trust.provenance verify ledger.jsonl --anchor anchor.json --public-key anchor.pub.pem --allow-growth
```

| Check of `verify --anchor --public-key` | Fails when |
|---|---|
| Signature (Ed25519 over the canonical JSON of the anchor without `signature`) | the anchor was edited, or signed with another key (`key_id` differs) |
| Ledger id | the ledger has another genesis |
| Anchored entry (`seq`, `hash`) | the ledger was rewritten (even with a recomputed chain) or cut below the anchor |
| Head = anchored entry | entries were added after the anchor (accept them with `--allow-growth`; they need a later anchor) |
| Whole chain | any check of section 1 |

A signed anchor without `--public-key` fails: nobody checked the signature. Redaction (section 7) keeps the entry hashes, so an anchor stays valid after an erasure. Python API: `fidetype.trust.anchor` (`generate_key`, `sign_anchor`, `verify_anchored`).

Key rules: keep the private key in a secret store or a file with owner-only access, on the operator's side. Publish the public key (for example next to the release notes). Make a new key pair when a person who had access leaves; old anchors stay valid with the old public key.

### 4.1a Automatic signed anchors

The Collector and the Python API can write signed anchors by themselves. Then a rewrite of the newest entries is covered between two manual runs. Each anchor is a separate file `anchor-<seq>.json` in its own directory. An older anchor is never changed.

```toml
[processors.trust]
type = "trust"
config = "trust.json"
ledger = { path = "out/ledger.jsonl", anchor = { dir = "out/anchors", key_env = "FIDETYPE_ANCHOR_KEY",
           every_n = 100, every_s = 60 } }
```

| Option of `ledger.anchor` | Meaning |
|---|---|
| `dir` (required) | Directory of the anchor files. It must not be the ledger file. |
| `key_env` or `key_file` (exactly one) | The environment variable that holds the PEM text, or a PEM file with owner-only access. The key never goes into the configuration file, a log, the metrics or an anchor. |
| `every_n` | Write an anchor after every N new entries. |
| `every_s` | Write an anchor when T seconds have passed and there are new entries (checked at each entry and at each loop step). |
| `on_stop` (default `true`) | Write the last anchor at stop. It covers every entry of the run. |
| `keep` | Keep only the newest N anchor files of this ledger. |

`verify --anchor` also accepts the directory. It then checks the newest anchor (highest `seq`):

```sh
python -m fidetype.trust.provenance verify out/ledger.jsonl --anchor out/anchors --public-key anchor.pub.pem --allow-growth
```

Python API: `AutoAnchor(ledger, load_private_key(key_env="FIDETYPE_ANCHOR_KEY"), "anchors", every_n=100)`; call `tick()` from a loop for the timer and `close()` at stop (or use `with`). It works with every `ProvenanceLedger`, also the one of `StreamingTrustLayer(ledger=)`. The Collector metrics hold `anchors` (count, newest `seq`, `key_id`).

### 4.2 External store (no code needed)

- **Second host.** Copy each anchor file to a host that the ledger's writer cannot change (another account, a write-once bucket, a public git repository).
- **RFC 3161 timestamp.** Send the anchor file's hash to a timestamp authority (TSA). The token proves that the anchor existed at that time.

```sh
openssl ts -query -data anchor.json -sha256 -cert -out anchor.tsq
# send anchor.tsq to the TSA of your choice (HTTP POST, content type application/timestamp-query) -> anchor.tsr
openssl ts -verify -data anchor.json -in anchor.tsr -CAfile tsa-ca.pem -untrusted tsa.pem
```

Fidetype does not call a TSA itself, and the tests never use the network. A signed anchor and a timestamp work together: sign first, then timestamp the signed file.

## 5. Consent references

A stream, a profile and a ledger hold only an **opaque reference** to a consent record that you keep elsewhere (spec rule SEC-6). `check_consent_ref` accepts 4 to 128 characters of letters, digits and `. _ : / # -`. It refuses spaces, e-mail addresses and phone numbers.

```python
from fidetype.trust.privacy import ConsentRecord

rec = ConsentRecord("cr-2026-0001", ["decode", "calibrate", "train-research"], "form-v2", "2026-11-01T00:00:00Z")
rec.allows("train-product")          # False
rec.withdraw()                       # then start the deletion (section 7)
```

Purposes: `decode`, `store-text`, `store-ledger`, `calibrate`, `personalise`, `train-research`, `train-product`, `share-research`. Keep `ConsentRecord` files in your own system, never in a public repository.

## 6. Privacy processor (Collector)

```toml
[processors.priv]
type = "privacy"
policy = "privacy.toml"          # optional; the built-in default is shown below
key_env = "FIDETYPE_PRIVACY_KEY" # needed when a rule hashes

[pipelines.main]
processors = ["check", "priv", "trust"]   # meta-only policies may run before trust
```

```toml
# privacy.toml
schema = "fidetype.privacy-policy/1.0"
default = "drop"        # meta keys that no rule names
text = "keep"           # decoded text: keep | drop | hash (drop / hash must come after trust)
scan_pii = true         # drop a kept value that holds an e-mail address, a phone number or an IP address
[meta]
"decoder.*" = "keep"
"subject.id" = "hash"   # "h:" + HMAC-SHA256(key, value)[:32]
```

The built-in default keeps the provenance namespaces (`device.*`, `decoder.*`, `adapter.*`, `lm.*`, `calibration.*`, `stream.*`), `data.*`, `consent.ref`, `language` and the modality keys. It drops `subject.*`, `session.*`, `user.*` and every other key. Check a policy file with `python -m fidetype.trust.privacy check-policy privacy.toml`.

## 7. Deletion on request

```sh
FT_SUBJECT=<subject.id> FT_LEDGER_KEY=<key> python -m fidetype.trust.privacy erase \
    --request-ref er-2026-0007 --profile profiles/p07.json --ledger ledger.jsonl \
    --subject-env FT_SUBJECT --ledger-key-env FT_LEDGER_KEY --receipt receipt.json
```

1. The profile file is deleted.
2. In each ledger, a `redaction` entry names every decision of the subject (and its corrections) by `seq` and `hash`.
3. The bodies of these entries are removed (tombstones). Each entry keeps `body_sha256`, so the chain still verifies. The random `salt` goes with the body, so nobody can confirm a guessed text from the digest.
4. The receipt lists the request reference, the user hash, the ledger ids, the counts and the new heads. It holds no raw id and no path.

Limits: copies outside these files (backups, synced folders) are not reached. A ledger written with the old hash rule `v0` cannot be redacted without breaking its chain; start a new ledger.

## 8. Erasure in Collector output files

The Collector also writes plain files: decision logs, NTS stream files, the `os_text` stub log. Prepare them so that an erasure can find one subject's items.

```toml
[processors.priv]
type = "privacy"
key_env = "FIDETYPE_PRIVACY_KEY"
subject_index = "out/subject-index.jsonl"   # one line per stream: session + "h:" HMAC code of subject.id

[exporters.log]
type = "jsonl"
path = "out/decisions.jsonl"                # shared decision log: lines are removed by session

[exporters.streams]
type = "jsonl"
path = "out/streams/{session}.nts.jsonl"    # one file per stream: the whole file is deleted
types = ["header", "frame", "segment_end", "end"]
```

- The subject index never holds the raw `subject.id`. It holds `"h:" + HMAC-SHA256(key, subject.id)[:32]`, the same code as a policy `hash` rule. The policy can still drop `subject.id` from the stream; the index keeps the link.
- `{session}` is the only path placeholder. Session ids with other characters than letters, digits and `. _ -` get a safe file name with a short hash (`fidetype.trust.erasure.session_token`).

Then add the outputs to the erasure request of section 7:

```sh
FT_SUBJECT=<subject.id> FT_PRIV_KEY=<privacy key> python -m fidetype.trust.privacy erase \
    --request-ref er-2026-0007 --subject-env FT_SUBJECT --index-key-env FT_PRIV_KEY \
    --subject-index out/subject-index.jsonl \
    --output out/decisions.jsonl --output out/typed.jsonl \
    --output-template "out/streams/{session}.nts.jsonl" --receipt receipt.json
```

| File | What the erasure does |
|---|---|
| per-session file (`--output-template`) | deleted |
| NTS stream file (`--output`, starts with a header) | deleted when its header `subject.id` is the subject (raw or `h:` code); else unchanged |
| decision log (`--output`) | the subject's `trust_decision` lines (by `session`) are removed; other lines stay byte for byte |
| `os_text` stub log (`--output`) | the lines whose `decision.session` is the subject's are removed |
| subject index | the subject's lines are removed |
| file with no line left | deleted (an empty file is not a decision log) |

`--sessions-env VAR` adds session ids directly (comma-separated, from an environment variable). The receipt (`fidetype.deletion-receipt/1.1`) gets `outputs`: per file its position in the request, the form, the action, the counts, SHA-256 before and after, and the `nts-conform` result before and after. It holds no path, no session id and no subject id. The command exits with 1 when a rewritten file lost conformance.

Decision-log rules are per session (TD-5 … TD-7), so removing whole sessions keeps the other sessions conformant. Not reached: live channels (WebSocket `/decisions`, LSL outlets, standard output) and copies outside these files. The metrics file holds counts only (no id, no text).

## Reference

- Module docs: `fidetype.trust.provenance`, `fidetype.trust.licence`, `fidetype.trust.privacy`.
- Concept page: [provenance ledger](../wiki/concepts/provenance-ledger.md).
- Spec: NTS 1.0 RC4 sections 6.5 (PRV-1 … PRV-3) and 10 (security and privacy).
