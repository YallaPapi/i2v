"""Credits service for managing user credit balances.

Provides atomic credit operations with transaction logging.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
import structlog

from app.models import User, CreditTransaction

logger = structlog.get_logger()


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits for an operation."""
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient credits: need {required}, have {available}")


def get_balance(db: Session, user_id: int) -> int:
    """Get current credit balance for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")
    return user.credits_balance


def add_credits(
    db: Session,
    user_id: int,
    amount: int,
    description: str,
    source: str = "manual",
    reference_id: Optional[str] = None,
) -> CreditTransaction:
    """Add credits to a user's balance.

    Args:
        db: Database session
        user_id: User ID to credit
        amount: Amount to add (must be positive)
        description: Human-readable description
        source: Transaction source (payment, manual, promo, refund)
        reference_id: Optional reference to payment, job, etc.

    Returns:
        Created CreditTransaction record
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for add_credits")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    new_balance = user.credits_balance + amount
    user.credits_balance = new_balance

    transaction = CreditTransaction(
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        description=description,
        source=source,
        reference_id=reference_id,
    )
    db.add(transaction)
    db.commit()

    logger.info(
        "Credits added",
        user_id=user_id,
        amount=amount,
        new_balance=new_balance,
        source=source,
    )

    return transaction


def deduct_credits(
    db: Session,
    user_id: int,
    amount: int,
    description: str,
    source: str = "job",
    reference_id: Optional[str] = None,
    allow_negative: bool = False,
) -> CreditTransaction:
    """Deduct credits from a user's balance.

    Args:
        db: Database session
        user_id: User ID to debit
        amount: Amount to deduct (must be positive)
        description: Human-readable description
        source: Transaction source (job, manual, etc.)
        reference_id: Optional reference to job, etc.
        allow_negative: If False, raises InsufficientCreditsError

    Returns:
        Created CreditTransaction record

    Raises:
        InsufficientCreditsError: If user doesn't have enough credits
    """
    if amount <= 0:
        raise ValueError("Amount must be positive for deduct_credits")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    if not allow_negative and user.credits_balance < amount:
        raise InsufficientCreditsError(amount, user.credits_balance)

    new_balance = user.credits_balance - amount
    user.credits_balance = new_balance

    transaction = CreditTransaction(
        user_id=user_id,
        amount=-amount,  # Negative for deductions
        balance_after=new_balance,
        description=description,
        source=source,
        reference_id=reference_id,
    )
    db.add(transaction)
    db.commit()

    logger.info(
        "Credits deducted",
        user_id=user_id,
        amount=amount,
        new_balance=new_balance,
        source=source,
    )

    return transaction


def check_sufficient_credits(db: Session, user_id: int, required: int) -> bool:
    """Check if user has sufficient credits for an operation.

    Args:
        db: Database session
        user_id: User ID to check
        required: Required credit amount

    Returns:
        True if user has enough credits
    """
    balance = get_balance(db, user_id)
    return balance >= required


def get_transaction_history(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    source: Optional[str] = None,
) -> list[CreditTransaction]:
    """Get credit transaction history for a user.

    Args:
        db: Database session
        user_id: User ID
        limit: Max results to return
        offset: Offset for pagination
        source: Optional filter by source type

    Returns:
        List of CreditTransaction records
    """
    query = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
    )

    if source:
        query = query.filter(CreditTransaction.source == source)

    return query.offset(offset).limit(limit).all()


def refund_credits(
    db: Session,
    user_id: int,
    amount: int,
    description: str,
    reference_id: Optional[str] = None,
) -> CreditTransaction:
    """Refund credits to a user (convenience wrapper for add_credits with source='refund')."""
    return add_credits(
        db=db,
        user_id=user_id,
        amount=amount,
        description=description,
        source="refund",
        reference_id=reference_id,
    )


# Pricing constants (credits per action)
PRICING = {
    # Image generation
    "i2i_standard": 1,  # Standard quality image
    "i2i_high": 2,  # High quality image
    "i2i_nsfw": 1,  # NSFW image (self-hosted, cheaper)

    # Video generation
    "i2v_5s": 5,  # 5 second video
    "i2v_10s": 10,  # 10 second video

    # Full pipeline
    "pipeline_full": 15,  # Image + video + audio + lip sync

    # Carousel
    "carousel_5": 3,  # 5-slide carousel
    "carousel_10": 5,  # 10-slide carousel

    # Extras
    "voice_clone": 5,  # Voice cloning setup
    "face_swap": 2,  # Face swap operation
}


def calculate_job_cost(
    output_type: str,
    quantity: int,
    options: Optional[dict] = None,
) -> int:
    """Calculate credit cost for a job.

    Args:
        output_type: Type of output (i2i, i2v, carousel, pipeline)
        quantity: Number of items to generate
        options: Additional options affecting price

    Returns:
        Total credits required
    """
    options = options or {}

    # Base pricing
    if output_type == "i2i":
        quality = options.get("quality", "standard")
        is_nsfw = options.get("nsfw", False)
        if is_nsfw:
            base_cost = PRICING["i2i_nsfw"]
        elif quality == "high":
            base_cost = PRICING["i2i_high"]
        else:
            base_cost = PRICING["i2i_standard"]

    elif output_type == "i2v":
        duration = options.get("duration_sec", 5)
        base_cost = PRICING["i2v_10s"] if duration >= 10 else PRICING["i2v_5s"]

    elif output_type == "carousel":
        slides = options.get("slides", 5)
        base_cost = PRICING["carousel_10"] if slides > 5 else PRICING["carousel_5"]

    elif output_type == "pipeline":
        base_cost = PRICING["pipeline_full"]

    else:
        base_cost = 1  # Default fallback

    return base_cost * quantity
