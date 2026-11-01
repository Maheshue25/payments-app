from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime
from database import Base
from enum import Enum

class TransactionType(str, Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    transfer = "transfer"

class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="completed")
    sender_id = Column(String, nullable=True)
    recipient_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))