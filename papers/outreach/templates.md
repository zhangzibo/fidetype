# Outreach message templates (M7-02)

*Drafts only. **The user is the sender** and owns every contact: the user picks the target, edits the text, checks the facts and sends it. Agents send nothing.*

- Targets, channels and timing: [`wiki/questions/partner-targets.md`](../../wiki/questions/partner-targets.md).
- Attach or link the [one-pager](outreach-one-pager.md).
- Placeholders are in `{CURLY_CAPS}`. Each message body is under 200 words.
- Send through the organisation's public channel only (contact form, partner page, GitHub issue, working-group list).
- Before sending: check that the benchmark page and (for waves 2+) the preprint links work.

---

## 1. Implant BCI company

**Subject:** Calibrated confidence for {COMPANY}'s decoded text: an open format and a free evaluation

Hello {TEAM_OR_ROLE},

I work on Fidetype, an open-source (Apache-2.0) trust layer and stream format for neural text entry: {REPO_URL}.

On the public Brain-to-Text '25 data (CC0), we ran our trust gate on the decoder output published with the dataset. Wrong sentence commits fell from 19.4 % to 4.4 % of trials, at a 4.3 % cost in effective typing speed. A simple "always offer the n-best" policy is close behind, and we report it next to our result. Details: {RESULT_URL}.

{COMPANY_SPECIFIC_LINE, e.g. "Your work on {PRODUCT} commits text to users, so a bounded wrong-commit rate may be useful."}

My ask: would you look at the NeuralTextStream spec ({SPEC_URL}) and tell us what it is missing for your decoder? If useful, we can write an adapter and run the evaluation offline on output you choose to share, or you run our open scorer in-house and your data stays with you.

These are offline replays of public data, not clinical results.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}

---

## 2. Consumer EMG / EEG wearable maker

**Subject:** An open output format for {DEVICE}: confidence, alternatives, provenance

Hello {TEAM_OR_ROLE},

I maintain Fidetype, an open-source (Apache-2.0) project: {REPO_URL}. It defines NeuralTextStream, a vendor-neutral format for what a neural or muscle decoder outputs: token probabilities, n-best alternatives, calibrated confidence and a provenance record. A trust layer then decides to commit, offer choices or abstain.

On public forearm sEMG typing data (Toronto, CC BY 4.0), the trust layer cut wrong sentence commits from 54–96 % to below 0.5 %. The sentences were composed from isolated key presses, so this is not yet natural typing. Details: {RESULT_URL}.

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

{DATASET_SPECIFIC_RESULT, e.g. "On the B2T '25 copy task, our trust gate on your published decoder output cut wrong commits from 0.194 to 0.044 of trials at −4.3 % eWPM. An always-offer baseline is close behind and is reported."}

Your data is a track on our benchmark: {BENCHMARK_URL}. The splits hold only trial ids and text hashes; we redistribute nothing.

My ask, in order of effort:
1. Tell us if we have misread or misused your data or results.
2. Look at the NeuralTextStream spec ({SPEC_URL}) and say what your decoders would need.
3. If you like, submit one of your decoders to the benchmark. We can write the stream adapter.

The draft paper is {PREPRINT_URL_OR "available on request"}.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}

---

## 4. Standards body / open infrastructure maintainers

**Subject:** NeuralTextStream: decoded neural output with confidence; mapping to {STANDARD}

Hello {WG_OR_PROJECT},

I work on Fidetype, an open-source (Apache-2.0) project: {REPO_URL}. We publish NeuralTextStream v0.1 ({SPEC_URL}), a format for *decoded* neural output: token probabilities, n-best alternatives, calibrated confidence and provenance. It has a 60-check conformance suite and a reference implementation. We have tested it on intracortical, MEG and forearm sEMG data.

As far as we can tell, {STANDARD} does not yet cover decoded output with confidence. We do not want a rival format. We want NeuralTextStream to map cleanly to {STANDARD}.

My ask: may we {SPECIFIC_ASK, e.g. "join the working group as observers and share a short mapping of NeuralTextStream fields to P2731 terms" / "open an issue proposing an LSL stream-metadata profile for NeuralTextStream"}? We welcome any feedback on the spec, including "this belongs elsewhere".

The spec is at Development status. All fields can still change.

Best regards,
{SENDER_NAME}
{SENDER_ROLE_AND_LINK}
