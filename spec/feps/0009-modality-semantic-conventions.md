# FEP-0009: Modality semantic conventions (emg, meg, implant)

| | |
|---|---|
| **FEP** | 0009 |
| **Title** | Keys for the modality namespaces `emg`, `meg` and `implant`, from producer evidence |
| **Author(s)** | Fidetype maintainers |
| **Status** | Draft (folded into [NTS 1.0 RC4](../nts-1.0-rc4.md) as the amendment of 2026-11-16: sections 1.6, 3.4 (MET-11), 12.5 and A.8; reference implementation and vectors in Python, TypeScript and Rust) |
| **Type** | Spec change (additive) |
| **Affects** | NTS 1.0 RC4 sections 3.4, 12.5, A.8; the registry [`spec/semconv/`](../semconv/registry.md) |
| **Created** | 2026-11-16 |
| **Discussion** | Open question SC-1 of the registry (roadmap P1-04); RC4 deferred it to "a FEP with evidence from real producers" |

## Summary
Eight optional keys in three modality namespaces. Each key is a fact that a reference adapter knows and writes. `eeg` and `fnirs` get no keys, because no reference producer writes EEG or fNIRS streams yet (new open question SC-9).

| Key | Type | Values / meaning |
|---|---|---|
| `emg.placement` | non-empty string | Open list: `wrist`, `forearm`, `face`, `neck` |
| `emg.derivation` | non-empty string | Open list: `bipolar` (also called differential), `monopolar` |
| `meg.sensor_types` | list of non-empty strings | Open list: `magnetometer`, `planar_gradiometer`, `axial_gradiometer`. An OPM sensor is a magnetometer |
| `implant.array_type` | non-empty string | Open list: `utah` |
| `implant.array_count` | integer ≥ 1 | Arrays that the decoder used |
| `implant.features` | list of non-empty strings | Open list: `threshold_crossings`, `spike_band_power`, `sorted_units` |
| `implant.bin_s` | number ≥ 0 | Width of one feature bin, seconds |
| `implant.areas` | list of non-empty strings | Brain areas, free text |

New rule **MET-11**: a modality key describes the recording of `device.modality` (`emg.*` with `emg`; `meg.*` with `meg` or `opm-meg`; `implant.*` with `intracortical` or `ecog`). A producer SHOULD NOT write the keys of another modality. All eight keys are optional and Development (target Development).

## Motivation
- A consumer that compares two streams of one modality needs a few recording facts: where the EMG electrodes are, which MEG sensors fed the decoder, which features and bin width an implant decoder used. Today each adapter writes these facts as free text in `device.model`, so a tool cannot read them.
- RC4 reserved the namespaces (SC-2) and asked for producer evidence first (SC-1). The P4 adapters now give it.

## Evidence (what each producer can fill)

| Producer | Modality | Keys it writes |
|---|---|---|
| `fidetype.adapters.emg2qwerty` (Meta emg2qwerty) | emg | `emg.placement = wrist`, `emg.derivation = bipolar` (the dataset says "differential") |
| `fidetype.adapters.kt_semg` (KT forearm sleeves) | emg | `emg.placement = forearm` (the derivation is not stated in our sources, so the adapter leaves it out) |
| `fidetype.adapters.toronto_semg` (Intan RHD2000) | emg | `emg.placement = forearm`, `emg.derivation = bipolar` |
| `fidetype.adapters.spanishbcbl_meg` (MEGIN 306 channels) | meg | `meg.sensor_types = [magnetometer, planar_gradiometer]` (102 + 204) |
| `fidetype.adapters.willett_handwriting` (Willett 2021) | intracortical | `implant.array_type = utah`, `implant.array_count = 2`, `implant.features = [threshold_crossings]`, `implant.bin_s = 0.01`, `implant.areas` |
| `fidetype.adapters.b2t25` (Brain-to-Text '25, T15) | intracortical | `implant.features = [threshold_crossings, spike_band_power]`, `implant.bin_s = 0.02`, `implant.areas` (array type and count are not in the dataset file, so the adapter leaves them out) |
| NLB MC_RTT (P12-03 converter; no stream adapter) | intracortical (macaque) | would write `implant.array_type = utah`, `implant.array_count = 1`, `implant.features = [sorted_units]`, `implant.bin_s = 0.02`, `implant.areas = [M1]` |

Rejected candidates (no producer can fill them, or another key holds the fact): `emg.gain_db` (no adapter knows it; V69 keeps it as a custom key with the MET-3 warning), `meg.system` (`device.vendor` and `device.model` hold it), a sample rate per modality (the stream holds decoder output, not samples; `implant.bin_s` is the only rate that changes how a consumer reads the frames).

## Proposal
Normative text: RC4 section 3.4 (MET-11 and 8 table rows), 12.5, and the registry files `spec/semconv/attributes/emg.yaml`, `meg.yaml`, `implant.yaml`.
- The registry gets the validator `non_empty_string_list` (a JSON array of strings, none of them `""`). The spec type text is "list of non-empty strings". An empty list is valid.
- `registered_values` (an open list, SC-4) may now be on a `string[]` key: it lists the registered item values.
- `emg`, `meg` and `implant` are now namespaces with keys. `eeg` and `fnirs` stay planned. A custom key in any of the five still gets the MET-3 warning.

## Compatibility
- Additive. Every RC4 vector keeps its verdict.
- A stream that wrote a custom key with one of the 8 names and a wrong type is now refused (NTS-META-TYPES). MET-3 already said SHOULD NOT, and no reference producer wrote one.
- The validators do not check MET-11 (the match of key and modality). It is content, like MET-6.

## Reference implementation
- Python `fidetype.conformance.checks.DEFINED_KEYS`, TypeScript `DEFINED_KEYS` (`sdk/typescript/src/checks.ts`), Rust `DEFINED_KEYS` (`sdk/rust/src/checks.rs`): 8 new keys; `PLANNED_NAMESPACES` is `eeg`, `fnirs`.
- The six adapters above write the keys.
- Vectors (`v0.1`): V83 (implant keys), V84 (emg keys), V85 (meg key) accept; V86 (`implant.bin_s` is a string), V87 (`meg.sensor_types` has an empty item) reject. Python = TypeScript = Rust.
- `tools/semconv/semconv.py --check` compares the new keys with the spec table, the three SDK tables and the accept vectors.

## Privacy and leakage
No personal data. `implant.areas` is anatomy at the level of a brain area, not a coordinate or an image. It holds no text of the user.

## Open questions
- SC-9: keys for `eeg` (montage, reference) and `fnirs` (wavelengths). Needs an EEG or fNIRS reference producer.
- Should `implant.bin_s` be `> 0` instead of `≥ 0`? The registry has no validator for `> 0` yet; a bin of 0 s has no meaning.
- Should the validators warn on a MET-11 mismatch (for example `emg.placement` with `device.modality = meg`)? An advisory check is cheap, but it is a new check in three SDKs.
