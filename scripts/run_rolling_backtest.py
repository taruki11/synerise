from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest import run_rolling_backtest
from src.config import PipelineConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rolling backtest on a built feature table.")
    parser.add_argument("--feature-path", type=Path, required=True)
    parser.add_argument("--output-prefix", type=str, required=True)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--min-train-snapshots", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PipelineConfig(
        dataset_root=Path("."),
        reports_dir=args.reports_dir,
        models_dir=args.models_dir,
        output_prefix=args.output_prefix,
    )
    results, summary = run_rolling_backtest(
        feature_path=args.feature_path,
        config=config,
        model_name=args.model_name,
        min_train_snapshots=args.min_train_snapshots,
    )
    print("[rolling_backtest_results]")
    print(results.to_string(index=False))
    print("[rolling_backtest_summary]")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
