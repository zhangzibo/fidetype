# B2T word decoder re-tuned on fit-A only

Paper choice (tuned on a random 400 of the 812 fit trials): {'lm_weight': 1.0, 'edit_penalty': 12.0, 'word_bonus': 3.0}.

| split | n fit-A | fit-A choice | same as paper | rank of the paper point on fit-A (of 12) | WER best / paper point | clean cal trials also in the paper tuning set |
|---|---|---|---|---|---|---|
| split A | 411 | lm 1.0, edit 12.0, bonus 3.0 | True | 1 | 0.1571 / 0.1571 | 187 of 401 |
| split B | 411 | lm 1.0, edit 12.0, bonus 3.0 | True | 1 | 0.1615 / 0.1615 | 189 of 401 |