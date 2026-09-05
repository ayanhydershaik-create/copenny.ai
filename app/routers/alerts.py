from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from app.services.email_service import EmailService

router = APIRouter(prefix="/alerts", tags=["alerts"])
email_service = EmailService()

class AlertRequest(BaseModel):
    email: EmailStr
    message: str = Field(..., max_length=1000)

@router.post("/test")
def test_alert(req: AlertRequest, request: Request):
    """
    Send a test email alert.
    """
    from app.tools.main import limiter
    @limiter.limit("2/minute")
    def _test_alert(req: AlertRequest, request: Request):
        if not email_service.enabled:
            raise HTTPException(status_code=503, detail="Email service is not configured (SMTP credentials missing)")
        
        success = email_service.send_alert(
            to_email=req.email,
            subject="Co Penny Advisor - Test Alert",
            body=f"This is a test alert from your Copilot.\n\nMessage: {req.message}"
        )
        
        if success:
            return {"status": "success", "message": f"Email sent to {req.email}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    return _test_alert(req, request)
    """
    Send a test email alert.
    """
    if not email_service.enabled:
        raise HTTPException(status_code=503, detail="Email service is not configured (SMTP credentials missing)")
    
    success = email_service.send_alert(
        to_email=req.email,
        subject="Co Penny Advisor - Test Alert",
        body=f"This is a test alert from your Copilot.\n\nMessage: {req.message}"
    )
    
    if success:
        return {"status": "success", "message": f"Email sent to {req.email}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")
