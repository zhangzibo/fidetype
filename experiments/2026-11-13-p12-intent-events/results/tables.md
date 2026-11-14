# P12-02 intent evaluation: tables

alpha: safe 0.1, undoable 0.05, irreversible 0.01 (per decision unit); LTT delta 0.1 (Bonferroni over 3 classes). Rates are means over (group, split) test sets; 'exceed' = share of test sets above alpha; irreversible wrong = wrong armed intents (execution needs a confirmation too).

| setting | input | act rate | commit / armed / offer / abstain | commit precision | truth in offer | wrong safe (exceed) | wrong undoable (exceed) | wrong irreversible (exceed, max) |
|---|---|---|---|---|---|---|---|---|
| synthetic/ltt/no-gate | clean | 0.690 | 0.62 / 0.07 / 0.16 / 0.15 | 0.874 | 0.766 | 0.0477 (0.00) | 0.0307 (0.03) | 0.0018 (0.02, 0.024) |
| synthetic/ltt/no-gate | nosignal-trials | 0.405 | 0.40 / 0.01 / 0.31 / 0.29 | 0.000 | 0.000 | 0.2340 (0.99) | 0.1612 (0.99) | 0.0102 (0.38, 0.116) |
| synthetic/ltt/no-gate | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/ltt/no-gate | pairshuffled | 0.690 | 0.62 / 0.07 / 0.16 / 0.15 | 0.074 | 0.173 | 0.2777 (1.00) | 0.2984 (1.00) | 0.0626 (0.81, 0.138) |
| synthetic/ltt/quality-gate | clean | 0.650 | 0.58 / 0.07 / 0.13 / 0.22 | 0.933 | 0.950 | 0.0244 (0.00) | 0.0147 (0.00) | 0.0008 (0.01, 0.011) |
| synthetic/ltt/quality-gate | nosignal-trials | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/ltt/quality-gate | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/ltt/quality-gate | pairshuffled | 0.622 | 0.56 / 0.06 / 0.14 / 0.24 | 0.082 | 0.192 | 0.2482 (1.00) | 0.2664 (1.00) | 0.0559 (0.81, 0.119) |
| synthetic/crc/no-gate | clean | 0.775 | 0.66 / 0.12 / 0.08 / 0.14 | 0.855 | 0.699 | 0.0478 (0.00) | 0.0476 (0.39) | 0.0097 (0.39, 0.031) |
| synthetic/crc/no-gate | nosignal-trials | 0.526 | 0.47 / 0.05 / 0.21 / 0.27 | 0.000 | 0.000 | 0.2341 (0.99) | 0.2403 (1.00) | 0.0514 (0.94, 0.163) |
| synthetic/crc/no-gate | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/crc/no-gate | pairshuffled | 0.775 | 0.66 / 0.12 / 0.08 / 0.14 | 0.074 | 0.214 | 0.2777 (1.00) | 0.3293 (1.00) | 0.1107 (1.00, 0.150) |
| synthetic/crc/quality-gate | clean | 0.723 | 0.61 / 0.11 / 0.06 / 0.22 | 0.921 | 0.942 | 0.0244 (0.00) | 0.0237 (0.00) | 0.0046 (0.04, 0.018) |
| synthetic/crc/quality-gate | nosignal-trials | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/crc/quality-gate | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| synthetic/crc/quality-gate | pairshuffled | 0.699 | 0.59 / 0.11 / 0.07 / 0.23 | 0.082 | 0.240 | 0.2483 (1.00) | 0.2940 (1.00) | 0.0988 (1.00, 0.135) |
| toronto/calib/ltt | clean | 0.082 | 0.08 / 0.00 / 0.10 / 0.81 | 0.733 | 0.904 | 0.0002 (0.00) | 0.0218 (0.03) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt | zero | 0.371 | 0.37 / 0.00 / 0.00 / 0.63 | 0.026 | 0.111 | 0.0000 (0.00) | 0.3612 (0.75) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt | pairshuffled | 0.082 | 0.08 / 0.00 / 0.10 / 0.81 | 0.075 | 0.116 | 0.0079 (0.00) | 0.0681 (0.68) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt | timeshuffled | 0.017 | 0.02 / 0.00 / 0.04 / 0.94 | 0.230 | 0.428 | 0.0000 (0.00) | 0.0128 (0.04) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc | clean | 0.114 | 0.11 / 0.01 / 0.08 / 0.80 | 0.676 | 0.913 | 0.0002 (0.00) | 0.0347 (0.21) | 0.0029 (0.08, 0.031) |
| toronto/calib/crc | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc | zero | 0.446 | 0.45 / 0.00 / 0.00 / 0.55 | 0.026 | - | 0.0000 (0.00) | 0.4340 (0.90) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc | pairshuffled | 0.114 | 0.11 / 0.01 / 0.08 / 0.80 | 0.064 | 0.121 | 0.0079 (0.00) | 0.0928 (0.78) | 0.0067 (0.29, 0.054) |
| toronto/calib/crc | timeshuffled | 0.033 | 0.02 / 0.01 / 0.03 / 0.94 | 0.215 | 0.447 | 0.0000 (0.00) | 0.0191 (0.10) | 0.0078 (0.18, 0.132) |
| toronto/calib/ltt-nofloor | clean | 0.132 | 0.13 / 0.00 / 0.10 / 0.77 | 0.767 | 0.903 | 0.0057 (0.00) | 0.0253 (0.04) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt-nosignalref | clean | 0.057 | 0.06 / 0.00 / 0.12 / 0.82 | 0.796 | 0.905 | 0.0002 (0.00) | 0.0115 (0.01) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.12 / 0.88 | - | 0.080 | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt-nosignalref | pairshuffled | 0.057 | 0.06 / 0.00 / 0.12 / 0.82 | 0.096 | 0.115 | 0.0080 (0.00) | 0.0432 (0.34) | 0.0000 (0.00, 0.000) |
| toronto/calib/ltt-nosignalref | timeshuffled | 0.006 | 0.01 / 0.00 / 0.04 / 0.95 | 0.291 | 0.430 | 0.0000 (0.00) | 0.0044 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc-nosignalref | clean | 0.067 | 0.06 / 0.01 / 0.12 / 0.82 | 0.776 | 0.912 | 0.0002 (0.00) | 0.0134 (0.02) | 0.0029 (0.08, 0.031) |
| toronto/calib/crc-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.12 / 0.88 | - | 0.080 | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/calib/crc-nosignalref | pairshuffled | 0.067 | 0.06 / 0.01 / 0.12 / 0.82 | 0.090 | 0.117 | 0.0080 (0.00) | 0.0471 (0.36) | 0.0068 (0.29, 0.061) |
| toronto/calib/crc-nosignalref | timeshuffled | 0.016 | 0.01 / 0.01 / 0.04 / 0.94 | 0.304 | 0.446 | 0.0000 (0.00) | 0.0049 (0.00) | 0.0078 (0.18, 0.132) |
| toronto/xsession/ltt | clean | 0.022 | 0.02 / 0.00 / 0.01 / 0.97 | 0.675 | 0.854 | 0.0000 (0.00) | 0.0073 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt | zero | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt | pairshuffled | 0.022 | 0.02 / 0.00 / 0.01 / 0.97 | 0.027 | 0.095 | 0.0000 (0.00) | 0.0218 (0.10) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc | clean | 0.024 | 0.02 / 0.00 / 0.01 / 0.96 | 0.664 | 0.892 | 0.0000 (0.00) | 0.0078 (0.00) | 0.0008 (0.02, 0.023) |
| toronto/xsession/crc | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc | zero | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc | pairshuffled | 0.024 | 0.02 / 0.00 / 0.01 / 0.96 | 0.027 | 0.096 | 0.0000 (0.00) | 0.0227 (0.12) | 0.0009 (0.03, 0.023) |
| toronto/xsession/ltt-nofloor | clean | 0.055 | 0.05 / 0.00 / 0.01 / 0.94 | 0.551 | 0.839 | 0.0012 (0.00) | 0.0235 (0.03) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt-nosignalref | clean | 0.022 | 0.02 / 0.00 / 0.01 / 0.97 | 0.675 | 0.854 | 0.0000 (0.00) | 0.0073 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/ltt-nosignalref | pairshuffled | 0.022 | 0.02 / 0.00 / 0.01 / 0.97 | 0.025 | 0.098 | 0.0000 (0.00) | 0.0218 (0.10) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc-nosignalref | clean | 0.024 | 0.02 / 0.00 / 0.01 / 0.96 | 0.664 | 0.892 | 0.0000 (0.00) | 0.0078 (0.00) | 0.0008 (0.02, 0.023) |
| toronto/xsession/crc-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsession/crc-nosignalref | pairshuffled | 0.024 | 0.02 / 0.00 / 0.01 / 0.96 | 0.028 | 0.095 | 0.0000 (0.00) | 0.0227 (0.12) | 0.0009 (0.02, 0.023) |
| toronto/xsubject/ltt | clean | 0.040 | 0.04 / 0.00 / 0.05 / 0.91 | 0.658 | 0.903 | 0.0007 (0.00) | 0.0131 (0.01) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt | zero | 0.000 | 0.00 / 0.00 / 0.04 / 0.96 | - | 0.092 | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt | pairshuffled | 0.040 | 0.04 / 0.00 / 0.05 / 0.91 | 0.091 | 0.110 | 0.0058 (0.01) | 0.0309 (0.25) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc | clean | 0.054 | 0.05 / 0.00 / 0.04 / 0.91 | 0.605 | 0.910 | 0.0007 (0.00) | 0.0195 (0.09) | 0.0014 (0.04, 0.031) |
| toronto/xsubject/crc | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc | zero | 0.004 | 0.00 / 0.00 / 0.04 / 0.96 | 0.024 | 0.092 | 0.0000 (0.00) | 0.0036 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc | pairshuffled | 0.054 | 0.05 / 0.00 / 0.04 / 0.91 | 0.081 | 0.110 | 0.0057 (0.01) | 0.0414 (0.39) | 0.0030 (0.09, 0.062) |
| toronto/xsubject/ltt-nofloor | clean | 0.125 | 0.13 / 0.00 / 0.05 / 0.83 | 0.646 | 0.903 | 0.0193 (0.00) | 0.0252 (0.04) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt-nosignalref | clean | 0.040 | 0.04 / 0.00 / 0.05 / 0.91 | 0.658 | 0.903 | 0.0007 (0.00) | 0.0131 (0.01) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.04 / 0.96 | - | 0.092 | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/ltt-nosignalref | pairshuffled | 0.040 | 0.04 / 0.00 / 0.05 / 0.91 | 0.094 | 0.107 | 0.0057 (0.01) | 0.0309 (0.25) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc-nosignalref | clean | 0.054 | 0.05 / 0.00 / 0.04 / 0.91 | 0.605 | 0.910 | 0.0007 (0.00) | 0.0195 (0.09) | 0.0014 (0.04, 0.031) |
| toronto/xsubject/crc-nosignalref | uniform | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc-nosignalref | zero | 0.000 | 0.00 / 0.00 / 0.04 / 0.96 | - | 0.092 | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/xsubject/crc-nosignalref | pairshuffled | 0.054 | 0.05 / 0.00 / 0.04 / 0.91 | 0.080 | 0.108 | 0.0057 (0.01) | 0.0414 (0.38) | 0.0029 (0.10, 0.062) |
| toronto/permuted-decoder/ltt | clean | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/permuted-decoder/crc | clean | 0.000 | 0.00 / 0.00 / 0.00 / 1.00 | - | - | 0.0000 (0.00) | 0.0000 (0.00) | 0.0000 (0.00, 0.000) |
| toronto/permuted-decoder/ltt-nofloor | clean | 0.002 | 0.00 / 0.00 / 0.00 / 1.00 | 0.000 | - | 0.0000 (0.00) | 0.0021 (0.00) | 0.0000 (0.00, 0.000) |

