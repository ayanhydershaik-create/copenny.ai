import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from app.tools.distributed_processor import ParallelStreamProcessor

try:
    import duckdb  # type: ignore
    _HAS_DUCKDB = True
except Exception:
    _HAS_DUCKDB = False


# Resolve CSV path relative to the repo root (apex-wealth-agents), not the process CWD
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ENV_PATH = os.getenv("CSV_TRANSACTIONS_PATH")
if _ENV_PATH:
    DATA_PATH = _ENV_PATH if os.path.isabs(_ENV_PATH) else os.path.join(_BASE_DIR, _ENV_PATH.replace("/", os.sep))
else:
    # FALLBACK: Use demo_user data if primary 'data/transactions.csv' is missing
    fallback_path = os.path.join(_BASE_DIR, "state", "models", "user_data", "demo_user", "transactions.csv")
    if os.path.exists(fallback_path):
        DATA_PATH = fallback_path
    else:
        DATA_PATH = os.path.join(_BASE_DIR, "data", "transactions.csv")


def get_user_csv_path(user_id: Optional[str] = None, base_path: str = DATA_PATH) -> Optional[str]:
    """Resolve user-specific CSV path if user_id is provided and file exists"""
    if user_id:
        from app.tools.csv_tools import normalize_user_id
        safe_id = normalize_user_id(user_id)
        # Check in state/models/user_data/{safe_id}/transactions.csv
        user_path = os.path.join(_BASE_DIR, "state", "models", "user_data", safe_id, "transactions.csv")
        if os.path.exists(user_path):
            return user_path
    if os.path.exists(base_path):
        return base_path
    return None


