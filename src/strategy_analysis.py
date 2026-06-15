from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .evaluate import compute_binary_metrics


DEFAULT_TOP_K_PCTS = [0.01, 0.02, 0.05, 0.10, 0.20]


def choose_best_model(metrics_frame: pd.DataFrame) -> str:
    valid_rows = metrics_frame.loc[metrics_frame["split"] == "valid"].copy()
    valid_rows = valid_rows.sort_values(["pr_auc", "auc", "f1"], ascending=[False, False, False])
    return str(valid_rows.iloc[0]["model"])



def build_threshold_candidates(y_score: np.ndarray) -> np.ndarray:
    fixed = np.arange(0.05, 0.96, 0.05)
    quantiles = np.quantile(y_score, [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 0.99])
    thresholds = np.unique(np.round(np.concatenate([fixed, quantiles]), 4))
    thresholds = thresholds[(thresholds > 0) & (thresholds < 1)]
    return thresholds



def threshold_sweep(prediction_frame: pd.DataFrame, thresholds: np.ndarray | None = None) -> pd.DataFrame:
    y_true = prediction_frame["y_true"].astype(int)
    y_score = prediction_frame["y_score"].to_numpy()
    thresholds = build_threshold_candidates(y_score) if thresholds is None else thresholds

    rows = []
    for threshold in thresholds:
        metrics = compute_binary_metrics(y_true, y_score, threshold=float(threshold))
        targeted = int((y_score >= threshold).sum())
        targeted_share = float(targeted / max(len(y_score), 1))
        rows.append(
            {
                "threshold": float(threshold),
                "targeted_users": targeted,
                "targeted_share": targeted_share,
                **metrics,
            }
        )
    return pd.DataFrame(rows).sort_values("threshold").reset_index(drop=True)



def pick_best_threshold(valid_thresholds: pd.DataFrame, optimize_for: str = "f1") -> float:
    ranked = valid_thresholds.sort_values([optimize_for, "recall", "precision", "threshold"], ascending=[False, False, False, False])
    return float(ranked.iloc[0]["threshold"])



def top_k_strategy(prediction_frame: pd.DataFrame, top_k_pcts: list[float] | None = None) -> pd.DataFrame:
    top_k_pcts = DEFAULT_TOP_K_PCTS if top_k_pcts is None else top_k_pcts
    scored = prediction_frame.sort_values("y_score", ascending=False).reset_index(drop=True)
    total = len(scored)
    total_positives = max(int(scored["y_true"].sum()), 1)
    baseline = float(scored["y_true"].mean())

    rows = []
    for pct in top_k_pcts:
        top_n = max(1, int(total * pct))
        bucket = scored.head(top_n)
        captured = int(bucket["y_true"].sum())
        precision = float(bucket["y_true"].mean())
        recall = float(captured / total_positives)
        lift = float(precision / baseline) if baseline > 0 else np.nan
        rows.append(
            {
                "top_k_pct": pct,
                "targeted_users": top_n,
                "captured_churn_users": captured,
                "churn_precision": precision,
                "churn_recall": recall,
                "lift_vs_base": lift,
                "avg_score": float(bucket["y_score"].mean()),
                "baseline_churn_rate": baseline,
            }
        )
    return pd.DataFrame(rows)



def run_strategy_analysis(
    reports_dir: Path,
    output_prefix: str,
    model_name: str | None = None,
) -> dict[str, object]:
    reports_dir = Path(reports_dir)
    metrics_path = reports_dir / f"{output_prefix}_metrics.csv"
    metrics_frame = pd.read_csv(metrics_path)
    model_name = choose_best_model(metrics_frame) if model_name is None else model_name

    valid_predictions = pd.read_csv(reports_dir / f"{output_prefix}_{model_name}_valid_predictions.csv")
    test_predictions = pd.read_csv(reports_dir / f"{output_prefix}_{model_name}_test_predictions.csv")

    valid_thresholds = threshold_sweep(valid_predictions)
    test_thresholds = threshold_sweep(test_predictions, thresholds=valid_thresholds["threshold"].to_numpy())
    best_threshold = pick_best_threshold(valid_thresholds, optimize_for="f1")

    valid_thresholds.to_csv(reports_dir / f"{output_prefix}_{model_name}_valid_threshold_sweep.csv", index=False)
    test_thresholds.to_csv(reports_dir / f"{output_prefix}_{model_name}_test_threshold_sweep.csv", index=False)

    baseline_row = test_thresholds.loc[np.isclose(test_thresholds["threshold"], 0.5)].copy()
    threshold_row = test_thresholds.loc[np.isclose(test_thresholds["threshold"], best_threshold)].copy()
    threshold_summary = pd.concat(
        [
            baseline_row.assign(strategy="threshold_0.50"),
            threshold_row.assign(strategy="threshold_f1_opt"),
        ],
        ignore_index=True,
    )
    threshold_summary.to_csv(reports_dir / f"{output_prefix}_{model_name}_threshold_strategy_summary.csv", index=False)

    valid_topk = top_k_strategy(valid_predictions)
    test_topk = top_k_strategy(test_predictions)
    valid_topk.to_csv(reports_dir / f"{output_prefix}_{model_name}_valid_topk_strategy.csv", index=False)
    test_topk.to_csv(reports_dir / f"{output_prefix}_{model_name}_test_topk_strategy.csv", index=False)

    summary = {
        "model": model_name,
        "best_threshold_by_f1": best_threshold,
        "baseline_threshold": 0.5,
        "test_threshold_summary_path": str(reports_dir / f"{output_prefix}_{model_name}_threshold_strategy_summary.csv"),
        "test_topk_path": str(reports_dir / f"{output_prefix}_{model_name}_test_topk_strategy.csv"),
    }
    pd.DataFrame([summary]).to_csv(reports_dir / f"{output_prefix}_{model_name}_strategy_analysis_summary.csv", index=False)
    return summary
