| Run | Params | Epochs (best) | Min | Split | CER tgt real | shuffled | zeros | Gap shuf-real [95% CI] | CER typed real | WER tgt | Key acc real / shuf (conv, conformer) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r0-baseline | 10.65M | 45 (19) | 5 | val | 0.641 | 0.641 | 0.848 | +0.001 [-0.006, +0.007] | 0.642 | 1.030 | - |
| r0-baseline | 10.65M | 45 (19) | 5 | test | 0.670 | 0.669 | 0.851 | -0.001 [-0.006, +0.004] | 0.668 | 1.046 | - |
| r1-small | 3.54M | 71 (50) | 7 | val | 0.648 | 0.650 | 0.819 | +0.002 [-0.005, +0.009] | 0.653 | 1.248 | - |
| r1-small | 3.54M | 71 (50) | 7 | test | 0.684 | 0.681 | 0.833 | -0.002 [-0.008, +0.003] | 0.683 | 1.268 | - |
| r2-small-aux0.5 | 3.55M | 95 (74) | 11 | val | 0.601 | 0.737 | 0.905 | +0.136 [+0.116, +0.157] | 0.599 | 0.893 | 0.396/0.091, 0.430/0.101 |
| r2-small-aux0.5 | 3.55M | 95 (74) | 11 | test | 0.628 | 0.744 | 0.906 | +0.116 [+0.103, +0.130] | 0.625 | 0.921 | 0.378/0.099, 0.415/0.107 |
| r3-small-aux1.0 | 3.55M | 76 (55) | 7 | val | 0.619 | 0.747 | 0.877 | +0.128 [+0.110, +0.146] | 0.616 | 0.924 | 0.411/0.095, 0.436/0.106 |
| r3-small-aux1.0 | 3.55M | 76 (55) | 7 | test | 0.639 | 0.754 | 0.880 | +0.116 [+0.102, +0.129] | 0.635 | 0.926 | 0.389/0.092, 0.418/0.107 |
| r4-pretrain-keys | 3.55M | 49 (33) | 5 | val | 2.343 | 2.142 | 0.912 | -0.201 [-0.301, -0.108] | 2.439 | 1.000 | 0.417/0.101, 0.436/0.099 |
| r4-pretrain-keys | 3.55M | 49 (33) | 5 | test | 2.398 | 2.227 | 0.912 | -0.170 [-0.236, -0.105] | 2.411 | 1.000 | 0.392/0.101, 0.408/0.100 |
| r4-small-aux0.5-pretrained | 3.55M | 59 (38) | 5 | val | 0.605 | 0.776 | 1.000 | +0.171 [+0.150, +0.191] | 0.599 | 0.893 | 0.411/0.090, 0.439/0.101 |
| r4-small-aux0.5-pretrained | 3.55M | 59 (38) | 5 | test | 0.619 | 0.776 | 1.000 | +0.156 [+0.141, +0.172] | 0.618 | 0.915 | 0.377/0.097, 0.411/0.107 |

Mean over subjects (CER target / typed), keystroke head on true key times, status:

- m1c-r0-baseline: status early_stopped; val 0.640/0.641; test 0.669/0.666
- m1c-r1-small: status early_stopped; val 0.649/0.654; test 0.682/0.680
- m1c-r2-small-aux0.5: status early_stopped; val 0.614/0.611; val key acc conv 0.396, conformer 0.430 (majority 0.129, n 4855); test 0.635/0.632; test key acc conv 0.378, conformer 0.415 (majority 0.132, n 8423)
- m1c-r3-small-aux1.0: status early_stopped; val 0.631/0.624; val key acc conv 0.411, conformer 0.436 (majority 0.129, n 4855); test 0.648/0.644; test key acc conv 0.389, conformer 0.418 (majority 0.132, n 8423)
- m1c-r4-pretrain-keys: status early_stopped; val 2.274/2.421; val key acc conv 0.417, conformer 0.436 (majority 0.129, n 4855); test 2.355/2.371; test key acc conv 0.392, conformer 0.408 (majority 0.132, n 8423)
- m1c-r4-small-aux0.5-pretrained: status early_stopped; val 0.617/0.607; val key acc conv 0.411, conformer 0.439 (majority 0.129, n 4855); test 0.624/0.622; test key acc conv 0.377, conformer 0.411 (majority 0.132, n 8423)

