# Device support matrix

<!-- GENERATED FILE. DO NOT EDIT. Made by `python -m fidetype.adapters.registry` from the ADAPTER_INFO of
     each adapter module and src/fidetype/adapters/planned.py (roadmap P4-15).
     CI fails when this page and the metadata differ (tests/test_adapter_registry.py). -->

This page tells you which devices, recording files and public datasets work with Fidetype, on what data each adapter ran, and its known limits. A script makes the page from the metadata in the code. The full catalogue (licences, tests, modules) is [adapters.md](adapters.md).

**Support:** 0 real device, 15 replay only, 2 synthetic only, 16 untested (planned).

**No adapter has run on a real device yet.** The project has no EEG, EMG or MEG hardware. Real-device tests are roadmap P4-06 and M6-12 (externally blocked: they need hardware and volunteers).

## Support levels

| Support | Meaning |
|---|---|
| `real-device` | It ran on a real device (column "Real device"). The evidence is in the repository. |
| `replay-only` | It ran on real recorded data (public dataset files, real recording files or real decoder output). It never ran on a live device. |
| `synthetic-only` | Its tests use synthetic data only (files made by the test, a fake or synthetic board, a loopback of the real protocol library with synthetic streams). |
| `untested` | No test runs it. Planned rows only (no code). |

The status column uses the catalogue levels: `tested`: CI tests run it, and it ran on the real thing it reads: real public dataset files, or the real protocol library (pylsl, websockets, BrainFlow) in a loopback; `experimental`: Code and CI tests on synthetic data exist. It has not run on real recordings or a real device. The registry refuses `tested` without real data, except for a transport (real protocol library in a loopback) and the synthetic source. The registry also refuses `real-device` or `replay-only` without a test or result in the repository (column "Tests cover", "Evidence").

Transports: `file` = reads recording or decoder-output files; `dataset` = reads the files of a public dataset; `lsl` = Lab Streaming Layer (live, network); `brainflow` = BrainFlow board API (live, in the same process); `websocket` = WebSocket (live, network); `in-process` = a Python call in the same process; `generated` = makes its own synthetic signal.

## Live devices and signal sources

| Device or format | Reader id | Modality | Transport | Status | Support | Tests cover | Known limits | Docs |
|---|---|---|---|---|---|---|---|---|
| BrainFlow boards (OpenBCI Cyton, Ganglion and others) -> LSL, and in-process in fidetype live (BrainFlowSource). CI uses the BrainFlow Synthetic board and a fake board only (extra `[brainflow]`) | `brainflow` | any | brainflow, lsl | `experimental` | `synthetic-only` | CI: the BrainFlow Synthetic board (sine waves and noise, no text) and a fake board; the bridge into a real pylsl loopback. | No real board is tested (P4-06, externally blocked: needs hardware). Fixed timing only: a board gives no key-onset markers. No reconnect in fidetype live. | [docs](../wiki/entities/brainflow.md) |
| Any raw-signal LSL stream and its marker stream (LSLSource of fidetype live; reconnect P4-11) (extra `[lsl]`) | `lsl-signal-source` | any | lsl | `tested` | `replay-only` | CI: the synthetic typist over fake inlets and a real pylsl loopback (loss and reconnect). The CI job replays the real KT-sEMG run3 over LSL into fidetype live --source lsl. Evidence: [kt_lsl_replay.py](../tools/ci/kt_lsl_replay.py). | No real amplifier has sent its LSL stream to it (P4-06). Clock correction is tested on one machine only. | [docs](live-decode.md) |
| Synthetic typist signal with key-press markers (SyntheticSource; no real data) | `synthetic-typist` | other | generated | `tested` | `synthetic-only` | CI: the synthetic typist signal through fidetype live and the adapter conformance helper. | Synthetic signal only. It carries no brain or muscle data. Use it to test the plumbing. | [docs](live-decode.md) |

## Recording files

