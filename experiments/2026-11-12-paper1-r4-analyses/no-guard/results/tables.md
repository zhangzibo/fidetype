# No-guard configuration (plain threshold): tables

Guard off unless marked. 95 % unified bootstrap CIs (seed 20261112, B 2000), conditional on the fitted pipeline and threshold. Zero counts: one-sided 95 % CP upper bound.

## Table 1 rows (fixed test sets)

| condition | row | rule | eWPM [CI] | wrong-commit [CI] | commit | EAC (wrong/commits) | λ |
|---|---|---|---|---|---|---|---|
| b2t-ours | full_fit | plug-in | 11.51 [10.79, 12.35] | 0.0355 [0.025, 0.046] | 0.165 | 29/135 | 0.60 |
| b2t-ours | split A | plug-in | 11.55 [10.83, 12.39] | 0.0404 [0.030, 0.051] | 0.183 | 33/149 | 0.60 |
| b2t-ours | split A | CRC max | 11.55 [10.83, 12.39] | 0.0404 [0.030, 0.051] | 0.183 | 33/149 | 0.60 |
| b2t-ours | split A | LTT max | 11.55 [10.83, 12.39] | 0.0404 [0.030, 0.051] | 0.183 | 33/149 | 0.60 |
| b2t-ours | split A | joint LTT b0.10 | 11.42 [10.73, 12.24] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-ours | split B | plug-in | 11.56 [10.84, 12.40] | 0.0343 [0.023, 0.046] | 0.168 | 28/137 | 0.60 |
| b2t-ours | split B | CRC max | 11.56 [10.84, 12.40] | 0.0343 [0.023, 0.046] | 0.168 | 28/137 | 0.60 |
| b2t-ours | split B | LTT max | 11.53 [10.82, 12.37] | 0.0294 [0.021, 0.038] | 0.147 | 24/120 | 0.62 |
| b2t-ours | split B | joint LTT b0.10 | 11.41 [10.73, 12.22] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-ours | split A (guard on, committed items) | plug-in | 11.48 [10.79, 12.29] | 0.0245 [0.015, 0.035] | 0.100 | 20/82 | 0.30 |
| b2t-ours | split A (guard on, committed items) | CRC max | 11.48 [10.79, 12.29] | 0.0245 [0.015, 0.035] | 0.100 | 20/82 | 0.31 |
| b2t-ours | split A (guard on, committed items) | LTT max | 11.48 [10.79, 12.29] | 0.0245 [0.015, 0.035] | 0.100 | 20/82 | 0.30 |
| b2t-ours | split A (guard on, committed items) | joint LTT b0.10 | 11.42 [10.73, 12.24] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-ours | split B (guard on, committed items) | plug-in | 11.55 [10.85, 12.36] | 0.0600 [0.049, 0.071] | 0.217 | 49/177 | 0.40 |
| b2t-ours | split B (guard on, committed items) | CRC max | 11.54 [10.84, 12.35] | 0.0600 [0.049, 0.071] | 0.212 | 49/173 | 0.41 |
| b2t-ours | split B (guard on, committed items) | LTT max | 11.54 [10.83, 12.34] | 0.0515 [0.043, 0.059] | 0.192 | 42/157 | 0.43 |
| b2t-ours | split B (guard on, committed items) | joint LTT b0.10 | 11.41 [10.73, 12.22] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-published | full_fit | plug-in | 18.62 [17.01, 20.17] | 0.0245 [0.014, 0.038] | 0.381 | 20/311 | 0.80 |
| b2t-published | split A | plug-in | 18.63 [17.03, 20.18] | 0.0270 [0.016, 0.040] | 0.391 | 22/319 | 0.80 |
| b2t-published | split A | CRC max | 18.63 [17.03, 20.18] | 0.0270 [0.016, 0.040] | 0.391 | 22/319 | 0.80 |
| b2t-published | split A | LTT max | 18.63 [17.03, 20.18] | 0.0270 [0.016, 0.040] | 0.391 | 22/319 | 0.80 |
| b2t-published | split A | joint LTT b0.10 | 18.11 [16.59, 19.57] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-published | split B | plug-in | 18.63 [17.02, 20.18] | 0.0245 [0.014, 0.038] | 0.387 | 20/316 | 0.80 |
| b2t-published | split B | CRC max | 18.63 [17.02, 20.18] | 0.0245 [0.014, 0.038] | 0.387 | 20/316 | 0.80 |
| b2t-published | split B | LTT max | 18.63 [17.02, 20.18] | 0.0245 [0.014, 0.038] | 0.387 | 20/316 | 0.80 |
| b2t-published | split B | joint LTT b0.10 | 18.11 [16.59, 19.57] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-published | split A (guard on, committed items) | plug-in | 18.79 [17.13, 20.37] | 0.0478 [0.029, 0.071] | 0.491 | 39/401 | 0.70 |
| b2t-published | split A (guard on, committed items) | CRC max | 18.79 [17.13, 20.37] | 0.0478 [0.029, 0.071] | 0.491 | 39/401 | 0.70 |
| b2t-published | split A (guard on, committed items) | LTT max | 18.65 [17.04, 20.20] | 0.0294 [0.013, 0.050] | 0.403 | 24/329 | 0.76 |
| b2t-published | split A (guard on, committed items) | joint LTT b0.10 | 18.11 [16.59, 19.57] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| b2t-published | split B (guard on, committed items) | plug-in | 18.78 [17.13, 20.36] | 0.0478 [0.029, 0.071] | 0.485 | 39/396 | 0.70 |
| b2t-published | split B (guard on, committed items) | CRC max | 18.78 [17.13, 20.36] | 0.0478 [0.029, 0.071] | 0.485 | 39/396 | 0.70 |
| b2t-published | split B (guard on, committed items) | LTT max | 18.68 [17.06, 20.23] | 0.0306 [0.014, 0.052] | 0.415 | 25/339 | 0.75 |
| b2t-published | split B (guard on, committed items) | joint LTT b0.10 | 18.11 [16.59, 19.57] | 0 (≤ 0.0037) | 0.000 | 0/0 | — |
| emg-calib | full_fit | plug-in | 8.02 [6.93, 9.19] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed | plug-in | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed | CRC max | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed | LTT max | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed | joint LTT b0.10 | 7.96 [6.94, 9.08] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-calib | fit-A guaranteed (guard on, committed items) | plug-in | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed (guard on, committed items) | CRC max | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed (guard on, committed items) | LTT max | 7.98 [6.95, 9.11] | 0.0036 [0.000, 0.009] | 0.038 | 2/21 | 0.70 |
| emg-calib | fit-A guaranteed (guard on, committed items) | joint LTT b0.10 | 7.96 [6.94, 9.08] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-xsession | full_fit | plug-in | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed | plug-in | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed | CRC max | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed | LTT max | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed | joint LTT b0.10 | 4.67 [4.19, 5.25] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-xsession | fit-A guaranteed (guard on, committed items) | plug-in | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed (guard on, committed items) | CRC max | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed (guard on, committed items) | LTT max | 4.68 [4.19, 5.25] | 0.0036 [0.000, 0.009] | 0.018 | 2/10 | 0.30 |
| emg-xsession | fit-A guaranteed (guard on, committed items) | joint LTT b0.10 | 4.67 [4.19, 5.25] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-xsubject | full_fit | plug-in | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed | plug-in | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed | CRC max | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed | LTT max | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed | joint LTT b0.10 | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-xsubject | fit-A guaranteed (guard on, committed items) | plug-in | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed (guard on, committed items) | CRC max | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| emg-xsubject | fit-A guaranteed (guard on, committed items) | LTT max | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | 0.30 |
| emg-xsubject | fit-A guaranteed (guard on, committed items) | joint LTT b0.10 | 4.08 [3.82, 4.37] | 0 (≤ 0.0054) | 0.000 | 0/0 | — |
| meg-async | full_fit | plug-in | 3.20 [3.01, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (instance level) | plug-in | 3.21 [3.02, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (instance level) | CRC max | 3.21 [3.02, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (instance level) | LTT max | 3.21 [3.02, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (instance level) | joint LTT b0.10 | 3.21 [3.02, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | — |
| meg-async | clean split (guard on, R3 items) | plug-in | 3.20 [3.01, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (guard on, R3 items) | CRC max | 3.20 [3.01, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (guard on, R3 items) | LTT max | 3.20 [3.01, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | 0.50 |
| meg-async | clean split (guard on, R3 items) | joint LTT b0.10 | 3.20 [3.01, 3.44] | 0 (≤ 0.0047) | 0.000 | 0/0 | — |

## Controls (commits / n; one-sided 95 % CP upper bound of the commit rate)

| condition | policy | control: commits/n (bound) |
|---|---|---|
| b2t-ours | plain threshold (full fit) | real: 38/300 (≤ 0.1627) wrong 0.027; other_trial: 38/300 (≤ 0.1627) wrong 0.127; frame_shuffled: 2/300 (≤ 0.0208) wrong 0.007; uniform: 203/300 (≤ 0.7213) wrong 0.677 |
| b2t-ours | split A plug-in | real: 43/300 (≤ 0.1809) wrong 0.037; other_trial: 43/300 (≤ 0.1809) wrong 0.143; frame_shuffled: 3/300 (≤ 0.0256) wrong 0.010; uniform: 198/300 (≤ 0.7053) wrong 0.660 |
| b2t-ours | split A LTT max | real: 43/300 (≤ 0.1809) wrong 0.037; other_trial: 43/300 (≤ 0.1809) wrong 0.143; frame_shuffled: 3/300 (≤ 0.0256) wrong 0.010; uniform: 198/300 (≤ 0.7053) wrong 0.660 |
| b2t-ours | split A CRC max | real: 43/300 (≤ 0.1809) wrong 0.037; other_trial: 43/300 (≤ 0.1809) wrong 0.143; frame_shuffled: 3/300 (≤ 0.0256) wrong 0.010; uniform: 198/300 (≤ 0.7053) wrong 0.660 |
| b2t-ours | split A joint LTT b0.10 | real: 0/300 (≤ 0.0099) wrong 0.000; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-ours | split A joint LTT b0.20 | real: 0/300 (≤ 0.0099) wrong 0.000; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | plain threshold (full fit) | real: 106/300 (≤ 0.4013) wrong 0.030; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | split A plug-in | real: 110/300 (≤ 0.4149) wrong 0.030; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | split A LTT max | real: 110/300 (≤ 0.4149) wrong 0.030; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | split A CRC max | real: 110/300 (≤ 0.4149) wrong 0.030; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | split A joint LTT b0.10 | real: 0/300 (≤ 0.0099) wrong 0.000; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| b2t-published | split A joint LTT b0.20 | real: 99/300 (≤ 0.3774) wrong 0.030; other_trial: 0/300 (≤ 0.0099) wrong 0.000; frame_shuffled: 0/300 (≤ 0.0099) wrong 0.000; uniform: 0/300 (≤ 0.0099) wrong 0.000 |
| emg-calib | plain threshold (full fit) | real: 8/200 (≤ 0.0710) wrong 0.005; other_sentence: 8/200 (≤ 0.0710) wrong 0.040; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-calib | fit-A plug-in | real: 8/200 (≤ 0.0710) wrong 0.005; other_sentence: 8/200 (≤ 0.0710) wrong 0.040; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-calib | fit-A LTT max | real: 8/200 (≤ 0.0710) wrong 0.005; other_sentence: 8/200 (≤ 0.0710) wrong 0.040; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-calib | fit-A joint LTT b0.10 | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsession | plain threshold (full fit) | real: 5/200 (≤ 0.0518) wrong 0.005; other_sentence: 5/200 (≤ 0.0518) wrong 0.025; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsession | fit-A plug-in | real: 5/200 (≤ 0.0518) wrong 0.005; other_sentence: 5/200 (≤ 0.0518) wrong 0.025; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsession | fit-A LTT max | real: 5/200 (≤ 0.0518) wrong 0.005; other_sentence: 5/200 (≤ 0.0518) wrong 0.025; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsession | fit-A joint LTT b0.10 | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsubject | plain threshold (full fit) | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsubject | fit-A plug-in | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsubject | fit-A LTT max | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| emg-xsubject | fit-A joint LTT b0.10 | real: 0/200 (≤ 0.0149) wrong 0.000; other_sentence: 0/200 (≤ 0.0149) wrong 0.000; frame_shuffled: 0/200 (≤ 0.0149) wrong 0.000; zeros_input: 0/200 (≤ 0.0149) wrong 0.000; permuted_label_decoder: 0/200 (≤ 0.0149) wrong 0.000 |
| meg-async | plain threshold (full fit) | real: 0/637 (≤ 0.0047) wrong 0.000; shuffled_meg: 0/637 (≤ 0.0047) wrong 0.000; zeros_meg: 0/637 (≤ 0.0047) wrong 0.000; other_sentence: 0/637 (≤ 0.0047) wrong 0.000; frame_shuffled: 0/637 (≤ 0.0047) wrong 0.000; uniform: 0/637 (≤ 0.0047) wrong 0.000 |
| meg-async | clean-split plug-in | real: 0/637 (≤ 0.0047) wrong 0.000; shuffled_meg: 0/637 (≤ 0.0047) wrong 0.000; zeros_meg: 0/637 (≤ 0.0047) wrong 0.000; other_sentence: 0/637 (≤ 0.0047) wrong 0.000; frame_shuffled: 0/637 (≤ 0.0047) wrong 0.000; uniform: 0/637 (≤ 0.0047) wrong 0.000 |
| meg-async | clean-split LTT max | real: 0/637 (≤ 0.0047) wrong 0.000; shuffled_meg: 0/637 (≤ 0.0047) wrong 0.000; zeros_meg: 0/637 (≤ 0.0047) wrong 0.000; other_sentence: 0/637 (≤ 0.0047) wrong 0.000; frame_shuffled: 0/637 (≤ 0.0047) wrong 0.000; uniform: 0/637 (≤ 0.0047) wrong 0.000 |

## Table 2 rows (repeated splits; guard off vs on)

| condition / guard / R | rule | wrong-commit mean (p05–p95) | >α [CP95] | commit | EAC pooled | no-commit splits | eWPM |
|---|---|---|---|---|---|---|---|
| b2t-ours/no guard/R200 | plug-in | 0.0350 (0.017–0.059) | 0.10 [0.06, 0.14] | 0.158 | 0.222 | 0.00 | 11.10 |
| b2t-ours/no guard/R200 | CRC pure | 0.0476 (0.027–0.071) | 0.41 [0.34, 0.48] | 0.196 | 0.243 | 0.00 | 11.11 |
| b2t-ours/no guard/R200 | CRC max | 0.0329 (0.016–0.049) | 0.05 [0.02, 0.09] | 0.153 | 0.215 | 0.00 | 11.09 |
| b2t-ours/no guard/R200 | LTT pure | 0.0350 (0.017–0.054) | 0.08 [0.05, 0.13] | 0.160 | 0.219 | 0.00 | 11.10 |
| b2t-ours/no guard/R200 | LTT max | 0.0296 (0.015–0.045) | 0.00 [0.00, 0.02] | 0.141 | 0.209 | 0.00 | 11.09 |
| b2t-ours/no guard/R200 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.02] | 0.000 | — | 1.00 | 10.98 |
| b2t-ours/no guard/R200 | joint LTT b0.20 | 0.0004 (0.000–0.000) | 0.00 [0.00, 0.02] | 0.002 | 0.236 | 0.98 | 10.98 |
| b2t-ours/no guard/R50 | plug-in | 0.0376 (0.026–0.056) | 0.10 [0.03, 0.22] | 0.165 | 0.228 | 0.00 | 11.07 |
| b2t-ours/no guard/R50 | CRC pure | 0.0466 (0.026–0.071) | 0.40 [0.26, 0.55] | 0.192 | 0.242 | 0.00 | 11.08 |
| b2t-ours/no guard/R50 | CRC max | 0.0341 (0.021–0.046) | 0.04 [0.00, 0.14] | 0.156 | 0.218 | 0.00 | 11.06 |
| b2t-ours/no guard/R50 | LTT pure | 0.0354 (0.015–0.054) | 0.12 [0.05, 0.24] | 0.159 | 0.223 | 0.00 | 11.06 |
| b2t-ours/no guard/R50 | LTT max | 0.0305 (0.013–0.043) | 0.00 [0.00, 0.07] | 0.143 | 0.213 | 0.00 | 11.05 |
| b2t-ours/no guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 10.95 |
| b2t-ours/no guard/R50 | joint LTT b0.20 | 0.0002 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.001 | 0.194 | 0.98 | 10.95 |
| b2t-ours/guard/R200 | plug-in | 0.0417 (0.019–0.070) | 0.30 [0.24, 0.37] | 0.178 | 0.234 | 0.00 | 11.11 |
| b2t-ours/guard/R200 | CRC pure | 0.0486 (0.027–0.073) | 0.44 [0.37, 0.51] | 0.199 | 0.245 | 0.00 | 11.12 |
| b2t-ours/guard/R200 | CRC max | 0.0377 (0.018–0.062) | 0.18 [0.13, 0.25] | 0.168 | 0.225 | 0.00 | 11.11 |
| b2t-ours/guard/R200 | LTT pure | 0.0359 (0.018–0.056) | 0.14 [0.10, 0.20] | 0.162 | 0.221 | 0.00 | 11.10 |
| b2t-ours/guard/R200 | LTT max | 0.0321 (0.016–0.051) | 0.07 [0.04, 0.12] | 0.152 | 0.212 | 0.00 | 11.10 |
| b2t-ours/guard/R200 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.02] | 0.000 | — | 1.00 | 10.99 |
| b2t-ours/guard/R200 | joint LTT b0.20 | 0.0004 (0.000–0.000) | 0.00 [0.00, 0.02] | 0.002 | 0.216 | 0.98 | 10.99 |
| b2t-ours/guard/R50 | plug-in | 0.0440 (0.021–0.072) | 0.34 [0.21, 0.49] | 0.186 | 0.237 | 0.00 | 11.08 |
| b2t-ours/guard/R50 | CRC pure | 0.0456 (0.026–0.068) | 0.34 [0.21, 0.49] | 0.192 | 0.237 | 0.00 | 11.09 |
| b2t-ours/guard/R50 | CRC max | 0.0368 (0.021–0.059) | 0.14 [0.06, 0.27] | 0.166 | 0.221 | 0.00 | 11.08 |
| b2t-ours/guard/R50 | LTT pure | 0.0344 (0.017–0.056) | 0.16 [0.07, 0.29] | 0.158 | 0.217 | 0.00 | 11.07 |
| b2t-ours/guard/R50 | LTT max | 0.0304 (0.016–0.052) | 0.08 [0.02, 0.19] | 0.147 | 0.207 | 0.00 | 11.07 |
| b2t-ours/guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 10.95 |
| b2t-ours/guard/R50 | joint LTT b0.20 | 0.0002 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.001 | 0.290 | 0.98 | 10.95 |
| b2t-published/no guard/R200 | plug-in | 0.0251 (0.017–0.042) | 0.03 [0.01, 0.06] | 0.373 | 0.067 | 0.00 | 18.49 |
| b2t-published/no guard/R200 | CRC pure | 0.0485 (0.031–0.071) | 0.41 [0.35, 0.49] | 0.498 | 0.098 | 0.00 | 18.66 |
| b2t-published/no guard/R200 | CRC max | 0.0248 (0.017–0.038) | 0.03 [0.01, 0.06] | 0.372 | 0.067 | 0.00 | 18.49 |
| b2t-published/no guard/R200 | LTT pure | 0.0310 (0.018–0.051) | 0.09 [0.05, 0.14] | 0.410 | 0.076 | 0.00 | 18.54 |
| b2t-published/no guard/R200 | LTT max | 0.0239 (0.017–0.032) | 0.01 [0.00, 0.03] | 0.367 | 0.065 | 0.00 | 18.48 |
| b2t-published/no guard/R200 | joint LTT b0.10 | 0.0040 (0.000–0.027) | 0.00 [0.00, 0.02] | 0.059 | 0.068 | 0.81 | 18.08 |
| b2t-published/no guard/R200 | joint LTT b0.20 | 0.0205 (0.006–0.031) | 0.00 [0.00, 0.02] | 0.322 | 0.064 | 0.05 | 18.42 |
| b2t-published/no guard/R50 | plug-in | 0.0244 (0.018–0.031) | 0.00 [0.00, 0.07] | 0.363 | 0.067 | 0.00 | 18.45 |
| b2t-published/no guard/R50 | CRC pure | 0.0509 (0.034–0.073) | 0.48 [0.34, 0.63] | 0.503 | 0.101 | 0.00 | 18.64 |
| b2t-published/no guard/R50 | CRC max | 0.0244 (0.018–0.031) | 0.00 [0.00, 0.07] | 0.363 | 0.067 | 0.00 | 18.45 |
| b2t-published/no guard/R50 | LTT pure | 0.0343 (0.022–0.059) | 0.10 [0.03, 0.22] | 0.421 | 0.081 | 0.00 | 18.53 |
| b2t-published/no guard/R50 | LTT max | 0.0244 (0.018–0.031) | 0.00 [0.00, 0.07] | 0.363 | 0.067 | 0.00 | 18.45 |
| b2t-published/no guard/R50 | joint LTT b0.10 | 0.0040 (0.000–0.027) | 0.00 [0.00, 0.07] | 0.054 | 0.074 | 0.84 | 18.05 |
| b2t-published/no guard/R50 | joint LTT b0.20 | 0.0218 (0.010–0.029) | 0.00 [0.00, 0.07] | 0.332 | 0.066 | 0.02 | 18.41 |
| b2t-published/guard/R200 | plug-in | 0.0395 (0.020–0.064) | 0.27 [0.21, 0.33] | 0.437 | 0.090 | 0.00 | 18.57 |
| b2t-published/guard/R200 | CRC pure | 0.0496 (0.029–0.076) | 0.42 [0.36, 0.50] | 0.484 | 0.102 | 0.00 | 18.64 |
| b2t-published/guard/R200 | CRC max | 0.0364 (0.019–0.060) | 0.17 [0.13, 0.23] | 0.424 | 0.086 | 0.00 | 18.55 |
| b2t-published/guard/R200 | LTT pure | 0.0337 (0.017–0.055) | 0.12 [0.07, 0.17] | 0.411 | 0.082 | 0.00 | 18.54 |
| b2t-published/guard/R200 | LTT max | 0.0303 (0.017–0.050) | 0.06 [0.03, 0.10] | 0.394 | 0.077 | 0.00 | 18.51 |
| b2t-published/guard/R200 | joint LTT b0.10 | 0.0046 (0.000–0.026) | 0.00 [0.00, 0.02] | 0.072 | 0.065 | 0.76 | 18.09 |
| b2t-published/guard/R200 | joint LTT b0.20 | 0.0195 (0.009–0.033) | 0.00 [0.00, 0.02] | 0.319 | 0.061 | 0.03 | 18.41 |
| b2t-published/guard/R50 | plug-in | 0.0394 (0.021–0.060) | 0.22 [0.12, 0.36] | 0.433 | 0.091 | 0.00 | 18.54 |
| b2t-published/guard/R50 | CRC pure | 0.0489 (0.029–0.075) | 0.42 [0.28, 0.57] | 0.478 | 0.102 | 0.00 | 18.60 |
| b2t-published/guard/R50 | CRC max | 0.0357 (0.021–0.055) | 0.14 [0.06, 0.27] | 0.418 | 0.085 | 0.00 | 18.52 |
| b2t-published/guard/R50 | LTT pure | 0.0342 (0.021–0.051) | 0.06 [0.01, 0.17] | 0.410 | 0.083 | 0.00 | 18.51 |
| b2t-published/guard/R50 | LTT max | 0.0307 (0.020–0.047) | 0.02 [0.00, 0.11] | 0.392 | 0.078 | 0.00 | 18.49 |
| b2t-published/guard/R50 | joint LTT b0.10 | 0.0043 (0.000–0.023) | 0.00 [0.00, 0.07] | 0.072 | 0.059 | 0.76 | 18.07 |
| b2t-published/guard/R50 | joint LTT b0.20 | 0.0197 (0.012–0.033) | 0.00 [0.00, 0.07] | 0.318 | 0.062 | 0.02 | 18.39 |
| emg-calib/no guard/R50 | plug-in | 0.0146 (0.004–0.033) | 0.00 [0.00, 0.07] | 0.116 | 0.126 | 0.00 | 8.01 |
| emg-calib/no guard/R50 | CRC pure | 0.0290 (0.013–0.061) | 0.06 [0.01, 0.17] | 0.190 | 0.152 | 0.00 | 8.04 |
| emg-calib/no guard/R50 | CRC max | 0.0125 (0.004–0.024) | 0.00 [0.00, 0.07] | 0.105 | 0.119 | 0.00 | 8.01 |
| emg-calib/no guard/R50 | LTT pure | 0.0175 (0.009–0.034) | 0.00 [0.00, 0.07] | 0.139 | 0.126 | 0.00 | 8.02 |
| emg-calib/no guard/R50 | LTT max | 0.0106 (0.004–0.019) | 0.00 [0.00, 0.07] | 0.093 | 0.114 | 0.00 | 8.00 |
| emg-calib/no guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 7.97 |
| emg-calib/no guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 7.97 |
| emg-calib/guard/R50 | plug-in | 0.0146 (0.004–0.033) | 0.00 [0.00, 0.07] | 0.116 | 0.126 | 0.02 | 8.01 |
| emg-calib/guard/R50 | CRC pure | 0.0286 (0.011–0.061) | 0.06 [0.01, 0.17] | 0.187 | 0.153 | 0.02 | 8.04 |
| emg-calib/guard/R50 | CRC max | 0.0125 (0.004–0.024) | 0.00 [0.00, 0.07] | 0.105 | 0.119 | 0.02 | 8.01 |
| emg-calib/guard/R50 | LTT pure | 0.0173 (0.009–0.034) | 0.00 [0.00, 0.07] | 0.137 | 0.127 | 0.02 | 8.02 |
| emg-calib/guard/R50 | LTT max | 0.0106 (0.004–0.019) | 0.00 [0.00, 0.07] | 0.093 | 0.115 | 0.02 | 8.00 |
| emg-calib/guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 7.97 |
| emg-calib/guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 7.97 |
| emg-xsession/no guard/R50 | plug-in | 0.0082 (0.000–0.033) | 0.04 [0.00, 0.14] | 0.019 | 0.438 | 0.32 | 4.68 |
| emg-xsession/no guard/R50 | CRC pure | 0.0395 (0.007–0.065) | 0.24 [0.13, 0.38] | 0.069 | 0.576 | 0.00 | 4.67 |
| emg-xsession/no guard/R50 | CRC max | 0.0068 (0.000–0.027) | 0.00 [0.00, 0.07] | 0.017 | 0.412 | 0.32 | 4.68 |
| emg-xsession/no guard/R50 | LTT pure | 0.0248 (0.005–0.044) | 0.02 [0.00, 0.11] | 0.047 | 0.530 | 0.00 | 4.68 |
| emg-xsession/no guard/R50 | LTT max | 0.0058 (0.000–0.023) | 0.00 [0.00, 0.07] | 0.015 | 0.380 | 0.32 | 4.68 |
| emg-xsession/no guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.68 |
| emg-xsession/no guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.68 |
| emg-xsession/guard/R50 | plug-in | 0.0082 (0.000–0.033) | 0.04 [0.00, 0.14] | 0.019 | 0.440 | 0.34 | 4.68 |
| emg-xsession/guard/R50 | CRC pure | 0.0248 (0.000–0.063) | 0.14 [0.06, 0.27] | 0.043 | 0.575 | 0.34 | 4.67 |
| emg-xsession/guard/R50 | CRC max | 0.0068 (0.000–0.027) | 0.00 [0.00, 0.07] | 0.016 | 0.414 | 0.34 | 4.68 |
| emg-xsession/guard/R50 | LTT pure | 0.0169 (0.000–0.044) | 0.02 [0.00, 0.11] | 0.032 | 0.532 | 0.34 | 4.68 |
| emg-xsession/guard/R50 | LTT max | 0.0057 (0.000–0.023) | 0.00 [0.00, 0.07] | 0.015 | 0.382 | 0.34 | 4.68 |
| emg-xsession/guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.68 |
| emg-xsession/guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.68 |
| emg-xsubject/no guard/R50 | plug-in | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/no guard/R50 | CRC pure | 0.0419 (0.025–0.061) | 0.20 [0.10, 0.34] | 0.051 | 0.822 | 0.00 | 4.06 |
| emg-xsubject/no guard/R50 | CRC max | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/no guard/R50 | LTT pure | 0.0249 (0.005–0.033) | 0.00 [0.00, 0.07] | 0.034 | 0.744 | 0.00 | 4.07 |
| emg-xsubject/no guard/R50 | LTT max | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/no guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/no guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | plug-in | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | CRC pure | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | CRC max | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | LTT pure | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | LTT max | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | joint LTT b0.10 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
| emg-xsubject/guard/R50 | joint LTT b0.20 | 0.0000 (0.000–0.000) | 0.00 [0.00, 0.07] | 0.000 | — | 1.00 | 4.07 |
