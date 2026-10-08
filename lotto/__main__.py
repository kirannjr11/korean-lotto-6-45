"""Run with python -m lotto; no package installation required."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from .data import DEFAULT_DATA, ROOT, atomic_write, draws_csv, load_draws


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def select_draws(path, start=None, end=None):
    draws = load_draws(path)
    start = draws[0]["round"] if start is None else start
    end = draws[-1]["round"] if end is None else end
    if not draws[0]["round"] <= start <= end <= draws[-1]["round"]:
        raise ValueError(f"Choose a range within {draws[0]['round']}..{draws[-1]['round']}.")
    return [d for d in draws if start <= d["round"] <= end]


def write_report(draws, window, directory):
    from .analysis import analyze, backtest, generate_sets
    report = analyze(draws, window=window)
    evaluation = backtest(draws, window=window) if len(draws) > window else None
    destination = Path(directory)
    atomic_write(destination / "analysis.json", json_text(report))
    atomic_write(destination / "backtest.json", json_text(evaluation))
    atomic_write(destination / "draws.csv", draws_csv(draws))
    for filename, rows in (("number_frequency.csv", report["numbers"]), ("draw_features.csv", report["per_draw"]),
                           ("pair_frequency.csv", report["pairs"]["counts"]), ("triple_frequency.csv", report["triples"]["counts"])):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})
        atomic_write(destination / filename, stream.getvalue())
    hot = ", ".join(f"{r['number']} ({r['recent_count']})" for r in report["top_hot"][:10])
    frequent = ", ".join(f"{r['number']} ({r['count']})" for r in report["top_frequent"][:10])
    features = report["per_draw"]
    common_odd = max(report["distributions"]["odd"], key=lambda row: row["count"])
    common_low = max(report["distributions"]["low"], key=lambda row: row["count"])
    consecutive = sum(row["consecutive_pairs"] > 0 for row in features)
    lines = ["# Korean Lotto 6/45 analysis", "",
             f"Data: {len(draws):,} draws, rounds {draws[0]['round']}–{draws[-1]['round']}, through {draws[-1]['date']}.", "",
             "Only the six main numbers enter the frequency and combination analysis. Bonus counts are separate.", "",
             f"Hot numbers over the most recent {min(window, len(draws))} draws (number / count): {hot}.", "",
             f"Most frequent in the selected history (number / count): {frequent}.", "",
             "## Structure of the winning sets", "",
             f"Mean sum: {report['summary']['average_sum']:.2f} (fair-draw expectation: 138). Observed sum range: {min(row['sum'] for row in features)}–{max(row['sum'] for row in features)}.", "",
             f"Most common odd/even split: {common_odd['value']} / {6-common_odd['value']}, in {common_odd['count']} draws ({common_odd['rate']:.1%}).", "",
             f"Most common low/high split (1–22 / 23–45): {common_low['value']} / {6-common_low['value']}, in {common_low['count']} draws ({common_low['rate']:.1%}).", "",
             f"At least one consecutive pair appeared in {consecutive} draws ({consecutive/len(draws):.1%}).", "",
             "`draw_features.csv` contains the full combination analysis for each draw, including spans, number bands and overlap with its predecessor.", "",
             "## Repeated combinations", "", "| Pair | Draw count |", "| --- | ---: |"]
    for row in report["pairs"]["top"][:10]:
        lines.append(f"| {', '.join(map(str, row['numbers']))} | {row['count']} |")
    lines += ["", "| Triple | Draw count |", "| --- | ---: |"]
    for row in report["triples"]["top"][:10]:
        lines.append(f"| {', '.join(map(str, row['numbers']))} | {row['count']} |")
    if evaluation:
        lines += ["", "## Walk-forward comparison", "",
                  f"{evaluation['draw_count']} test draws; each prediction uses earlier draws only. One ticket per strategy per draw; seed 645.", "",
                  "| Method | Mean matches | Tickets with 3+ main matches |", "| --- | ---: | ---: |"]
        for name, row in evaluation["strategies"].items():
            lines.append(f"| {name} | {row['avg_matches']:.4f} | {row['hits_at_least_3']} |")
        lines += ["", "A fair random ticket has 0.8 expected main-number matches. These descriptive results are not evidence of a predictive advantage."]
    lines += ["", "## Example sets", "", "Reproducible uniform samples (seed 645); these are not forecasts.", ""]
    lines += ["- " + ", ".join(map(str, ticket)) for ticket in generate_sets(draws, seed=645, window=window)]
    lines += ["", "Every six-number combination has a first-prize probability of 1 / 8,145,060 in a fair draw. Hot, cold, frequent and balanced selections do not improve that probability.", "",
              "Sources and verification coverage are recorded in `data/sources.json`; see `docs/RESEARCH.md` for research notes.", ""]
    atomic_write(destination / "summary.md", "\n".join(lines))
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description="Korean Lotto 6/45 historical analysis; not a reliable predictor.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Path to saved draws.json")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="Download and verify historical results")
    sync.add_argument("--end", type=int, default=1244)
    sync.add_argument("--output-dir", type=Path, default=ROOT / "data")
    validate = commands.add_parser("validate", help="Validate all records and round continuity")
    validate.add_argument("--end", type=int)
    report = commands.add_parser("report", help="Write analysis JSON, CSVs and a readable report")
    report.add_argument("--output", type=Path, default=ROOT / "reports")
    report.add_argument("--start", type=int)
    report.add_argument("--end", type=int)
    report.add_argument("--window", type=int, default=50)
    generate = commands.add_parser("generate", help="Sample sets using an explicit heuristic")
    generate.add_argument("--strategy", choices=["uniform", "hot", "frequent", "balanced"], default="uniform")
    generate.add_argument("--count", type=int, default=5)
    generate.add_argument("--seed", type=int, default=645)
    generate.add_argument("--window", type=int, default=50)
    generate.add_argument("--end", type=int)
    evaluate = commands.add_parser("backtest", help="Compare prior-only selections against random tickets")
    evaluate.add_argument("--window", type=int, default=50)
    evaluate.add_argument("--start-round", type=int)
    evaluate.add_argument("--end", type=int)
    evaluate.add_argument("--seed", type=int, default=645)
    serve_parser = commands.add_parser("serve", help="Start the local browser dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=6450)
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            from .sources import sync_draws
            manifest = sync_draws(end_round=args.end, output_dir=args.output_dir,
                                  progress=lambda message: print(message, file=sys.stderr, flush=True))
            print(json_text(manifest))
        elif args.command == "validate":
            from .data import validate_draws
            draws = validate_draws(load_draws(args.data), expected_start=1, expected_end=args.end)
            print(f"Valid: {len(draws):,} contiguous draws, {draws[0]['round']}-{draws[-1]['round']}, through {draws[-1]['date']}.")
        elif args.command == "report":
            draws = select_draws(args.data, args.start, args.end)
            result = write_report(draws, args.window, args.output)
            print(f"Report written to {result.resolve()}")
        elif args.command == "generate":
            from .analysis import generate_sets
            draws = select_draws(args.data, end=args.end)
            sets = generate_sets(draws, count=args.count, strategy=args.strategy, seed=args.seed, window=args.window)
            print(json_text({"through_round": draws[-1]["round"], "strategy": args.strategy, "seed": args.seed, "sets": sets,
                             "note": "These are heuristic samples, not reliable predictions. Each set has first-prize odds of 1 in 8,145,060."}))
        elif args.command == "backtest":
            from .analysis import backtest
            result = backtest(select_draws(args.data, end=args.end), window=args.window, start_round=args.start_round, seed=args.seed)
            print(json_text({k: v for k, v in result.items() if k != "rounds"}))
        elif args.command == "serve":
            from .server import serve
            serve(args.host, args.port, args.data)
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
