# Korean Lotto 6/45 analysis

Data: 1,244 draws, rounds 1–1244, through 2026-10-03.

Only the six main numbers enter the frequency and combination analysis. Bonus counts are separate.

Hot numbers over the most recent 50 draws (number / count): 31 (11), 38 (11), 13 (10), 15 (10), 27 (10), 1 (9), 18 (9), 16 (8), 24 (8), 28 (8).

Most frequent in the selected history (number / count): 34 (187), 13 (184), 27 (181), 12 (180), 18 (180), 33 (175), 45 (175), 37 (174), 38 (174), 40 (174).

## Structure of the winning sets

Mean sum: 138.28 (fair-draw expectation: 138). Observed sum range: 48–238.

Most common odd/even split: 3 / 3, in 414 draws (33.3%).

Most common low/high split (1–22 / 23–45): 3 / 3, in 411 draws (33.0%).

At least one consecutive pair appeared in 643 draws (51.7%).

`draw_features.csv` contains the full combination analysis for each draw, including spans, number bands and overlap with its predecessor.

## Repeated combinations

| Pair | Draw count |
| --- | ---: |
| 11, 21 | 34 |
| 33, 40 | 33 |
| 6, 38 | 31 |
| 10, 31 | 31 |
| 12, 24 | 31 |
| 37, 40 | 31 |
| 1, 28 | 30 |
| 34, 42 | 30 |
| 3, 13 | 29 |
| 3, 20 | 29 |

| Triple | Draw count |
| --- | ---: |
| 1, 3, 27 | 8 |
| 3, 8, 27 | 8 |
| 3, 20, 44 | 8 |
| 12, 15, 24 | 8 |
| 12, 34, 42 | 8 |
| 33, 37, 40 | 8 |
| 2, 25, 28 | 7 |
| 3, 8, 42 | 7 |
| 3, 12, 13 | 7 |
| 3, 20, 24 | 7 |

## Walk-forward comparison

1194 test draws; each prediction uses earlier draws only. One ticket per strategy per draw; seed 645.

| Method | Mean matches | Tickets with 3+ main matches |
| --- | ---: | ---: |
| uniform | 0.8333 | 37 |
| hot | 0.7956 | 24 |
| frequent | 0.7806 | 34 |

A fair random ticket has 0.8 expected main-number matches. These descriptive results are not evidence of a predictive advantage.

## Example sets

Reproducible uniform samples (seed 645); these are not forecasts.

- 7, 10, 13, 19, 27, 40
- 2, 14, 18, 20, 31, 45
- 7, 17, 18, 21, 22, 35
- 3, 5, 12, 22, 34, 44
- 8, 21, 24, 31, 44, 45

Every six-number combination has a first-prize probability of 1 / 8,145,060 in a fair draw. Hot, cold, frequent and balanced selections do not improve that probability.

Sources and verification coverage are recorded in `data/sources.json`; see `docs/RESEARCH.md` for research notes.
