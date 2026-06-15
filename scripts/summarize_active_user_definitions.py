from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def summarize_prefix(reports_dir: Path, prefix: str) -> dict[str, object]:
    metadata = pd.read_json(reports_dir / f"{prefix}_feature_metadata.json", typ="series")
    metrics = pd.read_csv(reports_dir / f"{prefix}_metrics.csv")
    best_test = pd.read_csv(reports_dir / f"{prefix}_best_model_test_metrics.csv").iloc[0]
    valid = metrics.loc[metrics["split"] == "valid"].sort_values(["pr_auc", "auc", "f1"], ascending=[False, False, False]).iloc[0]
    return {
        "prefix": prefix,
        "active_user_definition": metadata.get("active_user_definition"),
        "active_user_definition_detail": metadata.get("active_user_definition_detail"),
        "churn_definition": metadata.get("churn_definition"),
        "churn_definition_detail": metadata.get("churn_definition_detail"),
        "row_count": int(metadata.get("row_count", 0)),
        "feature_count": int(metadata.get("feature_count", 0)),
        "snapshot_count": int(metadata.get("snapshot_count", 0)),
        "best_valid_model": valid["model"],
        "valid_auc": valid["auc"],
        "valid_pr_auc": valid["pr_auc"],
        "valid_f1": valid["f1"],
        "test_refit_model": best_test["model"],
        "test_refit_auc": best_test["auc"],
        "test_refit_pr_auc": best_test["pr_auc"],
        "test_refit_f1": best_test["f1"],
        "test_positive_rate": best_test["positive_rate"],
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize active-user-definition experiments.")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--prefixes", nargs="+", required=True)
    parser.add_argument("--output-name", type=str, default="active_user_definition_comparison.csv")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    rows = [summarize_prefix(args.reports_dir, prefix) for prefix in args.prefixes]
    frame = pd.DataFrame(rows)
    output_path = args.reports_dir / args.output_name
    frame.to_csv(output_path, index=False)
    print(output_path)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
