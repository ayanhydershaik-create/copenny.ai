"""
app/routers/goals.py
Goal management API endpoints backed by PostgreSQL database.
Includes AI-powered goal planning via the Goal Execution Agent.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from fastapi import Cookie
import asyncio

router = APIRouter(prefix="/api/goals", tags=["goals"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class GoalCreate(BaseModel):
    name: str
    target_amount: float
    current_amount: float = 0.0
    deadline: Optional[str] = None
    auto_save_amount: float = 0.0
    auto_save_frequency: str = "monthly"


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    deadline: Optional[str] = None
    auto_save_amount: Optional[float] = None
    auto_save_frequency: Optional[str] = None
    status: Optional[str] = None


class GoalPlanRequest(BaseModel):
    message: str
    goal_id: Optional[str] = None


@router.get("")
def list_goals(user_id: str = Depends(get_user_id)):
    """Get all savings goals from PostgreSQL."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    goals = pg.get_goals(user_id)
    # Compute progress percentages
    for g in goals:
        target = float(g.get("target_amount") or 1)
        current = float(g.get("current_amount") or 0)
        g["progress_pct"] = round(min(100, current / target * 100), 1)
    return {"goals": goals, "count": len(goals)}


@router.get("/{goal_id}")
def get_goal(goal_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    goal = pg.get_goal(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.post("", status_code=201)
def create_goal(body: GoalCreate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        goal = pg.create_goal(user_id, body.model_dump())
        return goal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{goal_id}")
def update_goal(goal_id: str, body: GoalUpdate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    updated = pg.update_goal(goal_id, user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Goal not found")
    return updated


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    pg.delete_goal(goal_id, user_id)
    return None


@router.post("/plan")
async def plan_goal(body: GoalPlanRequest, user_id: str = Depends(get_user_id)):
    """
    AI-powered goal planning endpoint.
    Analyzes user's financial data and creates a realistic savings plan.
    Returns the plan for user confirmation before saving.
    """
    pg = get_postgres_service()
    from app.services.ai.agents.goals import analyze_goal_request

    # Get financial context
    analytics = pg.get_transaction_analytics(user_id)
    plan = await analyze_goal_request(body.message, analytics)

    return {
        "plan": plan,
        "requires_confirmation": True,
        "message": f"I've analyzed your finances and created a savings plan. Monthly savings capacity: ₹{(analytics.get('total_income', 0) - analytics.get('total_expense', 0)) / 3:,.0f}",
    }


@router.post("/{goal_id}/add-savings")
def add_savings(goal_id: str, amount: float = Query(..., gt=0), user_id: str = Depends(get_user_id)):
    """Add savings progress to a goal."""
    pg = get_postgres_service()
    goal = pg.get_goal(goal_id, user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    new_amount = float(goal.get("current_amount") or 0) + amount
    target = float(goal.get("target_amount") or 1)
    new_status = "completed" if new_amount >= target else goal.get("status", "active")
    updated = pg.update_goal(goal_id, user_id, {
        "current_amount": new_amount,
        "saved_amount": new_amount,
        "status": new_status,
    })
    completed = new_status == "completed" and goal.get("status") != "completed"
    return {
        "goal": updated,
        "progress_pct": round(min(100, new_amount / target * 100), 1),
        "completed": completed,
        "celebration": "🎉 Congratulations! You've reached your savings goal!" if completed else None,
    }
