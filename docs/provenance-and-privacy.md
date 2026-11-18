# Provenance, licences, consent and deletion

This page shows how to record where each output came from (data, weights, calibration), how licence flags travel to each output, how to reference consent, how to filter personal data in the Collector, and how to delete a person's data. Roadmap items P5-03 and P5-04.

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

Limits: copies outside these files (backups, synced folders, exported decision logs) are not reached. A ledger written before P5-04 (hash rule `v0`) cannot be redacted without breaking its chain; start a new ledger.

## Reference

- Module docs: `fidetype.trust.provenance`, `fidetype.trust.licence`, `fidetype.trust.privacy`.
- Concept page: [provenance ledger](../wiki/concepts/provenance-ledger.md).
- Spec: NTS 1.0 RC4 sections 6.5 (PRV-1 … PRV-3) and 10 (security and privacy).
