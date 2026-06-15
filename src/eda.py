from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.parquet as pq
import seaborn as sns

from .config import PipelineConfig


sns.set_theme(style="whitegrid")


def _event_row_counts(dataset_root: Path) -> pd.Series:
    counts = {}
    for event_name in ["product_buy", "add_to_cart", "remove_from_cart", "page_visit", "search_query"]:
        path = dataset_root / f"{event_name}.parquet"
        counts[event_name] = pq.ParquetFile(path).metadata.num_rows
    return pd.Series(counts).sort_values(ascending=False)


def generate_eda(config: PipelineConfig, feature_path: Path) -> None:
    config.ensure_directories()
    feature_table = pd.read_parquet(feature_path)
    feature_table["snapshot_date"] = pd.to_datetime(feature_table["snapshot_date"])
    event_counts = _event_row_counts(config.dataset_root)

    plt.figure(figsize=(8, 5))
    sns.barplot(x=event_counts.index, y=event_counts.values, hue=event_counts.index, palette="crest", legend=False)
    plt.xticks(rotation=20)
    plt.title("Event Type Distribution")
    plt.ylabel("Rows")
    plt.tight_layout()
    plt.savefig(config.figures_dir / f"{config.output_prefix}_event_type_share.png", dpi=180)
    plt.close()

    if "active_days_30d" in feature_table.columns:
        plt.figure(figsize=(8, 5))
        sns.histplot(feature_table["active_days_30d"], bins=30, kde=True, color="#1f77b4")
        plt.title("User Active Days Distribution (30d)")
        plt.tight_layout()
        plt.savefig(config.figures_dir / f"{config.output_prefix}_user_active_distribution.png", dpi=180)
        plt.close()

    if "product_buy_count_30d" in feature_table.columns:
        plt.figure(figsize=(8, 5))
        sns.histplot(feature_table["product_buy_count_30d"], bins=30, kde=True, color="#2ca02c")
        plt.title("Purchase Frequency Distribution (30d)")
        plt.tight_layout()
        plt.savefig(config.figures_dir / f"{config.output_prefix}_purchase_frequency_distribution.png", dpi=180)
        plt.close()

    plt.figure(figsize=(6, 4))
    sns.countplot(x="churn", data=feature_table, hue="churn", palette="mako", legend=False)
    plt.title("Churn Label Distribution")
    plt.tight_layout()
    plt.savefig(config.figures_dir / f"{config.output_prefix}_churn_label_distribution.png", dpi=180)
    plt.close()
