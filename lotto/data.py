"""Strict, dependency-free loading and validation of historical draws."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "draws.json"
DEFAULT_SOURCES = ROOT / "data" / "sources.json"
FIRST_DRAW_DATE = date(2002, 12, 7)


def validate_draws(draws, *, expected_start=None, expected_end=None):
    """Reject gaps, duplicates and malformed results; return ascending records.

    Dates are checked against the weekly draw calendar, never filled in silently.
    Optional source metadata is preserved; bonuses never enter the main set.
    """
    if not isinstance(draws, list) or not draws:
        raise ValueError("Draw data must be a non-empty list.")
    result = []
    for record in draws:
        if not isinstance(record, dict):
            raise ValueError("Each draw must be an object.")
        round_no = record.get("round")
        if type(round_no) is not int or round_no < 1:
            raise ValueError("Round numbers must be positive integers.")
        numbers = record.get("numbers")
        if (not isinstance(numbers, list) or len(numbers) != 6
                or any(type(n) is not int or not 1 <= n <= 45 for n in numbers)
                or len(set(numbers)) != 6):
            raise ValueError(f"Draw {round_no}: need six distinct integers from 1 to 45.")
        bonus = record.get("bonus")
        if type(bonus) is not int or not 1 <= bonus <= 45 or bonus in numbers:
            raise ValueError(f"Draw {round_no}: bonus must be a different number from 1 to 45.")
        try:
            draw_date = date.fromisoformat(record["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Draw {round_no}: invalid ISO draw date.") from exc
        try:
            expected_date = FIRST_DRAW_DATE + timedelta(weeks=round_no - 1)
        except OverflowError as exc:
            raise ValueError(f"Draw {round_no}: round is outside the supported calendar.") from exc
        if draw_date != expected_date:
            raise ValueError(f"Draw {round_no}: expected calendar date {expected_date}.")
        result.append({**record, "numbers": sorted(numbers), "date": draw_date.isoformat()})
    result.sort(key=lambda d: d["round"])
    rounds = [d["round"] for d in result]
    if len(set(rounds)) != len(rounds):
        raise ValueError("Duplicate round numbers in dataset.")
    first = rounds[0] if expected_start is None else expected_start
    last = rounds[-1] if expected_end is None else expected_end
    if rounds != list(range(first, last + 1)):
        raise ValueError(f"Expected every round from {first} through {last}, with no gaps.")
    return result


def load_draws(path=DEFAULT_DATA):
    path = Path(path)
    if not path.exists():
        raise ValueError(f"No dataset at {path}. Run: python -m lotto sync --end 1244")
    with path.open(encoding="utf-8-sig") as handle:
        return validate_draws(json.load(handle))


def atomic_write(path, content):
    """Replace one generated artifact only after its new contents are complete."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def save_draws(draws, path=DEFAULT_DATA):
    valid = validate_draws(draws)
    atomic_write(path, json.dumps(valid, ensure_ascii=False, indent=2) + "\n")


def draws_csv(draws):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["round", "date", "n1", "n2", "n3", "n4", "n5", "n6", "bonus", "source"])
    for draw in draws:
        writer.writerow([draw["round"], draw["date"], *draw["numbers"], draw["bonus"], draw.get("source", "")])
    return buffer.getvalue()
