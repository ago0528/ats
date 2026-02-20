from __future__ import annotations

from io import BytesIO
from typing import Dict

import pandas as pd


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "results") -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return bio.getvalue()


def dataframes_to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        used = set()
        for raw_name, df in sheets.items():
            name = str(raw_name or "sheet").strip() or "sheet"
            for ch in ('\\', '/', '*', '?', ':', '[', ']'):
                name = name.replace(ch, "_")
            name = name[:31] or "sheet"

            base = name
            seq = 1
            while name in used:
                suffix = f"_{seq}"
                name = f"{base[: max(0, 31 - len(suffix))]}{suffix}" or f"sheet_{seq}"
                seq += 1
            used.add(name)

            (df if df is not None else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name)
    return bio.getvalue()

