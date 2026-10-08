# Analysis and evaluation methodology

This project describes historical Korean Lotto 6/45 results and samples example tickets. It does not establish a way to predict a fair, independent lottery. Frequency rankings and apparent patterns can arise by chance, particularly when examining many numbers and combinations.

## Dataset and selected history

Each record has a round, draw date, six distinct main numbers from 1 to 45, and one different bonus number. Loading checks unique contiguous rounds, the weekly calendar starting on 2002-12-07, and valid numbers. Input order is normalized. Provenance and verification coverage are recorded in `data/sources.json`; research notes are in `docs/RESEARCH.md`.

Analyses describe only the supplied or selected range. “Recent” means the last `min(window, selected_draw_count)` recorded draws, not a period relative to today's date. Main-number frequencies, pair/triple counts, features, generation weights, and backtest matches exclude bonuses. Bonus counts are displayed separately.

## Number and combination statistics

- **Frequent:** main-number count over the selected history, descending. Ties use the lower number.
- **Hot:** main-number count in the recent window, descending. Ties use the lower number.
- **Cold:** recent count ascending, then longest absence, then lower number. Being cold or absent does not make a number due to appear.
- **Rate:** appearance count divided by the relevant number of draws. This is not the number's share of all six-number slots; number rates sum to six.
- **Last seen:** the last supplied round containing a number, or `null` if absent throughout the supplied history.
- **Draws since:** the number of supplied draws after that appearance; zero means it appeared in the last supplied draw. If unseen, this equals the supplied history length. It does not claim knowledge before the selected range.

All 990 pairs and 14,190 triples are counted, including combinations never seen. A draw contributes 15 pairs and 20 triples. Exports contain the complete counts; the dashboard receives the top 20 for each size, with numerical ordering to break count ties. For a fixed group of `k` distinct numbers, its probability of appearing in a fair draw is `C(6,k) / C(45,k)`. Its expected count in `N` draws is `N` times that probability: `N/66` for a pair and `2N/1419` for a triple. These expectations are descriptive references, not significance tests.

Per-draw features include sum, odd/even counts, low/high counts, span, consecutive pairs, overlap with the previous supplied draw, and bins 1–10, 11–20, 21–30, 31–40, and 41–45. Low is 1–22; high is 23–45. Span is maximum minus minimum. Consecutive pairs count adjacent numbers differing by one, so a run of four contributes three. The first supplied draw has no previous-draw overlap (`null`) and is excluded from that feature's frequency distribution. The theoretical average sum is 138.

## Example ticket generation

Each ticket has six distinct, sorted numbers. Tickets returned in the same batch are distinct. The CLI and dashboard default to seed 645 for reproducibility; the Python function accepts an explicit integer seed or `None`.

- **Uniform:** sample six numbers uniformly without replacement.
- **Hot:** sample sequentially without replacement using recent count plus one as each remaining number's weight.
- **Frequent:** use full selected-history count plus one as the sampling weight.
- **Balanced:** uniformly sample and accept only sets containing exactly three odd numbers and exactly three low numbers (1–22).

Adding one keeps every number eligible for weighted sampling. Filters and weights choose which tickets are shown; they do not improve a particular ticket's jackpot probability. All strategies use historical data only, and none is presented as a validated forecast.

## Historical backtest

The backtest starts after at least `window` earlier draws are available. For each evaluated draw it forms one ticket per method before adding the actual result to training:

1. **Hot:** the six highest-count numbers in the immediately preceding `window` draws.
2. **Frequent:** the six highest-count numbers in all preceding supplied draws.
3. **Uniform:** one uniformly sampled ticket from a seeded pseudorandom generator.

Hot and frequent ties favor the lower number. These deterministic top-six methods differ from the weighted sampling used by the example-ticket generator; the backtest does not evaluate those weighted samples. A requested evaluation start round excludes earlier scores while keeping earlier draws for training. The end round excludes later draws entirely. The random baseline consumes one ticket for every eligible draw before a start cutoff, keeping the same baseline tickets when only that cutoff changes.

Scoring counts intersections with the six actual main numbers. Reports give mean matches, a 0–6 match histogram, and the number/rate of tickets with at least three main matches. Bonus-dependent ranks, payouts, spending, and profit are not evaluated. Insufficient history produces zero evaluated draws and `null` averages, not zero performance.

Every fixed ticket has `6 × 6 / 45 = 0.8` expected main-number matches per fair draw. For exactly `m` main matches, the probability is `C(6,m) × C(39,6-m) / C(45,6)`. A favorable historical score against one random baseline is not evidence of a future advantage. No significance claim, forecast calibration, or profitability claim is made.

## Exact theoretical odds

There are `C(45,6) = 8,145,060` possible six-number tickets. The following counts are the numerators of exact probabilities with that common denominator:

| Result | Winning tickets | Probability |
| --- | ---: | ---: |
| Six main numbers | 1 | 1 / 8,145,060 |
| Five main numbers and bonus | 6 | 6 / 8,145,060 |
| Five main numbers without bonus | 228 | 228 / 8,145,060 |
| Four main numbers | 11,115 | 11,115 / 8,145,060 |
| Three main numbers | 182,780 | 182,780 / 8,145,060 |

The probability of at least three main matches is `194,130 / 8,145,060`. Each number's marginal main-number probability is `6/45`; its marginal bonus probability is `1/45`. These calculations assume a fair draw, and do not depend on historical hot or cold status.

## Reproducing the calculations

Use a saved dataset to make results independent of later source changes:

```text
python -m lotto validate --end 1244
python -m lotto report --end 1244 --window 50
python -m lotto backtest --end 1244 --window 50 --seed 645
python -m lotto generate --end 1244 --strategy uniform --seed 645
python -m unittest discover -s tests -v
```

The report includes full JSON, number/pair/triple frequency CSVs, per-draw features, draw results, and a readable summary. Record the dataset, selected rounds, window, method, and seed when comparing runs.
