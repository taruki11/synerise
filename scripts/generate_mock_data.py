from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _random_timestamps(rng: np.random.Generator, start: pd.Timestamp, end: pd.Timestamp, size: int) -> pd.Series:
    seconds = int((end - start).total_seconds())
    offsets = rng.integers(0, seconds, size=size)
    return pd.to_datetime(start + pd.to_timedelta(offsets, unit="s"))


def build_mock_dataset(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    clients = np.arange(1, 601)
    skus = np.arange(1000, 1120)
    urls = np.arange(2000, 2080)
    start = pd.Timestamp("2025-01-01")
    end = pd.Timestamp("2025-07-01")

    product_properties = pd.DataFrame(
        {
            "sku": skus,
            "category": rng.integers(1, 18, size=len(skus)),
            "price": rng.integers(1, 30, size=len(skus)),
            "embedding": [rng.integers(-8, 8, size=20).tolist() for _ in skus],
        }
    )
    product_properties.to_parquet(output_dir / "product_properties.parquet", index=False)

    event_specs = {
        "page_visit": {"rows": 18000, "value_column": "url", "values": urls},
        "add_to_cart": {"rows": 9000, "value_column": "sku", "values": skus},
        "remove_from_cart": {"rows": 2500, "value_column": "sku", "values": skus},
        "product_buy": {"rows": 6500, "value_column": "sku", "values": skus},
        "search_query": {"rows": 7000, "value_column": "query", "values": None},
    }

    for event_name, spec in event_specs.items():
        frame = pd.DataFrame(
            {
                "client_id": rng.choice(clients, size=spec["rows"], replace=True),
                "timestamp": _random_timestamps(rng, start, end, spec["rows"]),
            }
        )
        if spec["value_column"] == "query":
            frame["query"] = [rng.integers(-8, 8, size=20).tolist() for _ in range(spec["rows"])]
        else:
            frame[spec["value_column"]] = rng.choice(spec["values"], size=spec["rows"], replace=True)

        if event_name == "product_buy":
            high_value_clients = rng.choice(clients, size=80, replace=False)
            extra_rows = pd.DataFrame(
                {
                    "client_id": rng.choice(high_value_clients, size=1200, replace=True),
                    "timestamp": _random_timestamps(rng, pd.Timestamp("2025-04-15"), end, 1200),
                    "sku": rng.choice(skus[:40], size=1200, replace=True),
                }
            )
            frame = pd.concat([frame, extra_rows], ignore_index=True)

        frame = frame.sort_values(["client_id", "timestamp"]).reset_index(drop=True)
        frame.to_parquet(output_dir / f"{event_name}.parquet", index=False)

    print(f"[mock dataset ready] {output_dir}")


def main() -> None:
    build_mock_dataset(Path("data/sample/mock_synerise_dataset"))


if __name__ == "__main__":
    main()
