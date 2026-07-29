"""Load restaurant data from India-wide, metro, and Bangalore sources."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from datasets import load_dataset

from src.phase1_data.config import (
    DATASET_NAME,
    DATASET_SPLIT,
    LOAD_MAX_RETRIES,
    LOAD_RETRY_BASE_DELAY_SEC,
    REQUIRED_COLUMNS,
)
from src.phase1_data.exceptions import DatasetEmptyError, DatasetLoadError, DatasetSchemaError
from src.phase1_data.india_loader import load_india_rows
from src.phase1_data.metro_loader import load_metro_rows

logger = logging.getLogger(__name__)


def _validate_schema(column_names: list[str]) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in column_names]
    if missing:
        raise DatasetSchemaError(
            f"Dataset schema mismatch. Missing required columns: {', '.join(missing)}"
        )


def _load_hf_rows(
    *,
    max_rows: Optional[int] = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    last_error: Optional[Exception] = None

    for attempt in range(1, LOAD_MAX_RETRIES + 1):
        try:
            logger.info(
                "Loading Bangalore dataset %s (attempt %d/%d)",
                DATASET_NAME,
                attempt,
                LOAD_MAX_RETRIES,
            )
            load_kwargs: dict = {}
            if not use_cache:
                load_kwargs["download_mode"] = "force_redownload"

            dataset = load_dataset(
                DATASET_NAME,
                split=DATASET_SPLIT,
                **load_kwargs,
            )
            _validate_schema(dataset.column_names)

            if len(dataset) == 0:
                raise DatasetEmptyError("Bangalore dataset contains zero rows.")

            if max_rows is not None:
                dataset = dataset.select(range(min(max_rows, len(dataset))))

            rows = [dict(row) for row in dataset]
            logger.info("Loaded %d Bangalore HF rows", len(rows))
            return rows

        except (DatasetSchemaError, DatasetEmptyError):
            raise
        except Exception as exc:
            last_error = exc
            logger.warning("Bangalore dataset load attempt %d failed: %s", attempt, exc)
            if attempt < LOAD_MAX_RETRIES:
                delay = LOAD_RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1))
                time.sleep(delay)

    logger.warning(
        "Unable to load Bangalore HF dataset after retries: %s",
        last_error,
    )
    return []


def load_raw_rows(
    *,
    max_rows: Optional[int] = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Load restaurants for cities across India.

    Sources (merged + deduped later):
    1. India-wide Swiggy listings (primary — hundreds of cities)
    2. Multi-city Zomato metro CSV (Delhi, Mumbai, etc.)
    3. Bangalore Zomato HF dataset (richer Bangalore coverage)
    """
    india_cap = max_rows
    india_rows = load_india_rows(max_rows=india_cap)

    metro_rows = load_metro_rows(max_restaurants=None)

    # Keep Bangalore HF as a supplement; cap it when demo mode is on
    hf_cap = max_rows if max_rows is not None else None
    try:
        hf_rows = _load_hf_rows(max_rows=hf_cap, use_cache=use_cache)
    except (DatasetSchemaError, DatasetEmptyError) as exc:
        logger.warning("Skipping Bangalore HF source: %s", exc)
        hf_rows = []

    combined = india_rows + metro_rows + hf_rows
    if not combined:
        raise DatasetEmptyError(
            "No restaurant rows loaded from any source. Check network access."
        )

    logger.info(
        "Combined dataset: %d India + %d metro + %d Bangalore HF = %d total raw rows",
        len(india_rows),
        len(metro_rows),
        len(hf_rows),
        len(combined),
    )
    return combined
