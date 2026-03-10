"""CSV delta engine for the FPGA I/O Pin-Swap Bridge.

Compares a baseline pinout CSV (from Xpedition) against a new pinout CSV
(from Vivado) and returns only the signals whose pin or bank has changed.

Expected CSV schema (minimum required columns):
    Signal_Name, Pin, Bank
"""
import io
from typing import List

import pandas as pd

REQUIRED_COLUMNS = {"Signal_Name", "Pin", "Bank"}


def _load_csv(data: bytes, label: str) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame and validate required columns."""
    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Could not parse {label} CSV: {exc}") from exc

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"{label} CSV is missing required columns: {sorted(missing)}. "
            f"Expected at minimum: Signal_Name, Pin, Bank."
        )

    # Normalise the key column so leading/trailing whitespace doesn't break the join
    df["Signal_Name"] = df["Signal_Name"].astype(str).str.strip()
    df["Pin"] = df["Pin"].astype(str).str.strip()
    df["Bank"] = df["Bank"].astype(str).str.strip()
    return df


def compute_pin_delta(baseline_bytes: bytes, new_bytes: bytes) -> List[dict]:
    """Compare two pinout CSVs and return only the pins that changed location.

    Args:
        baseline_bytes: Raw bytes of the baseline (Xpedition schematic) CSV.
        new_bytes:      Raw bytes of the updated (Vivado export) CSV.

    Returns:
        List of dicts, one per changed signal, with keys:
        Signal_Name, Old_Pin, New_Pin, Old_Bank, New_Bank, AI_Risk_Assessment.

    Raises:
        ValueError: If either file cannot be parsed or is missing required columns.
    """
    baseline_df = _load_csv(baseline_bytes, "Baseline")
    new_df = _load_csv(new_bytes, "New Vivado")

    # Inner join — only compare signals present in both files
    merged = baseline_df.merge(
        new_df,
        on="Signal_Name",
        suffixes=("_old", "_new"),
    )

    # Keep only rows where pin or bank changed
    changed = merged[
        (merged["Pin_old"] != merged["Pin_new"])
        | (merged["Bank_old"] != merged["Bank_new"])
    ]

    return [
        {
            "Signal_Name": row["Signal_Name"],
            "Old_Pin": row["Pin_old"],
            "New_Pin": row["Pin_new"],
            "Old_Bank": row["Bank_old"],
            "New_Bank": row["Bank_new"],
            "AI_Risk_Assessment": None,
        }
        for _, row in changed.iterrows()
    ]
