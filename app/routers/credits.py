"""Credits router for viewing and managing user credits."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models import User, CreditTransaction
from app.core.security import get_current_user, require_role
from app.services.credits import (
    get_balance,
    get_transaction_history,
    add_credits,
    deduct_credits,
    calculate_job_cost,
    PRICING,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/credits", tags=["credits"])


# ============== Schemas ==============


class CreditBalanceResponse(BaseModel):
    """Response for credit balance."""
    balance: int
    tier: str


class TransactionResponse(BaseModel):
    """Response for a single transaction."""
    id: int
    amount: int
    balance_after: int
    description: str
    source: str
    reference_id: Optional[str]
    created_at: str


class TransactionListResponse(BaseModel):
    """Response for transaction list."""
    transactions: List[TransactionResponse]
    total: int


class CostEstimateRequest(BaseModel):
    """Request for cost estimation."""
    output_type: str = Field(..., description="Type: i2i, i2v, carousel, pipeline")
    quantity: int = Field(1, ge=1, le=500)
    options: Optional[dict] = None


class CostEstimateResponse(BaseModel):
    """Response for cost estimation."""
    output_type: str
    quantity: int
    credits_per_item: int
    total_credits: int
    sufficient: bool
    current_balance: int


class AdminCreditAdjustRequest(BaseModel):
    """Admin request to adjust user credits."""
    user_id: int
    amount: int = Field(..., description="Positive to add, negative to deduct")
    description: str = Field(..., max_length=500)


class PricingResponse(BaseModel):
    """Response with pricing table."""
    pricing: dict


# ============== User Endpoints ==============


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_my_balance(user: User = Depends(get_current_user)):
    """Get current user's credit balance."""
    return CreditBalanceResponse(
        balance=user.credits_balance,
        tier=user.tier,
    )


@router.get("/transactions", response_model=TransactionListResponse)
async def get_my_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None, description="Filter by source: payment, job, manual, promo, refund"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's credit transaction history."""
    transactions = get_transaction_history(
        db=db,
        user_id=user.id,
        limit=limit,
        offset=offset,
        source=source,
    )

    # Get total count for pagination
    total_query = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id)
    if source:
        total_query = total_query.filter(CreditTransaction.source == source)
    total = total_query.count()

    return TransactionListResponse(
        transactions=[
            TransactionResponse(
                id=t.id,
                amount=t.amount,
                balance_after=t.balance_after,
                description=t.description,
                source=t.source,
                reference_id=t.reference_id,
                created_at=t.created_at.isoformat(),
            )
            for t in transactions
        ],
        total=total,
    )


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_cost(
    request: CostEstimateRequest,
    user: User = Depends(get_current_user),
):
    """Estimate credit cost for a job before submitting."""
    total = calculate_job_cost(
        output_type=request.output_type,
        quantity=request.quantity,
        options=request.options,
    )

    credits_per_item = total // request.quantity if request.quantity > 0 else 0

    return CostEstimateResponse(
        output_type=request.output_type,
        quantity=request.quantity,
        credits_per_item=credits_per_item,
        total_credits=total,
        sufficient=user.credits_balance >= total,
        current_balance=user.credits_balance,
    )


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing():
    """Get current pricing table (public endpoint)."""
    return PricingResponse(pricing=PRICING)


# ============== Admin Endpoints ==============


@router.post("/admin/adjust")
async def admin_adjust_credits(
    request: AdminCreditAdjustRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to manually adjust user credits."""
    # Check target user exists
    target_user = db.query(User).filter(User.id == request.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        if request.amount > 0:
            transaction = add_credits(
                db=db,
                user_id=request.user_id,
                amount=request.amount,
                description=f"Admin adjustment: {request.description}",
                source="manual",
                reference_id=f"admin:{admin.id}",
            )
        else:
            transaction = deduct_credits(
                db=db,
                user_id=request.user_id,
                amount=abs(request.amount),
                description=f"Admin adjustment: {request.description}",
                source="manual",
                reference_id=f"admin:{admin.id}",
                allow_negative=True,  # Admins can force negative balance
            )

        logger.info(
            "Admin credit adjustment",
            admin_id=admin.id,
            target_user_id=request.user_id,
            amount=request.amount,
            new_balance=transaction.balance_after,
        )

        return {
            "success": True,
            "transaction_id": transaction.id,
            "new_balance": transaction.balance_after,
        }

    except Exception as e:
        logger.error("Credit adjustment failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust credits: {str(e)}",
        )


@router.get("/admin/user/{user_id}/balance")
async def admin_get_user_balance(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to view any user's credit balance."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "user_id": target_user.id,
        "email": target_user.email,
        "balance": target_user.credits_balance,
        "tier": target_user.tier,
    }


@router.get("/admin/user/{user_id}/transactions", response_model=TransactionListResponse)
async def admin_get_user_transactions(
    user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to view any user's transaction history."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    transactions = get_transaction_history(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    total = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).count()

    return TransactionListResponse(
        transactions=[
            TransactionResponse(
                id=t.id,
                amount=t.amount,
                balance_after=t.balance_after,
                description=t.description,
                source=t.source,
                reference_id=t.reference_id,
                created_at=t.created_at.isoformat(),
            )
            for t in transactions
        ],
        total=total,
    )