def _ensure_csv_exists(path: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found at {path}")


def _detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Return best-guess mapping for all required financial columns."""
    date_variants = ["ts", "date", "Date", "DATE", "dt", "timestamp", "trans_date", "Transaction Date"]
    amount_variants = ["amount", "Amount", "AMOUNT", "monthly_expense_total", "val", "sum", "price", "cost", "Value"]
    category_variants = ["category", "Category", "CATEGORY", "goods", "type", "narration", "description", "Category Name"]
    type_variants = ["type", "Type", "TYPE", "transaction_type"]
    merchant_variants = ["merchant", "Merchant", "description", "Description", "narration", "Narration"]
    
    return {
        "date": next((c for c in date_variants if c in df.columns), None),
        "amount": next((c for c in amount_variants if c in df.columns), None),
        "category": next((c for c in category_variants if c in df.columns), None),
        "type": next((c for c in type_variants if c in df.columns), None),
        "merchant": next((c for c in merchant_variants if c in df.columns), None)
    }


def load_user_data_smart(user_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Load user CSV data and normalize it for financial processing.
    Ensures:
    1. Proper pandas datetime in 'date' column.
    2. Proper numeric in 'amount' column.
    3. Categorical robustness in 'category' column.
    4. Sign handling (converts 'outflow' to negative if all amounts are positive).
    """
    path = get_user_csv_path(user_id)
    if not path or not os.path.exists(path):
        return None
        
    try:
        df = pd.read_csv(path)
        if df.empty:
            return df
            
        cols = _detect_columns(df)
        
        # 1. Normalize Date
        if cols["date"]:
            df["date"] = pd.to_datetime(df[cols["date"]], errors="coerce")
            df = df.dropna(subset=["date"])
            
        # 2. Normalize Amount
        if cols["amount"]:
            df["amount"] = pd.to_numeric(df[cols["amount"]], errors="coerce").fillna(0)
            
            # Smart Sign Detection
            # If we have a 'type' column with 'inflow/outflow' but all amounts are positive, fix signs
            if cols["type"]:
                df["__type_lower"] = df[cols["type"]].astype(str).str.lower()
                is_outflow = df["__type_lower"].isin(["outflow", "expense", "debit", "withdrawal"])
                # Only apply if we find outflows and the amounts are currently positive
                if is_outflow.any() and (df.loc[is_outflow, "amount"] > 0).any():
                    df.loc[is_outflow, "amount"] = -df.loc[is_outflow, "amount"].abs()
            
        # 3. Normalize Category
        if cols["category"]:
            df["category"] = df[cols["category"]].fillna("Uncategorized")
        else:
            df["category"] = "Uncategorized"
            
        return df
    except Exception as e:
        print(f"[SMART LOAD ERROR] {e}")
        return None


def _merchant_column(df: pd.DataFrame) -> Optional[str]:
    return next((c for c in ["merchant", "description", "narration", "Merchant", "Description"] if c in df.columns), None)


def _run_duckdb(sql: str, csv_path: str = DATA_PATH) -> pd.DataFrame:
    allowed_starts = ("select", "with")
    first_word = sql.strip().lower().split()[0]
    if first_word not in allowed_starts:
        raise ValueError(f"Only SELECT and WITH queries are allowed. Found: {first_word}")
    con = duckdb.connect(database=":memory:")
    try:
        con.execute(f"CREATE TABLE t AS SELECT * FROM read_csv_auto('{csv_path}', SAMPLE_SIZE=20000)")
        return con.execute(sql).df()
    finally:
        try:
            con.close()
        except Exception:
            pass


def _ym_filter_clause(year: Optional[int], month: Optional[int], date_expr: str = "d") -> str:
    clauses: List[str] = []
    if year is not None:
        clauses.append(f"YEAR({date_expr}) = {int(year)}")
    if month is not None:
        clauses.append(f"MONTH({date_expr}) = {int(month)}")
    return (" AND ".join(clauses)) or "TRUE"


def _normalize_date_sql(date_col: str) -> str:
    """DuckDB-safe conversion of a raw string column to DATE, with fallback parsing."""
    # TRY_CAST handles already-date-like strings; strptime is robust for dd/mm/yy variants
    return (
        f"COALESCE(TRY_CAST({date_col} AS DATE), "
        f"TRY_STRPTIME(CAST({date_col} AS VARCHAR), '%Y-%m-%d'), "
        f"TRY_STRPTIME(CAST({date_col} AS VARCHAR), '%d-%m-%Y'), "
        f"TRY_STRPTIME(CAST({date_col} AS VARCHAR), '%d/%m/%Y'), "
        f"TRY_STRPTIME(CAST({date_col} AS VARCHAR), '%m/%d/%Y'), "
        f"TRY_STRPTIME(CAST({date_col} AS VARCHAR), '%d.%m.%Y')"  # extra common format
        ")"
    )


def _pandas_date_series(df: pd.DataFrame, date_col: str) -> pd.Series:
    return pd.to_datetime(df[date_col], errors="coerce")


def total_spend(year: Optional[int] = None, month: Optional[int] = None, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return total amount spent for optional year and/or month filters."""
    path = csv_path or get_user_csv_path(user_id)
    if not path:
        return {"total": 0.0, "notes": "No data available"}
    _ensure_csv_exists(path)
    if _HAS_DUCKDB:
        df_head = pd.read_csv(path, nrows=1000)
        cols = _detect_columns(df_head)
        date_col = cols["date"]
        amount_col = cols["amount"]
        if not amount_col:
            return {"total": 0.0, "notes": "amount column not found"}
        d_expr = _normalize_date_sql(date_col) if date_col else "NULL"
        where = _ym_filter_clause(year, month, date_expr="d") if date_col else "TRUE"
        sql = f"""
            WITH s AS (
                SELECT {d_expr} AS d, CAST({amount_col} AS DOUBLE) AS amt FROM t
            )
            SELECT COALESCE(SUM(amt), 0) AS total FROM s WHERE {where}
        """
        df = _run_duckdb(sql, path)
        return {"year": year, "month": month, "total": round(float(df.iloc[0]["total"] or 0.0), 2)}

    df = pd.read_csv(path)
    cols = _detect_columns(df)
    date_col = cols["date"]
    amount_col = cols["amount"]
    if not amount_col:
        return {"total": 0.0, "notes": "amount column not found"}
    if date_col:
        ds = _pandas_date_series(df, date_col)
        if year is not None:
            df = df[ds.dt.year == int(year)]
        if month is not None:
            df = df[ds.dt.month == int(month)]
    total_val = float(pd.to_numeric(df[amount_col], errors="coerce").sum() or 0.0)
    return {"year": year, "month": month, "total": round(total_val, 2)}


def monthly_spend(year: Optional[int] = None, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return spend aggregated by month. If year provided, filter to that year."""
    path = csv_path or get_user_csv_path(user_id)
    if not path:
        return {"items": [], "notes": "No data available"}
    _ensure_csv_exists(path)
    if _HAS_DUCKDB:
        df_head = pd.read_csv(path, nrows=1000)
        cols = _detect_columns(df_head)
        date_col = cols["date"]
        amount_col = cols["amount"]
        if not (date_col and amount_col):
            return {"items": [], "notes": "date/amount columns not found"}
        d_expr = _normalize_date_sql(date_col)
        where = _ym_filter_clause(year, None, date_expr="d") if year is not None else "TRUE"
        sql = f"""
            WITH s AS (
                SELECT DATE_TRUNC('month', {d_expr}) AS m, CAST({amount_col} AS DOUBLE) AS amt FROM t
            )
            SELECT CAST(m AS DATE) AS month, SUM(amt) AS spent
            FROM s
            WHERE {where}
            GROUP BY 1
            ORDER BY 1
        """
        df = _run_duckdb(sql, path)
        items = [{"month": str(r["month"]), "spent": round(float(r["spent"] or 0.0), 2)} for _, r in df.iterrows()]
        return {"year": year, "items": items}

    df = pd.read_csv(path)
    cols = _detect_columns(df)
    date_col = cols["date"]
    amount_col = cols["amount"]
    if not (date_col and amount_col):
        return {"items": [], "notes": "date/amount columns not found"}
    ds = _pandas_date_series(df, date_col)
    if year is not None:
        df = df[ds.dt.year == int(year)]
        ds = _pandas_date_series(df, date_col)
    grp = (
        df.assign(__month=ds.dt.to_period("M").astype(str))
          .groupby("__month")[amount_col]
          .sum()
          .reset_index()
          .sort_values("__month")
    )
    items = [{"month": r["__month"], "spent": round(float(r[amount_col] or 0.0), 2)} for _, r in grp.iterrows()]
    return {"year": year, "items": items}


def daily_spend(year: Optional[int] = None, month: Optional[int] = None, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return spend aggregated by day with optional year/month filters."""
    path = csv_path or get_user_csv_path(user_id)
    if not path:
        return {"items": [], "notes": "No data available"}
    _ensure_csv_exists(path)
    if _HAS_DUCKDB:
        df_head = pd.read_csv(path, nrows=1000)
        cols = _detect_columns(df_head)
        date_col = cols["date"]
        amount_col = cols["amount"]
        if not (date_col and amount_col):
            return {"items": [], "notes": "date/amount columns not found"}
        d_expr = _normalize_date_sql(date_col)
        where = _ym_filter_clause(year, month, date_expr="d")
        sql = f"""
            WITH s AS (
                SELECT {d_expr} AS d, CAST({amount_col} AS DOUBLE) AS amt FROM t
            )
            SELECT CAST(d AS DATE) AS day, SUM(amt) AS spent
            FROM s
            WHERE {where}
            GROUP BY 1
            ORDER BY 1
        """
        df = _run_duckdb(sql, path)
        items = [{"day": str(r["day"]), "spent": round(float(r["spent"] or 0.0), 2)} for _, r in df.iterrows()]
        return {"year": year, "month": month, "items": items}

    df = pd.read_csv(path)
    cols = _detect_columns(df)
    date_col = cols["date"]
    amount_col = cols["amount"]
    if not (date_col and amount_col):
        return {"items": [], "notes": "date/amount columns not found"}
    ds = _pandas_date_series(df, date_col)
    if year is not None:
        df = df[ds.dt.year == int(year)]
        ds = _pandas_date_series(df, date_col)
    if month is not None:
        df = df[ds.dt.month == int(month)]
        ds = _pandas_date_series(df, date_col)
    grp = (
        df.assign(__day=ds.dt.date.astype(str))
          .groupby("__day")[amount_col]
          .sum()
          .reset_index()
          .sort_values("__day")
    )
    items = [{"day": r["__day"], "spent": round(float(r[amount_col] or 0.0), 2)} for _, r in grp.iterrows()]
    return {"year": year, "month": month, "items": items}


def category_stats(year: Optional[int] = None, month: Optional[int] = None, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return sum by category with optional year/month filters."""
    path = csv_path or get_user_csv_path(user_id)
    if not path:
        return {"items": [], "notes": "No data available"}
    _ensure_csv_exists(path)
    if _HAS_DUCKDB:
        df_head = pd.read_csv(path, nrows=1000)
        cols = _detect_columns(df_head)
        date_col = cols["date"]
        amount_col = cols["amount"]
        category_col = cols["category"]
        if not (amount_col and category_col):
            return {"items": [], "notes": "amount/category columns not found"}
        d_expr = _normalize_date_sql(date_col) if date_col else "NULL"
        where = _ym_filter_clause(year, month, date_expr="d") if date_col else "TRUE"
        sql = f"""
            WITH s AS (
                SELECT {d_expr} AS d, CAST({amount_col} AS DOUBLE) AS amt, {category_col} AS category FROM t
            )
            SELECT category, SUM(amt) AS spent
            FROM s
            WHERE {where}
            GROUP BY 1
            ORDER BY spent DESC
        """
        df = _run_duckdb(sql, path)
        items = [{"category": str(r["category"]), "spent": round(float(r["spent"] or 0.0), 2)} for _, r in df.iterrows()]
        return {"year": year, "month": month, "items": items}

    df = pd.read_csv(path)
    cols = _detect_columns(df)
    date_col = cols["date"]
    amount_col = cols["amount"]
    category_col = cols["category"]
    if not (amount_col and category_col):
        return {"items": [], "notes": "amount/category columns not found"}
    if date_col:
        ds = _pandas_date_series(df, date_col)
        if year is not None:
            df = df[ds.dt.year == int(year)]
            ds = _pandas_date_series(df, date_col)
        if month is not None:
            df = df[ds.dt.month == int(month)]
    grp = df.groupby(category_col)[amount_col].sum().reset_index().sort_values(amount_col, ascending=False)
    items = [{"category": str(r[category_col]), "spent": round(float(r[amount_col] or 0.0), 2)} for _, r in grp.iterrows()]
    return {"year": year, "month": month, "items": items}


def merchant_stats(year: Optional[int] = None, month: Optional[int] = None, top_n: int = 10, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return top merchants by spend with optional filters."""
    path = csv_path or get_user_csv_path(user_id)
    if not path:
        return {"items": [], "notes": "No data available"}
    _ensure_csv_exists(path)
    if _HAS_DUCKDB:
        df_head = pd.read_csv(path, nrows=1000)
        cols = _detect_columns(df_head)
        date_col = cols["date"]
        amount_col = cols["amount"]
        merchant_col = _merchant_column(df_head)
        if not (merchant_col and amount_col):
            return {"items": [], "notes": "merchant/amount columns not found"}
        d_expr = _normalize_date_sql(date_col) if date_col else "NULL"
        where = _ym_filter_clause(year, month, date_expr="d") if date_col else "TRUE"
        sql = f"""
            WITH s AS (
                SELECT {d_expr} AS d, CAST({amount_col} AS DOUBLE) AS amt, {merchant_col} AS merchant FROM t
            )
            SELECT merchant, SUM(amt) AS spent
            FROM s
            WHERE {where}
            GROUP BY 1
            ORDER BY spent DESC
            LIMIT {int(top_n or 10)}
        """
        df = _run_duckdb(sql, path)
        items = [{"merchant": str(r["merchant"]), "spent": round(float(r["spent"] or 0.0), 2)} for _, r in df.iterrows()]
        return {"year": year, "month": month, "items": items}

    df = pd.read_csv(path)
    cols = _detect_columns(df)
    date_col = cols["date"]
    amount_col = cols["amount"]
    merchant_col = _merchant_column(df)
    if not (merchant_col and amount_col):
        return {"items": [], "notes": "merchant/amount columns not found"}
    if date_col:
        ds = _pandas_date_series(df, date_col)
        if year is not None:
            df = df[ds.dt.year == int(year)]
            ds = _pandas_date_series(df, date_col)
        if month is not None:
            df = df[ds.dt.month == int(month)]
    grp = df.groupby(merchant_col)[amount_col].sum().reset_index().sort_values(amount_col, ascending=False).head(int(top_n or 10))
    items = [{"merchant": str(r[merchant_col]), "spent": round(float(r[amount_col] or 0.0), 2)} for _, r in grp.iterrows()]
    return {"year": year, "month": month, "items": items}


def time_coverage(csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return min/max dates found in the dataset."""
    path = csv_path or get_user_csv_path(user_id)
    _ensure_csv_exists(path)
    df = pd.read_csv(path, nrows=50000)
    cols = _detect_columns(df)
    date_col = cols["date"]
    if not date_col:
        return {"min": None, "max": None}
    ds = _pandas_date_series(df, date_col)
    if ds.notna().any():
        return {"min": str(ds.min().date()), "max": str(ds.max().date())}
    return {"min": None, "max": None}


__all__ = [
    "total_spend",
    "monthly_spend",
    "daily_spend",
    "category_stats",
    "merchant_stats",
    "time_coverage",
]


def extract_year_data(year: int, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Extract all data for a specific year (Backward compatibility wrapper)"""
    try:
        path = csv_path or get_user_csv_path(user_id)
        if not path: return {"year": year, "data_available": False}
        
        df = pd.read_csv(path)
        cols = _detect_columns(df)
        date_col = cols["date"]
        amount_col = cols["amount"]
        cat_col = cols["category"]
        if not date_col: return {"year": year, "data_available": False}
        
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        year_data = df[df[date_col].dt.year == year].copy()
        
        if year_data.empty:
            return {"year": year, "data_available": False}
            
        stats = category_stats(year=year, csv_path=path)
        monthly = monthly_spend(year=year, csv_path=path)
        
        return {
            "year": year,
            "total_spent": total_spend(year=year, csv_path=path)["total"],
            "categories": stats["items"],
            "monthly_breakdown": monthly["items"],
            "data_available": True
        }
    except Exception as e:
        return {"year": year, "error": str(e), "data_available": False}

def extract_year_range_data(start_year: int, end_year: int, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Extract data for a range of years"""
    # Simple wrapper for backward compatibility
    return {"start_year": start_year, "end_year": end_year, "data_available": False, "notes": "Use total_spend/category_stats with filters"}

def extract_month_data(year: int, month: int, csv_path: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Extract data for a specific month"""
    try:
        path = csv_path or get_user_csv_path(user_id)
        stats = category_stats(year=year, month=month, csv_path=path)
        total = total_spend(year=year, month=month, csv_path=path)
        return {
            "year": year, "month": month,
            "total_spent": total["total"],
            "categories": stats["items"],
            "data_available": len(stats["items"]) > 0
        }
    except Exception:
        return {"year": year, "month": month, "data_available": False}

def get_available_years(csv_path: Optional[str] = None, user_id: Optional[str] = None) -> List[int]:
    """Get list of available years in the dataset"""
    try:
        path = csv_path or get_user_csv_path(user_id)
        if not path: return []
        df = pd.read_csv(path, usecols=lambda x: x.lower() in ['date', 'ts'])
        date_col = next((c for c in df.columns if c.lower() in ['date', 'ts']), None)
        if not date_col: return []
        years = sorted(pd.to_datetime(df[date_col], errors='coerce').dt.year.dropna().unique().tolist())
        return [int(y) for y in years]
    except Exception:
        return []

def load_user_data_distributed(user_id: Optional[str] = None, chunk_size: int = 5000) -> pd.DataFrame:
    """
    High-Throughput Parallel Data Processing.
    Loads large CSV files in parallel using the ParallelStreamProcessor.
    """
    path = get_user_csv_path(user_id)
    if not path or not os.path.exists(path):
        return pd.DataFrame()
        
    processor = ParallelStreamProcessor(chunk_size=chunk_size)
    print(f"🚀 Initializing Distributed Processing for {path}...")
    
    # Process the CSV data in distributed fashion
    df = processor.process_csv(path)
    
    # Standard normalization after distributed loading
    if not df.empty:
        cols = _detect_columns(df)
        if cols["date"]:
            df["date"] = pd.to_datetime(df[cols["date"]], errors="coerce")
        if cols["amount"]:
            df["amount"] = pd.to_numeric(df[cols["amount"]], errors="coerce").fillna(0)
            
    return df

__all__ = [
    "total_spend",
    "monthly_spend",
    "daily_spend",
    "category_stats",
    "merchant_stats",
    "time_coverage",
    "get_available_years",
    "extract_year_data",
    "extract_month_data",
    "format_currency",
    "load_user_data_distributed"
]
