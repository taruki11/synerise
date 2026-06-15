from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import PipelineConfig
from .evaluate import compute_binary_metrics
from .train import _cap_training_rows, _prepare_xy, build_model_registry, load_feature_table


def _sorted_snapshot_dates(feature_table: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(pd.to_datetime(feature_table["snapshot_date"]).unique())


def _build_rolling_folds(snapshot_dates: list[pd.Timestamp], min_train_snapshots: int) -> list[dict[str, object]]:
    if len(snapshot_dates) < min_train_snapshots + 2:
        raise ValueError("Need at least min_train_snapshots + 2 snapshot dates for rolling backtest.")

    folds = []
    for test_idx in range(min_train_snapshots + 1, len(snapshot_dates)):
        train_dates = snapshot_dates[: test_idx - 1]
        valid_date = snapshot_dates[test_idx - 1]
        test_date = snapshot_dates[test_idx]
        folds.append(
            {
                "fold_id": len(folds) + 1,
                "train_dates": train_dates,
                "valid_date": valid_date,
                "test_date": test_date,
            }
        )
    return folds


def run_rolling_backtest(
    feature_path: Path,
    config: PipelineConfig,
    model_name: str | None = None,
    min_train_snapshots: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config.ensure_directories()
    feature_table = load_feature_table(feature_path)
    snapshot_dates = _sorted_snapshot_dates(feature_table)
    folds = _build_rolling_folds(snapshot_dates, min_train_snapshots=min_train_snapshots)

    model_registry = build_model_registry(random_state=config.random_state)
    model_names = [model_name] if model_name is not None else list(model_registry.keys())
    missing = [name for name in model_names if name not in model_registry]
    if missing:
        raise ValueError(f"Unsupported model(s) for rolling backtest: {missing}")

    rows: list[dict[str, object]] = []
    for fold in folds:
        train_frame = feature_table.loc[feature_table["snapshot_date"].isin(fold["train_dates"])].copy()
        valid_frame = feature_table.loc[feature_table["snapshot_date"] == fold["valid_date"]].copy()
        test_frame = feature_table.loc[feature_table["snapshot_date"] == fold["test_date"]].copy()

        X_train, y_train, _ = _prepare_xy(train_frame)
        X_valid, y_valid, _ = _prepare_xy(valid_frame)
        X_test, y_test, _ = _prepare_xy(test_frame)

        for current_model in model_names:
            estimator = build_model_registry(random_state=config.random_state)[current_model]
            X_fit, y_fit = _cap_training_rows(X_train, y_train, current_model, config.random_state)
            estimator.fit(X_fit, y_fit)

            for split_name, X_split, y_split, frame in (
                ("valid", X_valid, y_valid, valid_frame),
                ("test", X_test, y_test, test_frame),
            ):
                scores = estimator.predict_proba(X_split)[:, 1]
                metrics = compute_binary_metrics(y_split, scores)
                rows.append(
                    {
                        "fold_id": fold["fold_id"],
                        "model": current_model,
                        "split": split_name,
                        "train_snapshot_count": len(fold["train_dates"]),
                        "train_rows": len(train_frame),
                        "valid_rows": len(valid_frame),
                        "test_rows": len(test_frame),
                        "valid_snapshot_date": pd.Timestamp(fold["valid_date"]).date().isoformat(),
                        "test_snapshot_date": pd.Timestamp(fold["test_date"]).date().isoformat(),
                        "snapshot_date": pd.Timestamp(frame["snapshot_date"].iloc[0]).date().isoformat(),
                        **metrics,
                    }
                )

    results = pd.DataFrame(rows).sort_values(["model", "fold_id", "split"]).reset_index(drop=True)
    suffix = model_name if model_name is not None else "all_models"
    results_path = config.reports_dir / f"{config.output_prefix}_{suffix}_rolling_backtest.csv"
    results.to_csv(results_path, index=False)

    summary = (
        results.groupby(["model", "split"], dropna=False)
        .agg(
            folds=("fold_id", "nunique"),
            auc_mean=("auc", "mean"),
            auc_std=("auc", "std"),
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_std=("pr_auc", "std"),
            f1_mean=("f1", "mean"),
            f1_std=("f1", "std"),
            top_10pct_churn_recall_mean=("top_10pct_churn_recall", "mean"),
            positive_rate_mean=("positive_rate", "mean"),
        )
        .reset_index()
        .sort_values(["split", "pr_auc_mean", "auc_mean"], ascending=[True, False, False])
    )
    summary_path = config.reports_dir / f"{config.output_prefix}_{suffix}_rolling_backtest_summary.csv"
    summary.to_csv(summary_path, index=False)

    return results, summary
