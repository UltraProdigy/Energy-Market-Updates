from __future__ import annotations

import argparse
from pathlib import Path

from energy_market_updates.config import load_config
from energy_market_updates.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Energy market update pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Scan sources and build a report for newly found documents.")
    run_parser.add_argument(
        "--config",
        default="configs/sources.json",
        help="Path to the JSON config file.",
    )
    run_parser.add_argument(
        "--source",
        action="append",
        help="Optional source id to run. Repeat to run multiple sources.",
    )
    run_parser.add_argument(
        "--backfill-initial",
        action="store_true",
        help="Process currently listed documents on the first run instead of baselining them.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        project_root = Path.cwd()
        config_path = Path(args.config)
        config = load_config(config_path, project_root=project_root)
        selected_sources = set(args.source) if args.source else None
        result = run_pipeline(
            config=config,
            selected_sources=selected_sources,
            backfill_initial=args.backfill_initial,
        )

        baselines = result["baselines"]
        new_documents = result["new_documents"]
        report_path = result["report_path"]

        for source_id, count in baselines:
            print(f"Baselined {count} existing documents for {source_id}.")

        print(f"New documents processed: {len(new_documents)}")
        if report_path:
            print(f"Report written to: {report_path}")
        else:
            print("No report written for this run.")


if __name__ == "__main__":
    main()
