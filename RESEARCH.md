# Research status

Last update: 2026-11-22.

This page says what the Fidetype research has shown so far, what failed, and what comes next. You do not need it to use the toolkit: for that, start at the [README](README.md).

**Read this first.** Every result below is an offline replay of public datasets. None is a study with users. We fix each test plan before we see its numbers, and we keep the negative results.

## The questions

The research asks three questions:

1. **Safe self-improvement.** Can a decoder learn from the user's own corrections while its stated error bound stays valid after each update?
2. **Faithful language models.** Can a language model make decoded text better without adding text that the brain signal does not support?
3. **A new sensor in minutes.** Can a model trained on one signal (for example EMG) help a new sensor or a new user start with only minutes of labelled data?

## Terms

| Term | Meaning |
|---|---|
| T15, T12 | Two public implant datasets of attempted speech (Brain-to-Text '25 and Brain-to-Text '24). Each comes from one participant |
| EMG | Electromyography: muscle signals, here from wrist sensors during typing |
| CER, WER | Character and word error rate. 0 is perfect; 1 means almost every character or word is wrong |
| Safe WPM | Words per minute that the trust layer commits correctly. Wrong commits earn nothing. Text that the guard withholds costs time |
| No-BCI baseline | A typing speed that the same person could reach without a BCI (for example gaze typing) |
| Calibration draw | One random choice of the calibration data. A result is reliable only when it holds across many draws |
| [x, y] | A 95 % confidence interval |

## What works

- **The wrong-commit bound holds after updates.** The trust layer keeps its stated error bound when it learns only from items that it showed to the user. An audit of other thresholds found 0 violations in 200 checks ([details](wiki/questions/frontier-f1-online-guarantees.md)).
- **Worse decoders are refused.** The update gate refuses worse and broken decoders under partial feedback ([details](wiki/questions/frontier-e2-self-teaching.md)). A re-calibration rule for the same decoder refused 0 of 8 good updates and still refused every broken or worse decoder ([details](experiments/2026-11-18-p15-24-recal-rule/results.md)).
- **Unsupported text is blocked.** Language-model rescoring lowers the WER on T15. A grounding check stops every commit when the brain signal is swapped for another sentence's signal. A certified bound on fluent but wrong text commits 36 sentences on T15, and 34 of them are right ([details](wiki/questions/frontier-e3-hallucination.md)).
- **EMG typing beats the no-BCI baseline, narrowly.** With the trust layer and one sentence guard, EMG typing gives 5.90 [3.45, 8.89] safe WPM against a no-BCI baseline of 3.09, across calibration draws. A repeat with new draws gives 5.99 [3.52, 8.96]. This holds for 8 users and one test set of the emg2qwerty data (research-only licence) ([details](experiments/2026-11-21-p11-19-multi-split/results.md), [repeat](experiments/2026-11-22-p11-28-bx3-headroom/results.md)).
- **Faster first words.** A hybrid guard that commits word by word shows the first correct word about 5 times sooner than a guard that waits for the full sentence (median 2.7 s against 14.0 s). Its total speed gain is not robust ([details](experiments/2026-11-19-p5-28-hybrid-prefix/results.md)).

## What failed or is not shown yet

- **Implant speed is not reliably above the baseline.** On T15, safe WPM is 5.18 [0.00, 6.99] across 40 calibration draws, against a gaze-typing baseline of 4.02. That is above on average, but the interval contains 4.02 ([details](experiments/2026-11-20-p15-29-calibration-ci/results.md)). On T12 it is below: 2.37 [1.34, 3.62] against 4.11, because the T12 decoder is too weak ([details](experiments/2026-11-19-p15-26-replication/results.md)).
- **The language-model test failed its main rule.** With a language model, fluent but wrong commits were not lower than without it. The WER gain on T15 does not repeat on T12 ([details](wiki/questions/frontier-e3-hallucination.md)).
- **A learned commit score is not certified.** It raises speed, but its rate of fluent wrong text has no certified bound yet ([details](experiments/2026-11-19-p15-22-llm-learned/results.md)).
- **No new sensor in minutes yet.** In the first test, with 3 to 100 labelled minutes of implant handwriting, no model read the signal well (best CER 0.767) ([details](experiments/2026-11-19-p15-08-e1-cross-body/results.md)). With 10 or 30 minutes, EMG pretraining gave no valid gain over text-only pretraining on 5 seeds. At 10 minutes a control test failed: the models mostly learned which texts are common, not the signal ([details](experiments/2026-11-22-p15-41-more-seeds/results.md)). At 3 minutes EMG pretraining was better on 5 of 5 seeds, but the CER there is about 0.80, far from usable.
- **Only with all data does EMG pretraining help.** With all 506 labelled minutes, a model pretrained on EMG trains reliably (CER 0.360 and 0.431 on 2 seeds), where other starts fail on one or both seeds. This was not the pre-registered question ([details](experiments/2026-11-19-p15-08-e1-cross-body/results.md)).

The full internal records are in [`experiments/`](experiments/README.md) and the research notebook [`wiki/`](wiki/index.md).

## Roadmap

This roadmap is not law. It shows the current plan, and the plan changes when results change. Items that need outside people (reviewers, partners, volunteers) have no fixed date.

**Done**

- Release 0.1.0 of the Python, TypeScript and Rust SDKs on PyPI, npm and crates.io.
- The NTS 1.0 release candidate 4 (a draft, open for comment) with a conformance suite that all three SDKs pass.
- The trust layer with a guarantee sheet, no-signal controls and an audit log.
- An open benchmark with fixed splits on seven public datasets, and the safe-WPM metric. A newer safe-WPM definition with a reading cost is adopted.

**Now**

- A low-data training recipe, so that a new sensor can start with minutes of data.
- Stronger checks that stream faults (for example frames in the wrong order) cannot make the trust layer commit.
- The benchmark code and leaderboard move to the newer safe-WPM definition.
- Downloadable pretrained decoders with checked weights.

**Next**

- NTS 1.0 Stable, after review by at least two outside decoder groups.
- More SDK languages, and a more complete Collector.
- Live inputs from lab devices, and a demo with real hardware.
- Output beyond text: intents and control signals, with trust rules for actions.
- Later: a literature-first look at reading emotion and memory signals.

Detailed internal plan: [roadmap](wiki/questions/roadmap-standard.md) and [research direction](wiki/questions/north-star.md).
