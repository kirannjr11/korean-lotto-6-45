"""Descriptive Lotto 6/45 statistics, ticket sampling, and past-only evaluation.

Historical frequency is not a prediction of an independent lottery draw. All
rates in this module use draws as the denominator, rather than number slots.
The six main numbers and the bonus number are deliberately counted separately.
"""

from collections import Counter
from datetime import date
from itertools import combinations
from math import comb
import random


NUMBERS = tuple(range(1, 46))
TOTAL_COMBINATIONS = comb(45, 6)
MAX_GENERATED_SETS = 1000
STRATEGIES = ("uniform", "hot", "frequent", "balanced")


def _positive_integer(value, name, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")
    return value


def _random_generator(seed):
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("seed must be an integer or None")
    return random.Random(seed)


def _history(draws):
    """Validate and copy the fields this module consumes without mutating input."""
    if not isinstance(draws, (list, tuple)) or not draws:
        raise ValueError("draws must be a nonempty list or tuple")
    history = []
    previous_round = 0
    previous_date = None
    for draw in draws:
        if not isinstance(draw, dict):
            raise ValueError("each draw must be a dictionary")
        round_number = _positive_integer(draw.get("round"), "draw round")
        if round_number <= previous_round:
            raise ValueError("draw rounds must be unique and in ascending order")
        raw_numbers = draw.get("numbers")
        if not isinstance(raw_numbers, (list, tuple)) or len(raw_numbers) != 6:
            raise ValueError("each draw must contain exactly six main numbers")
        if any(isinstance(n, bool) or not isinstance(n, int) or n not in NUMBERS
               for n in raw_numbers):
            raise ValueError("main numbers must be integers from 1 to 45")
        if len(set(raw_numbers)) != 6:
            raise ValueError("main numbers must be distinct")
        bonus = draw.get("bonus")
        if (isinstance(bonus, bool) or not isinstance(bonus, int)
                or bonus not in NUMBERS or bonus in raw_numbers):
            raise ValueError("bonus must be a distinct integer from 1 to 45")
        raw_date = draw.get("date")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            raise ValueError("draw date must be an ISO date (YYYY-MM-DD)") from None
        if parsed_date.isoformat() != raw_date:
            raise ValueError("draw date must use YYYY-MM-DD")
        if previous_date is not None and parsed_date <= previous_date:
            raise ValueError("draw dates must be in ascending order")
        history.append({"round": round_number, "date": raw_date,
                        "numbers": sorted(raw_numbers), "bonus": bonus})
        previous_round, previous_date = round_number, parsed_date
    return history


def _counts(draws):
    return Counter(number for draw in draws for number in draw["numbers"])


def _rank(counts):
    """Stable numerical tie breaking prevents hidden randomness in rankings."""
    return sorted(NUMBERS, key=lambda number: (-counts[number], number))


def _combination_statistics(draws, size):
    counts = Counter(group for draw in draws
                     for group in combinations(draw["numbers"], size))
    draw_count = len(draws)
    probability = comb(6, size) / comb(45, size)
    rows = [{"numbers": list(group), "count": counts[group],
             "rate": counts[group] / draw_count}
            for group in combinations(NUMBERS, size)]
    top = sorted(rows, key=lambda row: (-row["count"], row["numbers"]))[:20]
    return {"total_possible": comb(45, size),
            "expected_probability": probability,
            "expected_count": draw_count * probability,
            "counts": rows, "top": top}


def _distribution(values):
    observed = [value for value in values if value is not None]
    counts = Counter(observed)
    return [{"value": value, "count": counts[value],
             "rate": counts[value] / len(observed)} for value in sorted(counts)]


def _theoretical_odds():
    tier_counts = [
        (1, "6 main numbers", 1),
        (2, "5 main numbers + bonus", 6),
        (3, "5 main numbers, without bonus", 6 * 38),
        (4, "4 main numbers", comb(6, 4) * comb(39, 2)),
        (5, "3 main numbers", comb(6, 3) * comb(39, 3)),
    ]
    return {
        "total_combinations": TOTAL_COMBINATIONS,
        "number_probability": 6 / 45,
        "bonus_probability": 1 / 45,
        "expected_matches": 6 * 6 / 45,
        "prize_tiers": [
            {"tier": tier, "description": description,
             "winning_combinations": count,
             "probability": count / TOTAL_COMBINATIONS,
             "one_in": TOTAL_COMBINATIONS / count}
            for tier, description, count in tier_counts
        ],
        "match_probabilities": [
            {"matches": matches,
             "probability": comb(6, matches) * comb(39, 6 - matches)
             / TOTAL_COMBINATIONS}
            for matches in range(7)
        ],
        "at_least_3_probability": sum(row[2] for row in tier_counts)
        / TOTAL_COMBINATIONS,
    }


def analyze(draws, window=50):
    """Return descriptive statistics for the supplied ascending draw history.

    ``last_seen`` is a round number or None; ``draws_since`` is the number
    of supplied draws after the last appearance (all supplied draws if unseen).
    Cold means few appearances in the recent window, with longer absence as
    the tie breaker. None of these measures changes the next-draw odds.
    Pair and triple ``counts`` cover every possible combination, including zero.
    """
    _positive_integer(window, "window")
    history = _history(draws)
    total = len(history)
    recent = history[-window:]
    counts = _counts(history)
    recent_counts = _counts(recent)
    bonus_counts = Counter(draw["bonus"] for draw in history)
    last_seen = {}
    for index, draw in enumerate(history):
        for number in draw["numbers"]:
            last_seen[number] = (index, draw["round"])

    number_rows = []
    for number in NUMBERS:
        occurrence = last_seen.get(number)
        number_rows.append({
            "number": number, "count": counts[number],
            "rate": counts[number] / total,
            "recent_count": recent_counts[number],
            "recent_rate": recent_counts[number] / len(recent),
            "bonus_count": bonus_counts[number],
            "last_seen": occurrence[1] if occurrence else None,
            "draws_since": total - occurrence[0] - 1 if occurrence else total,
        })
    by_number = {row["number"]: row for row in number_rows}

    per_draw = []
    previous_numbers = None
    for draw in history:
        numbers = draw["numbers"]
        odd = sum(number % 2 for number in numbers)
        low = sum(number <= 22 for number in numbers)
        bins = {"1-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-45": 0}
        bin_names = tuple(bins)
        for number in numbers:
            bins[bin_names[(number - 1) // 10]] += 1
        per_draw.append({
            **draw, "sum": sum(numbers), "odd": odd, "even": 6 - odd,
            "low": low, "high": 6 - low,
            "consecutive_pairs": sum(b == a + 1 for a, b in zip(numbers, numbers[1:])),
            "span": numbers[-1] - numbers[0],
            "repeated_from_previous": (len(set(numbers) & previous_numbers)
                                       if previous_numbers is not None else None),
            "tens_bins": bins,
        })
        previous_numbers = set(numbers)

    fields = ("sum", "odd", "low", "consecutive_pairs", "span",
              "repeated_from_previous")
    return {
        "summary": {
            "draw_count": total, "first_round": history[0]["round"],
            "last_round": history[-1]["round"],
            "first_date": history[0]["date"], "last_date": history[-1]["date"],
            "window": window, "recent_draw_count": len(recent),
            "total_main_numbers": total * 6,
            "expected_number_count": total * 6 / 45,
            "recent_expected_number_count": len(recent) * 6 / 45,
            "average_sum": sum(row["sum"] for row in per_draw) / total,
            "theoretical_average_sum": 138,
            "last_numbers": list(history[-1]["numbers"]),
            "last_bonus": history[-1]["bonus"],
        },
        "numbers": number_rows,
        "top_hot": [by_number[number] for number in _rank(recent_counts)[:10]],
        "top_frequent": [by_number[number] for number in _rank(counts)[:10]],
        "top_cold": sorted(number_rows, key=lambda row:
                           (row["recent_count"], -row["draws_since"], row["number"]))[:10],
        "pairs": _combination_statistics(history, 2),
        "triples": _combination_statistics(history, 3),
        "per_draw": per_draw,
        "distributions": {field: _distribution(row[field] for row in per_draw)
                          for field in fields},
        "odds": _theoretical_odds(),
        "methodology": {
            "rates": "Occurrences divided by draws; main and bonus counts are separate.",
            "hot": "Most main-number appearances in the last window draws; numerical ties.",
            "frequent": "Most main-number appearances across the supplied history; numerical ties.",
            "cold": "Fewest recent appearances; then longest absence; then number.",
            "low_high": "Low: 1-22. High: 23-45.",
            "combination_expectation": "Per-combination probability is C(6,k) / C(45,k).",
            "limitation": "Descriptive history is not evidence of a predictive advantage. "
                          "Every fixed set of six numbers has the same jackpot probability "
                          "in a fair, independent draw.",
        },
    }


def _weighted_ticket(weights, rng):
    available = list(NUMBERS)
    selected = []
    for _ in range(6):
        chosen = rng.choices(available, weights=[weights[n] for n in available], k=1)[0]
        available.remove(chosen)
        selected.append(chosen)
    return tuple(sorted(selected))


def generate_sets(draws, count=5, strategy="uniform", seed=None, window=50):
    """Sample distinct tickets for exploration, without a claimed advantage.

    Hot/frequent use the respective historical counts plus one as sampling
    weights, sampling six distinct numbers without replacement. Balanced
    uniformly samples tickets with exactly three odd and three low (1-22)
    numbers. These filters do not improve an individual ticket's win odds.
    """
    _positive_integer(count, "count", MAX_GENERATED_SETS)
    _positive_integer(window, "window")
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {', '.join(STRATEGIES)}")
    rng = _random_generator(seed)
    history = _history(draws)
    weights = None
    if strategy in ("hot", "frequent"):
        counts = _counts(history[-window:] if strategy == "hot" else history)
        weights = {number: counts[number] + 1 for number in NUMBERS}
    tickets, seen = [], set()
    # Very concentrated synthetic histories can make weighted unique sampling
    # expensive. Fail explicitly instead of silently changing the strategy.
    max_attempts = max(10000, count * 1000)
    for _ in range(max_attempts):
        ticket = (_weighted_ticket(weights, rng) if weights is not None
                  else tuple(sorted(rng.sample(NUMBERS, 6))))
        if strategy == "balanced":
            if sum(number % 2 for number in ticket) != 3:
                continue
            if sum(number <= 22 for number in ticket) != 3:
                continue
        if ticket not in seen:
            seen.add(ticket)
            tickets.append(list(ticket))
            if len(tickets) == count:
                return tickets
    raise ValueError("could not sample enough distinct sets; request fewer sets "
                     "or use uniform sampling")


def backtest(draws, window=50, start_round=None, seed=645):
    """Evaluate one ticket per strategy and draw using strictly earlier data.

    At least ``window`` prior draws are required. Hot selects the six most
    common numbers in that rolling window; frequent selects the six most
    common numbers in all earlier draws. Ties use the lower number. Uniform
    samples one independent ticket for each evaluated draw. Rankings here
    are deterministic; weighted exploratory generation is a different method.
    """
    _positive_integer(window, "window")
    if start_round is not None:
        _positive_integer(start_round, "start_round")
    rng = _random_generator(seed)
    history = _history(draws)
    names = ("uniform", "hot", "frequent")
    histograms = {name: Counter() for name in names}
    rounds = []
    cumulative = _counts(history[:window])
    rolling = cumulative.copy()
    for index in range(window, len(history)):
        draw = history[index]
        # Sample every eligible round, even if excluded by start_round, so a
        # seed refers to the same baseline ticket under different cutoffs.
        predictions = {
            "uniform": sorted(rng.sample(NUMBERS, 6)),
            "hot": sorted(_rank(rolling)[:6]),
            "frequent": sorted(_rank(cumulative)[:6]),
        }
        if start_round is None or draw["round"] >= start_round:
            actual = set(draw["numbers"])
            matches = {name: len(set(ticket) & actual)
                       for name, ticket in predictions.items()}
            for name, match_count in matches.items():
                histograms[name][match_count] += 1
            rounds.append({"round": draw["round"], "numbers": list(draw["numbers"]),
                           "predictions": predictions, "matches": matches})
        cumulative.update(draw["numbers"])
        rolling.subtract(history[index - window]["numbers"])
        rolling.update(draw["numbers"])
    evaluated = len(rounds)
    strategies = {}
    for name in names:
        histogram = histograms[name]
        hits = sum(histogram[matched] for matched in range(3, 7))
        strategies[name] = {
            "avg_matches": (sum(matched * count for matched, count in histogram.items())
                            / evaluated if evaluated else None),
            "match_histogram": {str(matched): histogram[matched] for matched in range(7)},
            "hits_at_least_3": hits,
            "hit_rate_at_least_3": hits / evaluated if evaluated else None,
        }
    return {
        "window": window, "draw_count": evaluated,
        "start_round": rounds[0]["round"] if rounds else None,
        "end_round": rounds[-1]["round"] if rounds else None,
        "seed": seed, "expected_matches": 6 * 6 / 45,
        "expected_at_least_3_rate": _theoretical_odds()["at_least_3_probability"],
        "strategies": strategies, "rounds": rounds,
        "methodology": {
            "training": "Predictions use only rounds before the evaluated draw. "
                        "Hot uses the prior window; frequent uses all prior draws.",
            "selection": "Hot/frequent take the top six, with lower-number ties. "
                         "These are different from weighted generated sets.",
            "baseline": "One uniformly sampled ticket per draw. "
                        "Expected main-number matches per ticket: 0.8.",
            "scoring": "Main-number intersections only; bonus and prize payouts are not scored.",
            "limitation": "Historical performance, including a lead over one random baseline, "
                          "does not establish predictive power or future profits.",
            "insufficient_history": evaluated == 0,
        },
    }