Median fitted thresholds (share of fits with 'never commit'):

| setting | safe | undoable | irreversible |
|---|---|---|---|
| synthetic/ltt/no-gate | 0.00 (0.00) | 0.71 (0.00) | 0.97 (0.00) |
| synthetic/ltt/quality-gate | 0.00 (0.00) | 0.71 (0.00) | 0.97 (0.00) |
| synthetic/crc/no-gate | 0.28 (0.00) | 0.57 (0.00) | 0.79 (0.00) |
| synthetic/crc/quality-gate | 0.28 (0.00) | 0.57 (0.00) | 0.79 (0.00) |
| toronto/calib/ltt | 0.00 (0.00) | 0.57 (0.00) | - (1.00) |
| toronto/calib/crc | 0.16 (0.01) | 0.50 (0.00) | 0.50 (0.00) |
| toronto/calib/ltt-nofloor | 0.00 (0.00) | 0.57 (0.00) | - (1.00) |
| toronto/calib/ltt-nosignalref | 0.00 (0.00) | 0.62 (0.00) | - (1.00) |
| toronto/calib/crc-nosignalref | 0.16 (0.01) | 0.61 (0.00) | 0.50 (0.00) |
| toronto/xsession/ltt | 0.00 (0.00) | 0.36 (0.00) | - (1.00) |
| toronto/xsession/crc | 0.20 (0.49) | 0.32 (0.00) | 0.29 (0.00) |
| toronto/xsession/ltt-nofloor | 0.00 (0.00) | 0.36 (0.00) | - (1.00) |
| toronto/xsession/ltt-nosignalref | 0.00 (0.00) | 0.36 (0.00) | - (1.00) |
| toronto/xsession/crc-nosignalref | 0.20 (0.49) | 0.32 (0.00) | 0.29 (0.00) |
| toronto/xsubject/ltt | 0.00 (0.00) | 0.45 (0.00) | - (1.00) |
| toronto/xsubject/crc | 0.11 (0.01) | 0.39 (0.00) | 0.39 (0.00) |
| toronto/xsubject/ltt-nofloor | 0.00 (0.00) | 0.45 (0.00) | - (1.00) |
| toronto/xsubject/ltt-nosignalref | 0.00 (0.00) | 0.45 (0.00) | - (1.00) |
| toronto/xsubject/crc-nosignalref | 0.11 (0.01) | 0.39 (0.00) | 0.39 (0.00) |
| toronto/permuted-decoder/ltt | 0.00 (0.00) | 0.04 (0.00) | - (1.00) |
| toronto/permuted-decoder/crc | - (1.00) | 0.04 (0.00) | - (0.89) |
| toronto/permuted-decoder/ltt-nofloor | 0.00 (0.00) | 0.04 (0.00) | - (1.00) |
