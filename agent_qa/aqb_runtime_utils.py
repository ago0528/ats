from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Dict

import pandas as pd


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "results") -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return bio.getvalue()


def dataframes_to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """
    여러 DataFrame을 하나의 Excel 파일(다중 시트)로 직렬화한다.
    시트명은 Excel 제약(31자/특수문자)을 고려해 안전하게 보정한다.
    """
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

            if df is None:
                pd.DataFrame().to_excel(writer, index=False, sheet_name=name)
            else:
                df.to_excel(writer, index=False, sheet_name=name)
    return bio.getvalue()
