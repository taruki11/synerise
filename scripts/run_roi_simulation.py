from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.roi_analysis import run_roi_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ROI simulation on strategy analysis outputs.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--output-prefix", type=str, required=True)
    parser.add_argument("--model-name", type=str, default="xgboost")
    parser.add_argument(
        "--scenario-preset",
        type=str,
        default="default",
        choices=["default", "realistic_ecommerce"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_roi_simulation(
        reports_dir=args.reports_dir,
        output_prefix=args.output_prefix,
        model_name=args.model_name,
        scenario_preset=args.scenario_preset,
    )
    for key, value in outputs.items():
        print(f"[{key}] {value}")


if __name__ == "__main__":
    main()