Examples m1c-r0-baseline (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 0.52 | S3 | las funciones leen los archivos | las enas ea las ceos |
| 0.64 | S1 | los grupos del organismo exigen la liberacion | las en las ce las ea las eos |
| 0.67 | S1 | el cuaderno presenta las divisiones enteras | las enos e las e las e las eos |
| 0.70 | S9 | los productos cumplen la propiedad asociada | las enlas cea las ce las eos |

Examples m1c-r1-small (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 0.55 | S1 | las funciones leen los archivos | las enlas e e las os |
| 0.65 | S11 | las versiones del programa soportan el comando | las enas e las elas elas a a aos |
| 0.69 | S1 | los grupos del organismo exigen la liberacion | las ena a a a las a las a las os |
| 0.72 | S25 | el cliente establece la conexion creada | las ena a ea a las a aos |

Examples m1c-r2-small-aux0.5 (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 0.29 | S25 | las funciones leen los archivos | las suciones e los aciaios |
| 0.58 | S3 | la revolucion nueva abarca las esferas | las s encioicios doraelas esitaas |
| 0.64 | S3 | las agencias disponen los equipos por la manana | los uan las esios bonmes o rconas as |
| 0.68 | S16 | la teoria erronea reduce el numero | la re a eo taauaros |

Examples m1c-r3-small-aux1.0 (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 0.37 | S15 | el cuaderno presenta las divisiones enteras | el chuaer paeata las ciicios etas |
| 0.59 | S15 | los motores rapidos consumen las energias | los eta eposicone lon icaeacos |
| 0.64 | S15 | los grupos del organismo exigen la liberacion | los esrucocrcan ebiiacore las icaticons |
| 0.70 | S1 | los productos cumplen la propiedad asociada | las prntiietaueda ann s |

Examples m1c-r4-pretrain-keys (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 1.37 | S11 | el cuaderno presenta las divisiones enteras | svlezlcumgnsecdyjsgsixksjmjdsnayrvlsivivnivzypaipzdnszxixvjgsndnveiyixsunvp |
| 2.09 | S16 | el cuaderno presenta las divisiones enteras | desyln qsevxkjpnilyeszjpzhgsnuiynvsjlsvnvpzyamsvcxwzyeixqvsizyenkzynvzpzpynynlsxivkpzynmgsnvlsnivjseivkvjzxdg |
| 2.30 | S19 | el cuaderno presenta las divisiones enteras | kxezycqanskpyiyxsgjlavzlsakqvyfivxzxesgnalskpizkvusysmlseivslivzxsmgnaynkszpeikjkq llzvxliusgzkepluganpykplvjgivzjgn |
| 2.62 | S16 | la teoria erronea reduce el numero | cedjnlncsvggsvkeislqivxvgabenkjzjynigjylguvivybgskiynvpvzlygylvshlexhpqwpynvz lscsmaikpjgjqvsvxvzgn |

Examples m1c-r4-small-aux0.5-pretrained (test; best, p25, median, p75 by CER target):

| CER | Subject | Target | Greedy CTC |
|---|---|---|---|
| 0.33 | S15 | el cuaderno presenta las divisiones enteras | el cuaer preta las daicioos eitrs |
| 0.55 | S19 | el centro describe las parabolas asociadas | e centanescion elas  la caina s |
| 0.63 | S25 | el cuaderno presenta las divisiones enteras | el osuampee de lrenaciins voas |
| 0.69 | S19 | el algoritmo de los controles recorre el nodo | e secot  lao ctunmas cpecios pe |

