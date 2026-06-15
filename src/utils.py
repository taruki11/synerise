from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    return numerator.divide(denominator).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def to_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=False)


def ensure_datetime_floor_day(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.floor("D")


def vector_to_array(value: object) -> np.ndarray:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.array([], dtype=float)
    if isinstance(value, np.ndarray):
        return value.astype(float)
    if isinstance(value, (list, tuple)):
        return np.asarray(value, dtype=float)
    text = str(value).strip()
    if not text:
        return np.array([], dtype=float)
    try:
        return np.asarray(json.loads(text), dtype=float)
    except json.JSONDecodeError:
        cleaned = text.replace("[", "").replace("]", "").replace(",", " ")
        parts = [piece for piece in cleaned.split() if piece]
        if not parts:
            return np.array([], dtype=float)
        return np.asarray(parts, dtype=float)


def write_json(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def flatten_columns(columns: Iterable[str]) -> list[str]:
    return [str(column) for column in columns]