| Device or format | Reader id | Modality | Transport | Status | Support | Tests cover | Known limits | Docs |
|---|---|---|---|---|---|---|---|---|
| EDF, EDF+ (continuous) and BDF files (many EEG, EMG and sleep systems) | `edf` | any | file | `tested` | `replay-only` | CI: synthetic EDF, EDF+ and BDF files made by the test. Real: PhysioNet EEGMMIDB EDF+ and the MNE test EDF+ / BDF files, in a local test (values equal MNE within one digital step; skipped in CI without the files). Evidence: [test_adapter_files_real.py](../tests/test_adapter_files_real.py). | Continuous files only: EDF+D (discontinuous) raises an error. A file, not a live device. | [docs](adapters.md#edf) |
| OpenBCI GUI v5+ raw recordings (Cyton, Cyton + Daisy, Ganglion) | `openbci-gui` | eeg | file | `tested` | `replay-only` | CI: synthetic GUI files and packet drops (Sample Index jumps). Real: the OpenBCI GUI v6 sample file (Cyton, millisecond time stamps) and two GUI v5 recordings (Cyton 8 ch; Cyton + Daisy 16 ch), local tests. Evidence: [test_adapter_files_real.py](../tests/test_adapter_files_real.py), [test_adapter_openbci_gui_real.py](../tests/test_adapter_openbci_gui_real.py). | No real recording with non-zero markers (P4-19). The Ganglion Sample Index rule is not checked (P4-20). GUI v4 files are refused. A file, not a live board. | [docs](adapters.md#openbci-gui) |

## Public datasets (recorded data)

| Device or format | Reader id | Modality | Transport | Status | Support | Tests cover | Known limits | Docs |
|---|---|---|---|---|---|---|---|---|
| Brain-to-Text '25 (Card et al. 2024, participant T15, attempted speech): phoneme CTC logits | `b2t25` | intracortical | dataset | `tested` | `replay-only` | CI: synthetic phoneme logits. Real: the T15 copy-task file of the public dataset, in a local test (skipped in CI without the file). Evidence: [test_adapter_b2t25.py](../tests/test_adapter_b2t25.py). | Replays recorded decoder output of one participant (T15). No live intracortical source. The published decoder weights have no hash (conformance check PV-WEIGHTS fails). | [docs](../wiki/entities/brain-to-text-25.md) |
| emg2qwerty (Meta, wrist sEMG during touch typing, 108 users): key presses per prompt (extra `[emg2qwerty]`) | `emg2qwerty` | emg | dataset | `tested` | `replay-only` | CI: synthetic HDF5 sessions made by the test. Real: the emg2qwerty sessions in P11-01 (decoder training, 2,445 streams) and P6-02 (benchmark baselines), local runs. Evidence: [2026-11-16-p11-01-emg-decoder](../experiments/2026-11-16-p11-01-emg-decoder/results.md), [2026-11-16-p6-02-scorer](../experiments/2026-11-16-p6-02-scorer/results.md). | Data CC BY-NC-SA 4.0: research use only. Recorded sessions only; the wristband that recorded them is not a supported device. | [docs](../wiki/entities/emg2qwerty.md) |
| KT-sEMG (Nokia, forearm sEMG during natural typing): key presses, LDA reference decoder | `kt-semg` | emg | dataset | `tested` | `replay-only` | CI: synthetic key logs and signal files. The CI job tools/ci/kt_lsl_replay.py downloads the real KT-sEMG run3 (SHA-256 pinned) and trains the reference decoder on it. Evidence: [kt_lsl_replay.py](../tools/ci/kt_lsl_replay.py). | One public dataset. In the CI job the LDA reference decoder is in-sample (a plumbing check, no accuracy claim). | [docs](../wiki/entities/kt-semg-dataset.md) |
| KT-sEMG recording replayed as live raw-signal LSL streams (fidetype live replay-kt) (extra `[lsl]`) | `kt-semg-lsl-replay` | emg | dataset, lsl | `tested` | `replay-only` | CI: the real KT-sEMG run3 (77 s, 32 channels, 2000 Hz) replayed over a real LSL loopback into fidetype live; the NTS output is checked. Evidence: [kt_lsl_replay.py](../tools/ci/kt_lsl_replay.py). | A replay of a recording, not a live device. The guard never commits on 77 s (in-sample plumbing model). | [docs](live-decode.md) |
| SpanishBCBL typing MEG (Brain2Qwerty data): ConvCTC output per typing segment | `spanishbcbl-meg` | meg | dataset | `tested` | `replay-only` | CI: synthetic log-probs (conformance helper and restamp tests). Real: the ConvCTC output on the SpanishBCBL MEG segments of the 5 M1-09 runs (1,074 streams each), rebuilt with this adapter's header by restamp_meg, reach conformance level provenance (M5-13, local). Evidence: [2026-11-11-m1-09-async-full](../experiments/2026-11-11-m1-09-async-full/results.md), [restamp_meg.py](../src/fidetype/decoders/restamp_meg.py). | Data CC BY-NC 4.0: research only. Recorded MEG only: MEG needs a lab system, so no live MEG source exists. | [docs](../wiki/entities/spanishbcbl-dataset.md) |
| SpanishBCBL typing MEG: file discovery, behavioural logs, clock alignment, typed text (extra `[data]`) | `spanishbcbl-reader` | meg | dataset | `tested` | `replay-only` | CI: synthetic file names, logs and clocks. Real: one finished S25 block of the local cache (integration test, skipped in CI). Evidence: [test_data_spanishbcbl.py](../tests/test_data_spanishbcbl.py). | Data CC BY-NC 4.0: research only. Needs MNE for the raw MEG files. | [docs](../wiki/entities/spanishbcbl-dataset.md) |
| Toronto sEMG typing dataset (Achituve et al. 2025, forearm sEMG, 19 participants): key presses | `toronto-semg` | emg | dataset | `tested` | `replay-only` | CI: synthetic Intan RHD files made by a test writer. Real: the Toronto CleanData files, in a local test (skipped in CI without the data). Evidence: [test_adapter_toronto_semg.py](../tests/test_adapter_toronto_semg.py). | Recorded sessions only; no live Intan source. | [docs](../wiki/entities/toronto-semg-typing-dataset.md) |
| Willett et al. 2021 handwriting BCI: real-time RNN character output (extra `[data]`) | `willett-handwriting` | intracortical | dataset | `tested` | `replay-only` | CI: synthetic sessions. Real: sentences.mat of the public archive (SHA-256 pinned) in the P6-02 benchmark baselines (local). Evidence: [2026-11-16-p6-02-scorer](../experiments/2026-11-16-p6-02-scorer/results.md). | Replays recorded real-time RNN output of one participant (T5). The RNN weights have no hash (PV-WEIGHTS fails). | [docs](../wiki/entities/willett-handwriting-2021.md) |

## Decoder outputs and transports

| Device or format | Reader id | Modality | Transport | Status | Support | Tests cover | Known limits | Docs |
|---|---|---|---|---|---|---|---|---|
| Any CTC decoder: (T, V) logits, probabilities or log-probabilities (.npy / .npz, batches) | `ctc-logits` | any | file, in-process | `tested` | `replay-only` | CI: synthetic logits, probabilities and padded batches. Real: the output of our emg2qwerty decoder (P11-01: 2,445 streams, all trust-ready, local run); the pretrained decoders call it on each decode. Evidence: [2026-11-16-p11-01-emg-decoder](../experiments/2026-11-16-p11-01-emg-decoder/results.md). | The input must be CTC scores (T, V) with a known vocabulary. It cannot check that the scores come from the decoder that the header names. | [docs](../wiki/concepts/ctc-logits-adapter.md) |
| Lab Streaming Layer: NTS in (LSL inlets -> trust layer) and out (NTS files -> LSL outlets) (extra `[lsl]`) | `lsl` | any | lsl | `tested` | `replay-only` | CI: fake inlets (header mapping, clock correction, gaps, loss, reconnect) and a real pylsl outlet -> inlet loopback with synthetic streams. Real (P4-21, local): the 816 B2T '25 M4-06 test trials over a real pylsl loopback; hypothesis route decisions equal the in-process replay and the batch harness (816 / 816); 161,503 double64 frames bit-equal. Evidence: [2026-11-22-p4-21-lsl-replay](../experiments/2026-11-22-p4-21-lsl-replay/results.md). | One machine only (localhost). The real replay is local (not in CI), unpaced, and does not run the frames-route trust decisions. No live device. | [docs](../wiki/concepts/lsl-input.md) |
| Any text-only decoder: CSV id,text or JSON Lines n-best lists -> hypothesis stream | `text-nbest` | any | file, in-process | `tested` | `replay-only` | CI: synthetic CSV and JSON Lines n-best files. Real: the item check (normalise_item) on the KT-sEMG LDA n-best lists through the trust drop-in (P5-33, local); read_csv and read_jsonl on real B2T '25 decoder output (1,718 online 1-best texts, 816 M4-06 10-best lists with evidence): exact round trip, 0 conformance failures (P4-22, local). Evidence: [2026-11-21-p5-33-withhold](../experiments/2026-11-21-p5-33-withhold/results.md), [2026-11-22-p4-22-nbest-readers](../experiments/2026-11-22-p4-22-nbest-readers/results.md). | The real CSV / JSON Lines files come from our converter (no local tool writes these forms); the real texts have no CSV quoting cases. One dataset family. | [docs](../wiki/concepts/text-nbest-adapter.md) |
| WebSocket binding nts-ws/0.1 (FEP-0004): NTS in both directions, decisions out (extra `[ws]`) | `ws` | any | websocket | `tested` | `replay-only` | CI: sans-IO cores (order, gaps, resume, auth) and a real server and client on localhost with synthetic streams. Real: the 816 Brain-to-Text '25 test trials over WebSocket, same decisions as the in-process replay (M6-11, local). Evidence: [b2t_replay_ws.py](../experiments/2026-11-13-m6-11-ws/b2t_replay_ws.py). | Localhost only; no test across a real network. | [docs](../wiki/concepts/websocket-input.md) |

## Planned (no code, not supported)

These rows have no code. Their support is `untested`. Each row names its roadmap item.

| Device, dataset or format | Id | Kind | Modality | Support | Roadmap |
|---|---|---|---|---|---|
| BIDS-EEG datasets (for example OpenNeuro EEG studies) and MOABB-listed BCI datasets | `bids-eeg` | dataset-reader | eeg | `untested` | P14-42 |
| BrainVision files (.vhdr / .eeg / .vmrk) | `brainvision-file` | file-reader | eeg | `untested` | P14-42 |
| Brain Products amplifiers (LiveAmp, actiCHamp) through their LSL connector | `brainvision-lsl` | device-source | eeg | `untested` | P4-05 |
| Consumer sEMG wristbands (for example Myo-class bands) | `consumer-emg-band` | device-source | emg | `untested` | P4-05 |
| Open low-cost sEMG wristband (our reference design) as NTS over LSL | `emg-wristband` | device-source | emg | `untested` | P18-02 |
| Emotiv EPOC X / Insight | `emotiv` | device-source | eeg | `untested` | P4-05 |
| fNIRS systems that stream LSL (for example NIRx, Artinis) | `fnirs-lsl` | device-source | fnirs | `untested` | P4-05 |
| GDF files (for example BCI Competition IV 2a / 2b) | `gdf` | file-reader | eeg | `untested` | P14-42 |
| Public inner / imagined speech EEG datasets (for example 'Thinking out loud', Kara One) | `inner-speech-eeg` | dataset-replay | eeg | `untested` | P14-42 |
| Interaxon Muse 2 / Muse S headband (4-channel EEG) | `muse` | device-source | eeg | `untested` | P4-05 |
| Neurosity Crown (8-channel EEG) | `neurosity-crown` | device-source | eeg | `untested` | P4-05 |
| OpenBCI Cyton / Ganglion on a real board (code exists in brainflow; a real-board test does not) | `openbci-cyton-board` | device-source | eeg | `untested` | P4-06 |
| OPM-MEG systems (wearable MEG) | `opm-meg` | device-source | opm-meg | `untested` | P4-05 |
| g.tec Unicorn Hybrid Black (8-channel EEG) | `unicorn` | device-source | eeg | `untested` | P4-05 |
| XDF files (LabRecorder recordings of LSL streams) | `xdf` | file-reader | any | `untested` | P14-42 |
| ZuCo (EEG and eye tracking during natural reading) | `zuco` | dataset-replay | eeg | `untested` | P14-42 |

## Add or change a row

Edit the `ADAPTER_INFO` of the adapter module (fields `status`, `support`, `hardware_tested`, `real_data_evidence`, `transport`, `test_covers`, `limits`), then run `python -m fidetype.adapters.registry`. Do not edit this page. See [CONTRIBUTING.md, section 7](../CONTRIBUTING.md#7-adapters-add-a-decoder-or-a-device).
