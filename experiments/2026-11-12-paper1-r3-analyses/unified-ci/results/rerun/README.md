# Re-run results: file names

The two multi-condition result files had very long names. Their paths were over 160 characters and broke `git clone` on Windows. On 2026-11-16 we renamed them. The content did not change.

| New name | Old name (dataset list, in run order) |
|---|---|
| `ablation/results/ablation-all6.json` | `ablation-emg-calib+emg-xsession+emg-xsubject+meg-async+b2t-ours+b2t-published.json` |
| `user-model/results/user-model-all6.json` | `user-model-emg-calib+emg-xsession+emg-xsubject+b2t-ours+b2t-published+meg-async.json` |

"all6" means all 6 default conditions: emg-calib, emg-xsession, emg-xsubject, meg-async, b2t-ours, b2t-published.

The round-1 scripts (`experiments/2026-11-12-paper1-r1-analyses/{ablation,user-model}/run.py`) now write `<module>-all6.json` for the default condition set. For other sets they write the joined condition names, or `<module>-n<count>-<hash>.json` if that name is longer than 40 characters.
