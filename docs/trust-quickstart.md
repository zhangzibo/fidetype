# Add trust to your decoder in 10 minutes

This page is for a team that already has a decoder (brain or muscle signals to text). At the end, your decoder output goes through the Fidetype trust layer. For each utterance you get one of three actions, with a stated wrong-commit guarantee and an audit log:

| Action | What your app does |
|---|---|
| `commit` | Use the text (`result.text`) |
| `offer` | Show the choices (`result.choices`); the user picks one or rejects all |
| `withhold` | Show nothing; ask again or let the user type |

You do not change your decoder. You do not need to learn the NeuralTextStream (NTS) format: the wrapper writes valid NTS underneath. Read the [guarantee sheet](trust-guarantee.md) before you rely on the numbers.

## What you need

- Python 3.12 or later.
- Your decoder output for **labelled** utterances: what the decoder gave, and what the user meant. Use 400 or more. With fewer than about 120, the guard cannot certify any commit and only offers or withholds.
- One of two output kinds:

| Your decoder gives | Input kind | Also give |
|---|---|---|
| A `(T, V)` matrix of CTC scores per utterance (logits, log-probabilities or probabilities; numpy or torch) | `logits` | `vocab` (the token of each column), `blank`, and a word list `lexicon` or your own `decode_fn` |
| A ranked list of texts with log scores per utterance (n-best) | `nbest` | `null_inputs`: your decoder's n-best output on null input (no signal, or a time-shuffled recording), about 100 lists |

## Step 1 (2 min): install

The package is not on PyPI yet. Install it from GitHub:

```sh
pip install "git+https://github.com/zhangzibo/fidetype.git"
```

Or from a clone: `git clone https://github.com/zhangzibo/fidetype.git`, then `cd fidetype` and `pip install .`.

## Step 2 (2 min): run the example

The example uses synthetic data only. It needs no data download and no network. It takes about one minute on a laptop CPU.

```sh
python examples/trust_dropin_quickstart.py --out out/
```

(With the `git+` install, download [`examples/trust_dropin_quickstart.py`](../examples/trust_dropin_quickstart.py) first.)

It calibrates two guards (logits and n-best), prints each guarantee sheet, decides on 200 new utterances and writes `out/guard-*.json` and `out/audit-*.jsonl`. The end of the output looks like this (numbers change with the data):

```text
  uniform            0/100 commits (allowed 5): PASS
  shuffled           1/100 commits (allowed 5): PASS
...
[logits] 200 test utterances: 69 commit, 0 offer, 131 withhold; wrong commits 1/200 = 0.005
```

## Step 3 (4 min): use your own data

Replace the synthetic decoder with yours. Only the calibration call changes between the two input kinds.

**Logits (CTC):**

```python
import fidetype.trust as ft

# cal_logits: list of (T, V) arrays from your decoder; cal_texts: what the user meant.
guard = ft.calibrate(
    cal_logits, cal_texts,
    vocab=["_", *"abcdefghijklmnopqrstuvwxyz", " "],  # column order of your logits
    blank="_",                                          # the CTC blank column (index or token)
    lexicon=my_word_list,                               # or: decode_fn=my_beam_search_with_lm
    alpha=0.05, delta=0.1,
    decoder_name="acme-emg-decoder", decoder_version="2.1", modality="emg",
)
print(guard.sheet)
```

- `decode_fn` is your own text decoder: `f(log_probs) -> [(text, log_score), ...]`, best first. It gets the `(T, V)` natural-log probabilities after the frame temperature of the calibration.
- A Hugging Face style `vocab.json` or a `tokens.txt` file also works as `vocab` (give the path). Use `word_delimiter="|"` if your vocabulary marks word boundaries with `|`.

**n-best:**

```python
guard = ft.calibrate(
    cal_nbest, cal_texts,               # cal_nbest[i] = [("turn on the light", -0.2), ("turn on the night", -1.9), ...]
    null_inputs=null_nbest,             # your decoder's n-best on no-signal or time-shuffled recordings
    alpha=0.05, delta=0.1, decoder_name="acme-speech-bci", modality="intracortical",
)
```

Each n-best item can be a string, a `(text, score)` pair, or a dict with `text`, `score` and optional `char_confidences` (one value in [0, 1] per character; the hallucination guard uses them). Scores are log-domain: higher is better.

