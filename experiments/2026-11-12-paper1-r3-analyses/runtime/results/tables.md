# Trust-layer run time per decision (CPU, single thread)

Hardware: AMD Ryzen 7 9800X3D 8-Core Processor, 16 logical cores, 31.2 GB RAM; Windows-11-10.0.26200-SP0; Python 3.12.16, NumPy 2.5.4. One thread. GPU training job (MEG seed queue) and other CPU analyses ran at the same time: upper bounds for an idle machine.

| device | items x passes | frame T median / p95 (ms) | analyze median / p95 | decide median / p95 | trust layer total median / p95 | decoder (uncached) median / p95 |
|---|---|---|---|---|---|---|
| emg-calib | 551 x 3 | 0.078 / 0.104 | 0.099 / 0.877 | 0.0024 / 0.0039 | **0.188 / 0.987** | 66.9 / 127.0 (n 10) |
| emg-xsession | 551 x 3 | 0.076 / 0.102 | 0.099 / 0.869 | 0.0022 / 0.0035 | **0.182 / 0.961** | 72.0 / 150.9 (n 10) |
| emg-xsubject | 551 x 3 | 0.075 / 0.099 | 0.102 / 0.806 | 0.0022 / 0.0035 | **0.185 / 0.890** | 44.9 / 133.4 (n 10) |
| meg-async | 637 x 3 | 0.122 / 0.179 | 0.106 / 0.901 | 0.0022 / 0.0038 | **0.240 / 1.061** | 184.7 / 238.5 (n 10) |
| b2t-ours | 816 x 3 | 0.160 / 0.266 | 0.108 / 0.833 | 0.0025 / 0.0040 | **0.304 / 1.040** | 232.3 / 869.5 (n 10) |
| b2t-published | 816 x 3 | 0.163 / 0.264 | 0.111 / 0.277 | 0.0026 / 0.0038 | **0.283 / 0.491** | — (shares our decoder) |