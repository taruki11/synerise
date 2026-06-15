from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PipelineConfig
from src.feature_engineering import build_feature_table
from src.train import train_and_evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Synerise churn prediction pipeline.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-prefix", type=str, default="synerise_churn")
    parser.add_argument("--observation-days", type=int, default=30)
    parser.add_argument("--label-days", type=int, default=14)
    parser.add_argument("--snapshot-step-days", type=int, default=14)
    parser.add_argument("--max-snapshots", type=int, default=None)
    parser.add_argument("--sample-frac", type=float, default=None)
    parser.add_argument("--generate-eda", action="store_true")
    parser.add_argument(
        "--active-user-definition",
        choices=["historical_buyers", "recently_active_buyers", "recent_engaged_buyers"],
        default="recent_engaged_buyers",
    )
    parser.add_argument(
        "--churn-definition",
        choices=["no_buy_in_label_window", "no_buy_and_low_future_activity"],
        default="no_buy_and_low_future_activity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PipelineConfig(
        dataset_root=args.dataset_root,
        observation_days=args.observation_days,
        label_days=args.label_days,
        snapshot_step_days=args.snapshot_step_days,
        max_snapshots=args.max_snapshots,
        sample_frac=args.sample_frac,
        output_prefix=args.output_prefix,
        active_user_definition=args.active_user_definition,
        churn_definition=args.churn_definition,
    )

    feature_path = build_feature_table(config)
    metrics_frame, best_test_metrics = train_and_evaluate(feature_path, config)
    if args.generate_eda:
        from src.eda import generate_eda

        generate_eda(config, feature_path)

    print("[feature_table]", feature_path)
    print("[metrics]")
    print(metrics_frame.to_string(index=False))
    print("[best_model_test]")
    print(best_test_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
