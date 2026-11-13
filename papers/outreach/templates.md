# Outreach message templates (M7-02)

*Drafts only. **The user is the sender** and owns every contact: the user picks the target, edits the text, checks the facts and sends it. Agents send nothing.*

- Targets, channels and timing: [`wiki/questions/partner-targets.md`](../../wiki/questions/partner-targets.md).
- Attach or link the [one-pager](outreach-one-pager.md).
- Placeholders are in `{CURLY_CAPS}`. Each message body is under 200 words.
- Send through the organisation's public channel only (contact form, partner page, GitHub issue, working-group list).
- Before sending: check that the benchmark page and the Paper 1 PDF link work. Paper 1 status: preprint in preparation; arXiv submission ready, arXiv endorsement pending. Do not say it is on arXiv until it is. PDF: https://github.com/zhangzibo/fidetype/blob/main/papers/paper1/final/fidetype-paper1.pdf
- Numbers below are from the final Paper 1 and committed result files (updated 2026-11-12). Results are from one intracortical participant; a second-participant test is in progress and has no results yet.

---

## 1. Implant BCI company

**Subject:** Calibrated confidence for {COMPANY}'s decoded text: an open format and a free evaluation

Hello {TEAM_OR_ROLE},

I work on Fidetype, an open-source (Apache-2.0) trust layer and stream format for neural text entry: {REPO_URL}.

On the public Brain-to-Text '25 data (CC0; one participant, 14 days), always committing sent wrong text for 19–61 % of sentences. With our commit rule calibrated on earlier days, the pooled wrong-commit rate on later days was 1.0–2.7 % (target 5 %), and no day was significantly above 5 %. On 300 no-signal streams, a plain threshold committed 198; with our evidence guard, none. The cost: current decoders commit only 15–39 % of sentences; the rest go to the user as choices. Paper (preprint in preparation): {PAPER_PDF_URL}.

{COMPANY_SPECIFIC_LINE, e.g. "Your work on {PRODUCT} commits text to users, so a bounded wrong-commit rate may be useful."}

My ask: would you look at the NeuralTextStream spec ({SPEC_URL}) and tell us what it is missing for your decoder? If useful, we can write an adapter and run the evaluation offline on output you choose to share, or you run our open scorer in-house and your data stays with you.

These are offline replays of public data from one participant, not clinical results.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}

---

## 2. Consumer EMG / EEG wearable maker

**Subject:** An open output format for {DEVICE}: confidence, alternatives, provenance

Hello {TEAM_OR_ROLE},

I maintain Fidetype, an open-source (Apache-2.0) project: {REPO_URL}. It defines NeuralTextStream, a vendor-neutral format for what a neural or muscle decoder outputs: token probabilities, n-best alternatives, calibrated confidence and a provenance record. A trust layer then decides to commit, offer choices or abstain.

On public forearm sEMG typing data (Toronto, CC BY 4.0), the trust layer cut wrong sentence commits from 54–96 % to below 0.5 %. The sentences were composed from isolated key presses, so this is not yet natural typing. The layer also runs live on Lab Streaming Layer input: on a BrainFlow synthetic board (no text information) it committed nothing and handled dropouts and reconnects. Details: {RESULT_URL}.

My ask: would you try emitting NeuralTextStream from one {DEVICE} decoder or event stream, and run our conformance check on it (`python -m fidetype.conformance check`)? Even a short note on where the spec does not fit your output would help. We can write the adapter from your public SDK.

No product or speed claims are made for {DEVICE}.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}

---

## 3. Research lab (public data or decoders)

**Subject:** Your {DATASET} on an open neural text-entry benchmark: a check request

Hello {LAB_NAME} team,

Thank you for releasing {DATASET} under {LICENCE}. We used it in Fidetype, an open-source trust layer and benchmark for neural text entry: {REPO_URL}.

{DATASET_SPECIFIC_RESULT, e.g. "On the B2T '25 copy task, calibrated on earlier days, our commit rule kept the pooled wrong-commit rate at 1.0–2.7 % on later days (target 5 %), on our decoder and on your published sentence. The bound covers the mix of days, not each day: one day ran at about 10 %, and we report a per-session fix."}

Your data is a track on our benchmark: {BENCHMARK_URL}. The splits hold only trial ids and text hashes; we redistribute nothing.

My ask, in order of effort:
1. Tell us if we have misread or misused your data or results.
2. Look at the NeuralTextStream spec ({SPEC_URL}) and say what your decoders would need.
3. If you like, submit one of your decoders to the benchmark. We can write the stream adapter.

The paper is a preprint in preparation (arXiv endorsement pending): {PAPER_PDF_URL}.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}

---

## 4. Standards body / open infrastructure maintainers

**Subject:** NeuralTextStream: decoded neural output with confidence; mapping to {STANDARD}

Hello {WG_OR_PROJECT},

I work on Fidetype, an open-source (Apache-2.0) project: {REPO_URL}. We publish NeuralTextStream v0.1 ({SPEC_URL}), a format for *decoded* neural output: token probabilities, n-best alternatives, calibrated confidence and provenance. It has a 60-check conformance suite, a reference implementation, and opt-in profiles for streaming trust events (FEP-0001) and for NTS over Lab Streaming Layer (FEP-0002). We have tested it on intracortical, MEG and forearm sEMG data, and live over LSL.

As far as we can tell, {STANDARD} does not yet cover decoded output with confidence. We do not want a rival format. We want NeuralTextStream to map cleanly to {STANDARD}.

My ask: may we {SPECIFIC_ASK, e.g. "join the working group as observers and share a short mapping of NeuralTextStream fields to P2731 terms" / "open an issue proposing an LSL stream-metadata profile for NeuralTextStream"}? We welcome any feedback on the spec, including "this belongs elsewhere".

The spec is at Development status. All fields can still change.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}
