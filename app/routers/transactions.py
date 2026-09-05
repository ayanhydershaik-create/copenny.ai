"""
app/routers/transactions.py
Transaction CRUD API endpoints backed by PostgreSQL hackwave_db.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional, List
from pydantic import BaseModel, Field
from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from fastapi import Cookie

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class TransactionCreate(BaseModel):
    date: str
    description: str = ""
    merchant: str = ""
    amount: float
    category: str = "Uncategorized"
    type: str = Field("expense", pattern="^(income|expense)$")
    notes: str = ""


class TransactionUpdate(BaseModel):
    date: Optional[str] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    type: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_transactions(
    user_id: str = Depends(get_user_id),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
):
    """Get transactions for the current user from PostgreSQL with filtering."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        rows = pg.get_transactions(
            user_id=user_id,
            limit=limit,
            offset=offset,
            category=category,
            tx_type=type,
            from_date=from_date,
            to_date=to_date,
            search=search,
        )
        return {"transactions": rows, "count": len(rows), "offset": offset, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
def get_analytics(user_id: str = Depends(get_user_id)):
    """Get category-level financial analytics from real PostgreSQL data."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        return pg.get_transaction_analytics(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tx_id}")
def get_transaction(tx_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    tx = pg.get_transaction(tx_id, user_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.post("", status_code=201)
def create_transaction(body: TransactionCreate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        tx = pg.create_transaction(user_id, body.model_dump())
        return tx
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tx_id}")
def update_transaction(tx_id: str, body: TransactionUpdate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    updated = pg.update_transaction(tx_id, user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return updated


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    pg.delete_transaction(tx_id, user_id)
    return None
