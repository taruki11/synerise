from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.strategy_analysis import run_strategy_analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run threshold and top-k strategy analysis for a trained experiment.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--output-prefix", type=str, required=True)
    parser.add_argument("--model-name", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_strategy_analysis(
        reports_dir=args.reports_dir,
        output_prefix=args.output_prefix,
        model_name=args.model_name,
    )
    print(summary)


if __name__ == "__main__":
    main()
