import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
import random
import uuid

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Import database setup and models at the top
from database import engine, Base, SessionLocal, get_db
from models import TransactionModel

# Create tables in PostgreSQL
Base.metadata.create_all(bind=engine)

# --- 1. Pydantic Schemas ---
class TransactionType(str, Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    transfer = "transfer"

class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Amount must be strictly positive")
    type: TransactionType
    sender_id: str | None = None
    recipient_id: str | None = None

class TransactionResponse(TransactionCreate):
    id: str
    timestamp: datetime
    status: TransactionStatus

    class Config:
        from_attributes = True

ACTIVE_USER_IDS = [f"usr_{str(uuid.uuid4())[:8]}" for _ in range(50)]

# --- 2. Background Task ---
async def generate_synthetic_data():
    while True:
        await asyncio.sleep(10)
        txn_type = random.choice(list(TransactionType))
        sender = random.choice(ACTIVE_USER_IDS) if txn_type in [TransactionType.transfer, TransactionType.withdrawal] else None
        recipient = random.choice(ACTIVE_USER_IDS) if txn_type in [TransactionType.transfer, TransactionType.deposit] else None

        if txn_type == TransactionType.transfer:
            while recipient == sender:
                recipient = random.choice(ACTIVE_USER_IDS)

        db = SessionLocal()
        try:
            record = TransactionModel(
                amount=round(random.uniform(5.0, 2500.0), 2),
                type=txn_type.value,
                sender_id=sender,
                recipient_id=recipient,
                status=TransactionStatus.completed.value
            )
            db.add(record)
            db.commit()
            print(f"[DB Stream] Saved: {record.type.upper()} ${record.amount} | {sender or 'EXTERNAL'} -> {recipient or 'EXTERNAL'}")
        except Exception as e:
            db.rollback()
            print(f"[DB Stream Error]: {e}")
        finally:
            db.close()

# --- 3. App Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(generate_synthetic_data())
    yield
    task.cancel()

app = FastAPI(title="Finance API with PostgreSQL", lifespan=lifespan)

# CORS Middleware with explicit origins and wildcard methods/headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Routes ---
@app.get("/")
def root(db: Session = Depends(get_db)):
    count = db.query(TransactionModel).count()
    return {"message": "Finance API is connected to PostgreSQL", "total_transactions_in_db": count}

@app.post("/transactions", response_model=TransactionResponse)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    if payload.type == TransactionType.transfer and (not payload.sender_id or not payload.recipient_id):
        raise HTTPException(status_code=400, detail="Transfers require both sender_id and recipient_id")

    db_txn = TransactionModel(
        amount=payload.amount,
        type=payload.type.value,
        sender_id=payload.sender_id,
        recipient_id=payload.recipient_id,
        status=TransactionStatus.completed.value
    )
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)
    return db_txn

@app.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(TransactionModel).order_by(TransactionModel.timestamp.desc()).limit(limit).all()