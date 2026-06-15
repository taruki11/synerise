from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score


def compute_binary_metrics(
    y_true: pd.Series,
    y_score: np.ndarray,
    threshold: float = 0.5,
    top_k_pct: float = 0.1,
) -> dict[str, float]:
    y_pred = (y_score >= threshold).astype(int)
    top_k = max(1, int(len(y_score) * top_k_pct))
    ranking = np.argsort(-y_score)
    top_k_mask = np.zeros(len(y_score), dtype=int)
    top_k_mask[ranking[:top_k]] = 1
    positives = max(int(y_true.sum()), 1)

    return {
        "auc": float(roc_auc_score(y_true, y_score)) if y_true.nunique() > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, y_score)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "top_10pct_churn_recall": float(((top_k_mask == 1) & (y_true == 1)).sum() / positives),
        "positive_rate": float(y_true.mean()),
    }


def extract_feature_importance(estimator, feature_names: list[str]) -> pd.DataFrame:
    model = estimator.named_steps["model"] if hasattr(estimator, "named_steps") else estimator
    if hasattr(model, "feature_importances_"):
        importance = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        importance = np.abs(np.asarray(model.coef_).reshape(-1))
    else:
        importance = np.zeros(len(feature_names), dtype=float)
    frame = pd.DataFrame({"feature": feature_names, "importance": importance})
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)


def save_feature_importance(estimator, feature_names: list[str], output_path: Path, top_n: int = 50) -> None:
    frame = extract_feature_importance(estimator, feature_names).head(top_n)
    frame.to_csv(output_path, index=False)


def build_prediction_frame(
    client_ids: pd.Series,
    snapshot_dates: pd.Series,
    y_true: pd.Series,
    y_score: np.ndarray,
) -> pd.DataFrame:
    prediction_frame = pd.DataFrame(
        {
            "client_id": client_ids.to_numpy(),
            "snapshot_date": pd.to_datetime(snapshot_dates).to_numpy(),
            "y_true": y_true.to_numpy(),
            "y_score": y_score,
        }
    )
    prediction_frame["y_pred"] = (prediction_frame["y_score"] >= 0.5).astype(int)
    prediction_frame["error_type"] = np.select(
        [
            (prediction_frame["y_true"] == 1) & (prediction_frame["y_pred"] == 0),
            (prediction_frame["y_true"] == 0) & (prediction_frame["y_pred"] == 1),
        ],
        ["false_negative", "false_positive"],
        default="correct",
    )
    return prediction_frame


def run_error_analysis(
    prediction_frame: pd.DataFrame,
    feature_frame: pd.DataFrame,
    output_prefix: str,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    merged = prediction_frame.merge(feature_frame, on=["client_id", "snapshot_date"], how="left")
    recent_buy_col = "product_buy_count_30d" if "product_buy_count_30d" in merged.columns else None
    if recent_buy_col is not None and merged[recent_buy_col].nunique() > 1:
        quantiles = pd.qcut(merged[recent_buy_col].rank(method="first"), q=min(4, merged[recent_buy_col].nunique()), labels=False, duplicates="drop")
        label_map = {0: "low", 1: "mid_low", 2: "mid_high", 3: "high"}
        merged["value_segment"] = quantiles.map(label_map).fillna("unknown")
    else:
        merged["value_segment"] = "unknown"

    aggregations = {
        "users": ("client_id", "size"),
        "avg_score": ("y_score", "mean"),
    }
    if recent_buy_col is not None:
        aggregations["avg_buy_count_30d"] = (recent_buy_col, "mean")
    if "active_days_30d" in merged.columns:
        aggregations["avg_active_days_30d"] = ("active_days_30d", "mean")

    error_profile = merged.groupby(["error_type", "value_segment"], dropna=False).agg(**aggregations).reset_index()
    error_profile.to_csv(output_dir / f"{output_prefix}_error_profile.csv", index=False)

    numeric_columns = merged.select_dtypes(include=[np.number]).columns.tolist()
    numeric_columns = [column for column in numeric_columns if column not in {"client_id", "y_true", "y_pred"}]
    for error_type in ("false_positive", "false_negative"):
        subset = merged.loc[merged["error_type"] == error_type]
        examples = subset.sort_values("y_score", ascending=False).head(200)
        examples.to_csv(output_dir / f"{output_prefix}_{error_type}_examples.csv", index=False)
        if not subset.empty and numeric_columns:
            profile = subset[numeric_columns].mean().sort_values(ascending=False).reset_index()
            profile.columns = ["feature", "mean_value"]
            profile.to_csv(output_dir / f"{output_prefix}_{error_type}_feature_means.csv", index=False)
