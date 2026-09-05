"""
Demo Mode Router for Co Penny.
Provides endpoints to activate demo mode and retrieve pre-built demo summaries.
"""
from fastapi import APIRouter, Response

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/activate")
def activate_demo(response: Response):
    """Activate demo mode: generate sample data, issue a JWT cookie, and return demo user credentials."""
    try:
        from app.tools.demo_data import ensure_demo_data, DEMO_USER_ID
        from app.tools.auth import create_access_token
        ensure_demo_data()

        # Issue a signed JWT for the demo user
        token = create_access_token(data={"user_id": DEMO_USER_ID, "email": "demo@copenny.ai"})
        response.set_cookie(
            key="copenny_auth",
            value=token,
            path="/",
            max_age=604800, # 7 days
            samesite="lax",
            httponly=True
        )

        return {
            "success":   True,
            "user_id":   DEMO_USER_ID,
            "user_name": "Demo Investor",
            "message":   "Demo data loaded — explore Co Penny without uploading a CSV!",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/summary")
def demo_summary():
    """Return pre-computed financial summary for the demo user."""
    try:
        from app.tools.demo_data import get_demo_summary
        return get_demo_summary()
    except Exception as e:
        return {"success": False, "error": str(e), "has_data": False}
