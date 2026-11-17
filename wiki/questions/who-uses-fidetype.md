---
title: Who uses Fidetype, and why
type: question
tags: [planning, adoption, audiences, value-first, aac, trust, benchmark, roadmap]
sources: [case-study-langchain, case-study-opentelemetry, neural-input-landscape-2026]
updated: 2026-11-16
---

# Who uses Fidetype, and why

**Question asked (2026-11-15):** who has a reason to install Fidetype, what problem do they have today, and what do we offer them? The answer frames the "value first" phase [P14](roadmap-standard.md#p14-value-first-a-useful-toolkit-added-2026-11-15) of the roadmap. Each P14 item names the audiences that it serves.

**Why this page exists:** a format alone does not get adopters. People install a tool because it solves a problem for them today. The format then spreads as a side effect, as with LangChain ([LangChain case study](../sources/case-study-langchain.md)).

## Audiences
"Built today" uses three values: **yes** (works in the repository now), **partly** (parts exist, gaps listed), **no** (planned only).

| # | Audience | Their pain today | What Fidetype offers | Built today? |
|---|---|---|---|---|
| 1 | **BCI companies** (implant makers, EMG wristband makers) | Decoders make errors. A language model can write fluent text that the person did not intend. A regulator or a clinical partner asks for evidence of the error rate. Each company builds its own safety logic and logs | The **trust layer**: COMMIT / OFFER / WITHHOLD (ABSTAIN) for each utterance, with a measured wrong-commit guarantee (CRC / LTT bound with α, δ, method). Every decision is a `trust_decision` event. The **provenance ledger** gives an audit log from data to each committed output. Together they can serve as evidence for a regulatory file (our interpretation; not legal advice) | **Partly.** Trust layer and guarantees: yes ([trust decision](../concepts/trust-decision.md), [conformal risk control](../concepts/conformal-risk-control.md), [learn then test](../concepts/learn-then-test.md), `src/fidetype/trust/`). Decision-level ledger: yes, v0 ([provenance ledger](../concepts/provenance-ledger.md)); licence checks open (P5-03). Drop-in wrapper for any decoder: yes, v0 ([P14-03](roadmap-standard.md#p14-03-trust-layer-as-a-drop-in-wrapper): `fidetype.trust.calibrate`, logits or n-best in, null controls refuse a bad config; [quickstart](../../docs/trust-quickstart.md), [guarantee sheet](../../docs/trust-guarantee.md)); validation on public replay sets open. On-device core: no (P5-05) |
| 2 | **AAC app makers** (assistive and alternative communication) | Each BCI has its own output. An AAC app must add custom code for each device, so most apps support no BCI at all | **One standard input (NTS)**, so that every BCI works with their app, as USB HID lets every keyboard work with every computer. The app reads only committed text (and, as an option, offered choices) over WebSocket | **Partly.** NTS spec and SDKs: yes ([NTS spec](../concepts/nts-spec.md), Python, TypeScript, Rust). WebSocket binding and Collector WebSocket exporter: yes ([WebSocket input](../concepts/websocket-input.md), [collector](../concepts/collector.md)). OS input exporters (TSF, IME): no (P3). An example integration in a real AAC app: no ([P14-09](roadmap-standard.md#p14-09-example-aac-integration)) |
| 3 | **Research labs** | Results across labs are hard to compare. Each paper uses its own metric, split and controls. Replay of other public datasets needs new loader code each time | A **fair benchmark**: NTS submissions, fixed splits, required shuffled and null controls, metrics with latency and wrong-commit rate, and "safe WPM at α". **Replay adapters** for 6 public datasets give the same stream from each one | **Partly.** Benchmark v0.1 with 3 tracks and a static leaderboard: yes ([open benchmark](../concepts/open-benchmark.md), `benchmark/`). Replay adapters for 6 datasets (B2T '25, Willett, KT-sEMG, Toronto sEMG, SpanishBCBL, emg2qwerty): yes (P4-01, [public datasets](public-datasets.md)). Safe-WPM column: yes, on 3 tracks + 2 replay sets ([P14-05](roadmap-standard.md#p14-05-headline-metric-safe-words-per-minute), [docs/safe-wpm.md](../../docs/safe-wpm.md)). Public site and pull-request scoring: no (P6-03, P13-03) |
| 4 | **Clinical trials** | Recordings and decoder outputs are stored in local formats. A later audit or re-analysis cannot always say which data, weights and settings made an output | **Standard recording and replay with provenance:** NTS files carry the stream header, timing, decoder identity and weights hash. Replay gives the same stream again. The ledger links each output to its data, weights and calibration | **Partly.** NTS file binding and replay: yes ([NTS spec](../concepts/nts-spec.md), P4-01 adapters). Conformance level `provenance`: yes ([conformance suite](../concepts/conformance-suite.md)). Ledger v0: yes; full lineage and consent records: no (P5-03, P5-04). Use in a real trial: no (**externally blocked**: partners, ethics) |
| 5 | **Small teams and hobbyists** (OpenBCI and similar boards) | No pretrained decoder to start from. No safe way to decide when decoded text is good enough to use. Live input, decoder and UI must be joined by hand | **End to end:** pretrained baseline decoders, the trust layer and live input from tools they already use (LSL, BrainFlow, OpenBCI boards), with a demo to copy | **Partly.** LSL binding and BrainFlow → LSL bridge: yes ([LSL input](../concepts/lsl-input.md), [BrainFlow](../entities/brainflow.md), `src/fidetype/adapters/brainflow_bridge.py`). Browser demo: yes, simulated input (`demo/`). Pretrained decoders with one-line load: no ([P14-01](roadmap-standard.md#p14-01-pretrained-decoders-one-line-load-and-decode)). One-command live path: no ([P14-04](roadmap-standard.md#p14-04-live-decode-from-lab-tools)). Recorded EMG demo: no ([P14-06](roadmap-standard.md#p14-06-visible-demo-recorded-emg-to-text)) |

> **Our take:** audience 1 (BCI companies) and audience 2 (AAC app makers) are the two sides of one market. Companies emit NTS if apps read it. Apps read NTS if devices emit it. The trust layer and the benchmark give each side a reason to move first, before the other side exists. Audiences 3 and 5 are the fastest to reach, because they need no partner and no approval.

## Which P14 items serve which audience
| Audience | P14 items |
|---|---|
| 1 BCI companies | P14-03, P14-05, P14-07, P14-08 |
| 2 AAC app makers | P14-09 (and P14-06 as the input source) |
| 3 Research labs | P14-01, P14-02, P14-03, P14-04, P14-05, P14-08 |
| 4 Clinical trials | P14-08 (plus existing P5-03, P5-04) |
| 5 Small teams and hobbyists | P14-01, P14-02, P14-03, P14-04, P14-06, P14-07 |

Details, dependencies and done criteria: [roadmap P14](roadmap-standard.md#p14-value-first-a-useful-toolkit-added-2026-11-15).

## Limits
- Fidetype is research software. It is not a medical device. No item on this page is a medical or legal claim.
- Regulatory use of the trust evidence (audience 1) and clinical use (audience 4) need outside review: **externally blocked** (P5-06, P10-05).
- Pretrained weights from emg2qwerty are research only (CC BY-NC-SA 4.0). Clean weights come only from CC0 / CC BY data ([`LICENSES/DATA.md`](../../LICENSES/DATA.md)).

## Related pages
- [Long-term roadmap](roadmap-standard.md) (P14 value first)
- [Partner targets](partner-targets.md)
- [Open-source playbook](open-source-playbook.md)
- [Direction decision](direction-decision.md)
- [Architecture](architecture.md)
