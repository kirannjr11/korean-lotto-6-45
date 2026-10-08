"""Fetch draw history with explicit provenance and official cross-checks.

Donghaeng's JSON endpoint is used by its public result page; it is an
undocumented website endpoint, not a supported public API. Historical pages
are requested sequentially with a delay, and verified responses are cached.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .data import (DEFAULT_DATA, DEFAULT_SOURCES, FIRST_DRAW_DATE, atomic_write,
                   draws_csv, save_draws, validate_draws)

ARCHIVE_URL = "https://raw.githubusercontent.com/minmi0123/lotto-lab/main/app/src/data/lottoData.js"
ARCHIVE_PAGE = "https://github.com/minmi0123/lotto-lab"
OFFICIAL_PAGE = "https://www.dhlottery.co.kr/lt645/result"
OFFICIAL_ENDPOINT = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
INDEPENDENT_PAGE = "https://www.lottonews.kr/lotto/summary/1244/"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _fetch(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LottoHistoryResearch/1.0)",
        "Accept": "application/json,text/plain,*/*",
        "Referer": OFFICIAL_PAGE,
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def parse_archive(text, end_round):
    """Parse JSON records without executing the downloaded JavaScript."""
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith('{"round":'):
            continue
        record = json.loads(line.strip().rstrip(','))
        if type(record.get("round")) is not int or record["round"] < 1:
            raise ValueError("Archive contains an invalid round number.")
        if record["round"] > end_round:
            continue
        try:
            rows.append({
                "round": record["round"],
                "date": (FIRST_DRAW_DATE + timedelta(weeks=record["round"] - 1)).isoformat(),
                "numbers": record["n"], "bonus": record["b"], "source": ARCHIVE_URL,
            })
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError("Archive is missing valid draw fields.") from exc
    return validate_draws(rows, expected_start=1, expected_end=end_round)


def normalize_official(record):
    if not isinstance(record, dict):
        raise ValueError("Official response contains a draw that is not an object.")
    try:
        round_no = record["ltEpsd"]
        raw_date = str(record["ltRflYmd"])
        numbers = [record[f"tm{i}WnNo"] for i in range(1, 7)]
        bonus = record["bnsWnNo"]
    except KeyError as exc:
        raise ValueError("Official response is missing required draw fields.") from exc
    if len(raw_date) != 8 or not raw_date.isdigit():
        raise ValueError("Official response contains an invalid draw date.")
    result = {
        "round": round_no,
        "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
        "numbers": numbers,
        "bonus": bonus,
        "source": f"{OFFICIAL_ENDPOINT}?srchDir=center&srchLtEpsd={round_no}",
    }
    return validate_draws([result])[0]


def _same_draw(left, right):
    return all(left[key] == right[key] for key in ("round", "date", "numbers", "bonus"))


def _official_page(round_no):
    url = f"{OFFICIAL_ENDPOINT}?srchDir=center&srchLtEpsd={round_no}"
    payload = json.loads(_fetch(url).decode("utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Official response is missing its data object.")
    rows = payload["data"].get("list")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Official response for round {round_no} has no draw records.")
    # Validate before any result can be marked as official.
    for row in rows:
        normalize_official(row)
    return rows


def sync_data(end_round=1244, output=DEFAULT_DATA, manifest_path=DEFAULT_SOURCES,
              verify_official=True, delay_seconds=1.2, progress=None):
    """Save complete history; report precisely which rounds were verified.

    A network failure leaves unverified rows attributed to the archive. An
    actual disagreement or malformed result aborts before replacing artifacts.
    Existing official response caches avoid repeating historical requests.
    """
    if type(end_round) is not int or end_round < 1:
        raise ValueError("end_round must be a positive integer.")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must not be negative.")
    output, manifest_path = Path(output), Path(manifest_path)
    raw_dir = output.parent / "raw"
    cached_path = raw_dir / "official-results.json"
    archive_bytes = _fetch(ARCHIVE_URL)
    draws = parse_archive(archive_bytes.decode("utf-8-sig"), end_round)
    by_round = {row["round"]: row for row in draws}
    verified = {}
    fetched_rows = {}
    cached_count = 0
    warnings = []
    cached_retrieved_at = None
    if verify_official and cached_path.exists():
        cached = json.loads(cached_path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict) or not isinstance(cached.get("records"), list):
            raise ValueError("Official cache is missing its draw records.")
        cached_retrieved_at = cached.get("retrieved_at")
        for row in cached["records"]:
            normalized = normalize_official(row)
            round_no = normalized["round"]
            if round_no <= end_round:
                if not _same_draw(by_round[round_no], normalized):
                    raise ValueError(f"Archive disagrees with cached official draw {round_no}.")
                verified[round_no] = normalized
                fetched_rows[round_no] = row
        cached_count = len(verified)
    request_count = 0
    if verify_official:
        while len(verified) < end_round:
            target = max(set(by_round) - set(verified))
            if request_count:
                time.sleep(delay_seconds)
            try:
                raw_rows = _official_page(target)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                warnings.append(f"Official retrieval stopped: {exc}. Remaining rows use the archive.")
                break
            request_count += 1
            added = 0
            for raw in raw_rows:
                official = normalize_official(raw)
                round_no = official["round"]
                if round_no > end_round:
                    continue
                if not _same_draw(by_round[round_no], official):
                    raise ValueError(f"Archive disagrees with official draw {round_no}; existing data was not replaced.")
                if round_no not in verified:
                    added += 1
                verified[round_no] = official
                fetched_rows[round_no] = raw
            if not added:
                raise ValueError(f"Official response did not contain missing draw {target}.")
            if progress:
                progress(f"Verified {len(verified)}/{end_round} draws against Donghaeng Lottery.")
    else:
        warnings.append("Official verification was disabled; data is attributed to the archive.")

    final = validate_draws([verified.get(row["round"], row) for row in draws],
                           expected_start=1, expected_end=end_round)
    generated_at = _now()
    manifest = {
        "generated_at": generated_at,
        "start_round": 1, "end_round": end_round, "draw_count": len(final),
        "first_draw_date": final[0]["date"], "last_draw_date": final[-1]["date"],
        "official_verified_count": len(verified),
        "official_verified_rounds": sorted(verified),
        "official_cached_count": cached_count,
        "official_cache_retrieved_at": cached_retrieved_at,
        "official_requests": request_count,
        "all_official_verified": len(verified) == end_round,
        "coverage_note": (f"All {end_round} rounds match the official website's draw records. "
                          "Dates, six main numbers, and bonus numbers were cross-checked."
                          if len(verified) == end_round else
                          f"All {end_round} rounds are present; {len(verified)} match official records. "
                          "Remaining rows use the attributed independent archive, with dates derived from the weekly calendar."),
        "date_method": ("Official draw date for every record." if len(verified) == end_round else
                        "Official date for verified rounds; 2002-12-07 + 7*(round-1) days for archive-only rounds."),
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "warnings": warnings,
        "sources": [
            {"name": "Donghaeng Lottery official results", "url": OFFICIAL_PAGE,
             "role": "Primary draw result verification", "reliability": "Official lottery operator"},
            {"name": "Donghaeng results JSON", "url": OFFICIAL_ENDPOINT,
             "role": "Reported draw dates, six main numbers, and bonus numbers",
             "reliability": "Official website internal endpoint; undocumented and subject to change"},
            {"name": "Lotto Lab public history archive", "url": ARCHIVE_URL,
             "role": "Complete seed archive; checked against official records",
             "reliability": "Independent public archive"},
            {"name": "LottoNews round 1244", "url": INDEPENDENT_PAGE,
             "role": "Additional round 1244 web research cross-check",
             "reliability": "Independent results publisher"},
        ],
    }
    # No output is replaced until all available comparisons and validations pass.
    atomic_write(raw_dir / "archive-lottoData.js.txt", archive_bytes.decode("utf-8-sig"))
    if fetched_rows:
        atomic_write(cached_path, json.dumps({
            "retrieved_at": generated_at if request_count else cached_retrieved_at,
            "endpoint": OFFICIAL_ENDPOINT,
            "records": [fetched_rows[n] for n in sorted(fetched_rows)],
        }, ensure_ascii=False, indent=2) + "\n")
    save_draws(final, output)
    atomic_write(output.with_suffix(".csv"), draws_csv(final))
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def sync_draws(end_round=1244, output_dir="data", **kwargs):
    output_dir = Path(output_dir)
    return sync_data(end_round, output_dir / "draws.json", output_dir / "sources.json", **kwargs)
