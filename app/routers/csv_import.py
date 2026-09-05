"""
app/routers/csv_import.py
CSV Upload & Bulk Transaction Import backed by PostgreSQL batch insertion.

Requirements:
- File upload & CSV parsing
- Flexible column detection (date, description, amount, category, merchant)
- Preview before import
- Auto-categorization using keywords / fallback
- Batch insertion with ON CONFLICT DO NOTHING (duplicate avoidance)
- Import summary with valid, duplicates, invalid counts
"""
import io
import csv
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Cookie
from pydantic import BaseModel

from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token

router = APIRouter(prefix="/api/import", tags=["csv_import"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


def _auto_categorize(desc: str, current_cat: str) -> str:
    if current_cat and current_cat.lower() not in ["", "uncategorized", "other", "none"]:
        return current_cat

    desc_lower = desc.lower()
    keywords = {
        "Food & Dining": ["swiggy", "zomato", "restaurant", "cafe", "coffee", "starbucks", "mcdonald", "burger", "pizza", "subway", "bar", "kitchen"],
        "Groceries": ["supermarket", "grocery", "zepto", "blinkit", "instamart", "bigbasket", "dmart", "spencer", "store"],
        "Shopping": ["amazon", "flipkart", "myntra", "zara", "h&m", "retail", "clothing", "apple", "apparel"],
        "Entertainment": ["netflix", "spotify", "prime", "hotstar", "cinema", "movie", "bookmyshow", "youtube", "steam", "playstation"],
        "Transportation": ["uber", "ola", "metro", "fuel", "petrol", "diesel", "shell", "hpcl", "flight", "indigo", "irctc", "train"],
        "Utilities": ["electricity", "water", "gas", "broadband", "wifi", "airtel", "jio", "vi", "recharge", "bill"],
        "Healthcare": ["pharmacy", "apollo", "medplus", "hospital", "clinic", "doctor", "lab", "medicine"],
        "Investment": ["zerodha", "groww", "mutual fund", "sip", "stocks", "etf", "indmoney"],
        "Income": ["salary", "payroll", "dividend", "interest", "bonus", "freelance", "refund"],
    }
    for cat, kws in keywords.items():
        if any(kw in desc_lower for kw in kws):
            return cat
    return "General Expense"


def _normalize_date(val: str) -> str:
    val = val.strip()
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def _parse_csv_content(content: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return []

    # Map headers
    field_map = {}
    for f in reader.fieldnames:
        f_norm = f.strip().lower()
        if "date" in f_norm or "time" in f_norm:
            field_map["date"] = f
        elif "amount" in f_norm or "sum" in f_norm or "price" in f_norm:
            field_map["amount"] = f
        elif "merchant" in f_norm or "payee" in f_norm or "vendor" in f_norm:
            field_map["merchant"] = f
        elif "desc" in f_norm or "narration" in f_norm or "title" in f_norm or "particulars" in f_norm:
            field_map["description"] = f
        elif "cat" in f_norm:
            field_map["category"] = f
        elif "type" in f_norm:
            field_map["type"] = f

    rows = []
    for raw in reader:
        date_str = _normalize_date(raw.get(field_map.get("date", ""), ""))
        desc = raw.get(field_map.get("description", ""), "").strip()
        merchant = raw.get(field_map.get("merchant", ""), "").strip()
        cat_raw = raw.get(field_map.get("category", ""), "").strip()

        # Parse amount
        amount_raw = raw.get(field_map.get("amount", "0"), "0")
        try:
            cleaned_amt = str(amount_raw).replace(",", "").replace("₹", "").replace("$", "").strip()
            amount = float(cleaned_amt)
        except ValueError:
            continue

        category = _auto_categorize(f"{desc} {merchant}", cat_raw)
        tx_type = "income" if amount > 0 and ("salary" in desc.lower() or category == "Income") else "expense"
        if amount < 0:
            tx_type = "expense"
            amount = abs(amount)

        rows.append({
            "date": date_str,
            "description": desc or merchant or "Expense",
            "merchant": merchant or desc or "Merchant",
            "amount": amount,
            "category": category,
            "type": tx_type,
            "notes": "Imported via CSV",
        })
    return rows


@router.post("/preview")
async def preview_csv(file: UploadFile = File(...), user_id: str = Depends(get_user_id)):
    """
    Preview the uploaded CSV file. Parses headers, auto-categorizes, and returns summary stats.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = (await file.read()).decode("utf-8", errors="replace")
    rows = _parse_csv_content(content)

    if not rows:
        raise HTTPException(status_code=400, detail="No valid transactions could be parsed from this CSV.")

    return {
        "filename": file.filename,
        "total_rows_detected": len(rows),
        "preview": rows[:10],
        "categories_found": list(set(r["category"] for r in rows)),
        "total_amount_preview": round(sum(r["amount"] for r in rows), 2),
    }


class ImportConfirmReq(BaseModel):
    rows: List[Dict[str, Any]]


@router.post("/confirm")
async def confirm_csv_import(body: ImportConfirmReq, user_id: str = Depends(get_user_id)):
    """
    Commit parsed transactions to PostgreSQL in an efficient batch operation.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="PostgreSQL database unavailable")

    if not body.rows:
        raise HTTPException(status_code=400, detail="No rows provided for import")

    inserted = pg.batch_insert_transactions(user_id, body.rows)
    total = len(body.rows)
    duplicates = total - inserted

    return {
        "success": True,
        "total_rows": total,
        "inserted": inserted,
        "duplicates_skipped": duplicates,
        "summary": f"Import complete: {inserted} transactions added, {duplicates} skipped as duplicates/invalid.",
    }