Same call with pairs: `ft.wrap(zip(cal_inputs, cal_texts), alpha=0.05, ...)`.

## Step 4 (1 min): decide, keep the audit log, save

```python
r = guard.decide(new_output, utterance_id="session7-trial12")   # or: guard(new_output)
if r.action == "commit":
    app.type(r.text)
elif r.action == "offer":
    app.show_choices(r.choices)
# "withhold": show nothing

guard.write_audit("audit.jsonl")    # header (config_id + guarantee sheet), then one record per decision
guard.save("guard.json")            # numbers and settings only: no signal, no text
guard = ft.load("guard.json")       # add decode_fn=... if you calibrated with your own decoder
```

`TrustResult` fields: `action`, `text`, `choices`, `p_top1` (calibrated probability that the top text is right), `guard_risk`, `reason`, `raw_action` (`COMMIT`, `OFFER`, `ABSTAIN`, ...), `config_id`, `seq`, `event` (the NTS `trust_decision` event).

`guard.nts_events(x)` gives the NTS events that the guard reads for one input. Write them as JSON Lines to get a valid NTS file of your decoder output (check it with `fidetype.validate(path)`).

## Step 5 (1 min): read the sheet

Check three lines of `print(guard.sheet)`:

1. `guarantee`: the bound that you asked for.
2. `null controls`: both `PASS`. If a control fails, `calibrate` raises `NullControlError` and gives no guard.
3. `commit threshold`: a number means the guard can commit. `never commits` means it cannot certify any commit with your data; it still offers and withholds.

What each line means, and what is not guaranteed: [guarantee sheet](trust-guarantee.md).

## If something goes wrong

| Message or result | Cause | What to do |
|---|---|---|
| `NullControlError ... shuffled` with the built-in decoder | No language model and no lexicon: shuffled frames keep their confidence, so the decoder writes confident nonsense | Pass `lexicon=` or your own `decode_fn` with a language model |
| `NullControlError ... uniform` | The decoder (or `decode_fn`) gives confident text on no-signal input | Check that the inputs are per-frame scores; check the scores of your n-best; fix the decoder's confidence |
| `NullControlError` on very short utterances (one or two letters) | A shuffle of a two-letter word can give a real word ("no" -> "on") | Calibrate on utterances of the real length; or accept a small `null_max_commit_rate` and say so |
| `ValueError: n-best input needs null_inputs=` | Fidetype does not run your decoder, so it cannot make a shuffled control for text | Run your decoder on time-shuffled or no-signal recordings; pass the n-best lists |
| Sheet says `never commits` | Too few LTT items, or the decoder is wrong too often for `alpha` | More labelled data; a larger `alpha` (state it); a better decoder |
| Few commits, many withholds | The guarantee is on the rate over all utterances, so a weak decoder commits rarely | Expected. The guard trades commits for safety |

## Reference

| Function or class | Signature (short) |
|---|---|
| `fidetype.trust.calibrate` | `calibrate(inputs, texts, *, alpha=0.05, delta=0.1, input_kind="auto", vocab=None, blank=0, word_delimiter=None, input_scale="auto", frame_period=0.02, decode_fn=None, lexicon=None, null_inputs=None, null_trials=300, null_max_commit_rate=None, decoder_name="my-decoder", decoder_version="0", modality="other", name="", seed=0, audit_text=True) -> TrustGuard` |
| `fidetype.trust.wrap` | `wrap(calibration_set, *, alpha=0.05, **kwargs) -> TrustGuard` (pairs of output and text) |
| `fidetype.trust.load` | `load(path, decode_fn=None, *, audit_text=True) -> TrustGuard` |
| `TrustGuard` | `.decide(x, *, utterance_id=None) -> TrustResult`, `__call__`, `.decide_many(xs)`, `.sheet`, `.audit_log`, `.write_audit(path)`, `.save(path)`, `.nts_events(x)`, `.config_id`, `.input_kind` |
| `NullControlError` | `.report`: list of `ControlResult(name, description, n, n_commit, allowed, passed)` |

Full docstrings: `help(fidetype.trust.calibrate)`. Source: [`src/fidetype/trust/dropin.py`](../src/fidetype/trust/dropin.py). Tests: [`tests/test_trust_dropin.py`](../tests/test_trust_dropin.py).

**Limits.** Fidetype is research software, not a medical device. The guarantee holds only under the assumptions on the [guarantee sheet](trust-guarantee.md).
