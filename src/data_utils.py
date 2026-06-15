from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .utils import to_timestamp


EVENT_COLUMNS: Dict[str, list[str]] = {
    "product_buy": ["client_id", "timestamp", "sku"],
    "add_to_cart": ["client_id", "timestamp", "sku"],
    "remove_from_cart": ["client_id", "timestamp", "sku"],
    "page_visit": ["client_id", "timestamp", "url"],
    "search_query": ["client_id", "timestamp", "query"],
}

PRODUCT_COLUMNS = ["sku", "category", "price", "embedding"]


def find_parquet_file(dataset_root: Path, stem: str) -> Path:
    matches = list(dataset_root.rglob(f"{stem}.parquet"))
    if not matches:
        raise FileNotFoundError(f"Could not find {stem}.parquet under {dataset_root}")
    matches.sort()
    return matches[0]


def load_event_table(
    dataset_root: Path,
    event_name: str,
    sample_frac: float | None = None,
) -> pd.DataFrame:
    path = find_parquet_file(dataset_root, event_name)
    columns = EVENT_COLUMNS[event_name]
    frame = pd.read_parquet(path, columns=columns)
    frame["timestamp"] = to_timestamp(frame["timestamp"])
    frame = frame.dropna(subset=["client_id", "timestamp"]).copy()
    frame["client_id"] = frame["client_id"].astype("int64")

    if "sku" in frame.columns:
        frame = frame.dropna(subset=["sku"]).copy()
        frame["sku"] = frame["sku"].astype("int64")
    if "url" in frame.columns:
        frame["url"] = frame["url"].fillna(-1).astype("int64")

    if sample_frac is not None and 0 < sample_frac < 1:
        frame = frame.sample(frac=sample_frac, random_state=42)

    return frame.sort_values(["client_id", "timestamp"]).reset_index(drop=True)


def load_product_properties(dataset_root: Path) -> pd.DataFrame:
    path = find_parquet_file(dataset_root, "product_properties")
    full_frame = pd.read_parquet(path)
    columns = [column for column in PRODUCT_COLUMNS if column in full_frame.columns]
    frame = full_frame[columns].copy()
    if "sku" not in frame.columns:
        raise ValueError("product_properties.parquet must contain sku")
    frame = frame.drop_duplicates(subset=["sku"]).copy()
    frame["sku"] = frame["sku"].astype("int64")
    for column in ("category", "price"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_all_event_tables(dataset_root: Path, sample_frac: float | None = None) -> dict[str, pd.DataFrame]:
    return {
        event_name: load_event_table(dataset_root, event_name, sample_frac=sample_frac)
        for event_name in EVENT_COLUMNS
    }
