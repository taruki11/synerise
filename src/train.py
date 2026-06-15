from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

from .config import PipelineConfig
from .evaluate import build_prediction_frame, compute_binary_metrics, run_error_analysis, save_feature_importance


DROP_COLUMNS = {"client_id", "snapshot_date", "split", "churn", "future_buy_count_14d", "future_active_days_14d"}



MODEL_TRAIN_ROW_CAPS = {
    "logistic_regression": 1200000,
    "random_forest": 300000,
    "xgboost": 1200000,
    "lightgbm": 1500000,
}


def _cap_training_rows(X: pd.DataFrame, y: pd.Series, model_name: str, random_state: int) -> tuple[pd.DataFrame, pd.Series]:
    cap = MODEL_TRAIN_ROW_CAPS.get(model_name)
    if cap is None or len(X) <= cap:
        return X, y

    target = y.astype(int).copy()
    class_counts = target.value_counts(dropna=False).sort_index()
    sampled_indices = []
    remaining = cap

    for target_value, class_count in class_counts.items():
        if remaining <= 0:
            break
        target_index = target.index[target == target_value]
        target_quota = int(round(cap * class_count / len(target)))
        target_quota = max(1, target_quota)
        target_quota = min(target_quota, len(target_index), remaining)
        sampled_indices.extend(
            target.loc[target_index].sample(n=target_quota, random_state=random_state).index.tolist()
        )
        remaining -= target_quota

    if remaining > 0:
        unused_index = target.index.difference(sampled_indices)
        if len(unused_index) > 0:
            fill_index = target.loc[unused_index].sample(
                n=min(remaining, len(unused_index)),
                random_state=random_state,
            ).index.tolist()
            sampled_indices.extend(fill_index)

    sampled_indices = list(dict.fromkeys(sampled_indices))
    if len(sampled_indices) > cap:
        sampled_indices = (
            target.loc[sampled_indices]
            .sample(n=cap, random_state=random_state)
            .index.tolist()
        )

    X_sampled = X.loc[sampled_indices].reset_index(drop=True)
    y_sampled = target.loc[sampled_indices].reset_index(drop=True)
    return X_sampled, y_sampled

def load_feature_table(feature_path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(feature_path)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"])
    return frame


def build_model_registry(random_state: int = 42) -> dict[str, Pipeline]:
    registry = {
        "logistic_regression": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000, solver="liblinear", class_weight="balanced")),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=12,
                        min_samples_leaf=10,
                        class_weight="balanced_subsample",
                        random_state=random_state,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "lightgbm": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
                (
                    "model",
                    LGBMClassifier(
                        objective="binary",
                        n_estimators=400,
                        learning_rate=0.05,
                        num_leaves=63,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        class_weight="balanced",
                        random_state=random_state,
                        verbosity=-1,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }

    if XGBClassifier is not None:
        registry["xgboost"] = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
                (
                    "model",
                    XGBClassifier(
                        objective="binary:logistic",
                        eval_metric="logloss",
                        n_estimators=400,
                        learning_rate=0.05,
                        max_depth=6,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        reg_lambda=1.0,
                        random_state=random_state,
                        n_jobs=1,
                    ),
                ),
            ]
        )

    return registry


def _prepare_xy(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    feature_columns = [column for column in frame.columns if column not in DROP_COLUMNS]
    numeric_frame = frame[feature_columns].copy()
    numeric_frame = numeric_frame.select_dtypes(include=["number", "bool"])
    feature_columns = numeric_frame.columns.tolist()
    y = frame["churn"].astype(int)
    return numeric_frame, y, feature_columns


def train_and_evaluate(feature_path: Path, config: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    config.ensure_directories()
    feature_table = load_feature_table(feature_path)

    train_frame = feature_table.loc[feature_table["split"] == "train"].copy()
    valid_frame = feature_table.loc[feature_table["split"] == "valid"].copy()
    test_frame = feature_table.loc[feature_table["split"] == "test"].copy()

    X_train, y_train, feature_names = _prepare_xy(train_frame)
    X_valid, y_valid, _ = _prepare_xy(valid_frame)
    X_test, y_test, _ = _prepare_xy(test_frame)

    metrics_rows = []
    model_registry = build_model_registry(random_state=config.random_state)
    best_model_name = None
    best_valid_pr_auc = float("-inf")

    for model_name, estimator in model_registry.items():
        X_fit, y_fit = _cap_training_rows(X_train, y_train, model_name, config.random_state)
        estimator.fit(X_fit, y_fit)
        joblib.dump(estimator, config.models_dir / f"{config.output_prefix}_{model_name}.joblib")

        for split_name, X_split, y_split, frame in (
            ("valid", X_valid, y_valid, valid_frame),
            ("test", X_test, y_test, test_frame),
        ):
            scores = estimator.predict_proba(X_split)[:, 1]
            metrics = compute_binary_metrics(y_split, scores)
            metrics_rows.append({"model": model_name, "split": split_name, **metrics})

            prediction_frame = build_prediction_frame(
                client_ids=frame["client_id"],
                snapshot_dates=frame["snapshot_date"],
                y_true=y_split,
                y_score=scores,
            )
            prediction_frame.to_csv(
                config.reports_dir / f"{config.output_prefix}_{model_name}_{split_name}_predictions.csv",
                index=False,
            )

            if split_name == "test":
                run_error_analysis(
                    prediction_frame=prediction_frame,
                    feature_frame=frame[["client_id", "snapshot_date"] + feature_names].copy(),
                    output_prefix=f"{config.output_prefix}_{model_name}_{split_name}",
                    output_dir=config.reports_dir,
                )

            if split_name == "valid" and metrics["pr_auc"] > best_valid_pr_auc:
                best_valid_pr_auc = metrics["pr_auc"]
                best_model_name = model_name

        save_feature_importance(
            estimator,
            feature_names,
            config.reports_dir / f"{config.output_prefix}_feature_importance_{model_name}.csv",
        )

    metrics_frame = pd.DataFrame(metrics_rows).sort_values(["split", "pr_auc", "auc"], ascending=[True, False, False])
    metrics_frame.to_csv(config.reports_dir / f"{config.output_prefix}_metrics.csv", index=False)

    if best_model_name is None:
        raise ValueError("Could not determine best model from validation split.")

    best_estimator = build_model_registry(random_state=config.random_state)[best_model_name]
    train_valid_frame = pd.concat([train_frame, valid_frame], ignore_index=True)
    X_train_valid, y_train_valid, feature_names = _prepare_xy(train_valid_frame)
    X_refit, y_refit = _cap_training_rows(X_train_valid, y_train_valid, best_model_name, config.random_state)
    best_estimator.fit(X_refit, y_refit)
    joblib.dump(best_estimator, config.models_dir / f"{config.output_prefix}_{best_model_name}_refit.joblib")

    best_test_scores = best_estimator.predict_proba(X_test)[:, 1]
    best_test_metrics = pd.DataFrame(
        [{"model": best_model_name, "split": "test_refit", **compute_binary_metrics(y_test, best_test_scores)}]
    )
    best_test_metrics.to_csv(config.reports_dir / f"{config.output_prefix}_best_model_test_metrics.csv", index=False)
    save_feature_importance(
        best_estimator,
        feature_names,
        config.reports_dir / f"{config.output_prefix}_feature_importance_{best_model_name}_refit.csv",
    )

    return metrics_frame, best_test_metrics
