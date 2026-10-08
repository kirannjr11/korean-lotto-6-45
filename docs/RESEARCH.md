# Research notes

Research scope: Korean Lotto 6/45, all winning draws 1–1244, through October 3, 2026. Research performed October 8, 2026 (Korea time).

## Primary sources

- [Donghaeng Lottery: Lotto 6/45 introduction](https://www.dhlottery.co.kr/lt645/intro): official game format and first-prize odds of 1 in 8,145,060. Six numbers are selected from 1–45; the bonus number serves a separate prize condition.
- [Donghaeng Lottery: draw results](https://www.dhlottery.co.kr/lt645/result): the official results page.
- [Official result data, including draw 1244](https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do?srchDir=center&srchLtEpsd=1244): current website JSON endpoint discovered during research. Records include `ltEpsd` (round), `ltRflYmd` (date), `tm1WnNo` through `tm6WnNo` and `bnsWnNo`. It is an internal website endpoint, not a promised public API.

## Additional sources checked

- [Lotto Lab historical data](https://raw.githubusercontent.com/minmi0123/lotto-lab/main/app/src/data/lottoData.js): machine-readable independent history used to seed the collection, with official comparisons performed by the collector. Its JavaScript is parsed as data, never executed.
- [LottoNews draw 1244](https://www.lottonews.kr/lotto/summary/1244/): an additional latest-draw cross-check against the official record.
- [Lotto45](https://lotto45.kr/): its indexed page listed history through 1244 and the latest result. Its “AI” scoring labels were not adopted as evidence of predictive power.
- [Lotto draw map](https://lotto.pickbetterlab.com/): the indexed page independently listed rounds 1–1244 and draw 1244 as `1, 13, 18, 26, 34, 38`, bonus `25`. Direct programmatic retrieval of this site returned HTTP 403, so it is a research cross-check, not a data dependency.
- [LottoHaebom](https://lottohaebom.com/): the indexed page identified its recent-data scope as 1145–1244, including a 1235–1244 recent-number summary and attribution to official results.
- [Kit All number statistics](https://kitall.dev/statistics/lotto-stats): the indexed table covered only rounds 1–1210 and included bonus numbers. Its counts should not be compared directly with this project's main-only 1–1244 totals.

The snapshot of round 1244 is October 3, 2026, with six main numbers **1, 13, 18, 26, 34, 38**, and bonus **25**. Full machine-readable verification coverage, including any retrieval limitations, is in `data/sources.json`; it is the authoritative audit record for the saved dataset.

## Research decisions

1. Collect actual results instead of copying another site's rankings. Recompute every frequency and combination statistic locally.
2. Keep main and bonus numbers separate. Different bonus inclusion policies and date cutoffs explain many apparent disagreements between sites.
3. Validate round continuity, exact six-number uniqueness, legal ranges, bonus exclusion and dates before analysis. Reject disagreements rather than choosing a convenient source silently.
4. Show historical patterns with their definitions. A pair or triple can occur often just by chance when thousands of combinations are compared.
5. Evaluate selection rules in chronological order. A test prediction may use only earlier draws. This prevents future-data leakage but cannot itself establish a useful predictive signal.

No private player ticket selections are collected. There is no purchase automation, paid prediction service, or guarantee of winning.
