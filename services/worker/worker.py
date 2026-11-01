import asyncio
import random
import uuid

from sqlalchemy.orm import Session
from database import SessionLocal
from models import TransactionModel, TransactionType, TransactionStatus

ACTIVE_USER_IDS = [f"usr_{str(uuid.uuid4())[:8]}" for _ in range(50)]


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

if __name__ == "__main__":
    print("Starting synthetic transaction worker...")
    asyncio.run(generate_synthetic_data())