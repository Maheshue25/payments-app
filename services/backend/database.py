import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/finance_db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Creates the engine that manages connections to PostgreSQL
engine = create_engine(DATABASE_URL)

# Each instance of SessionLocal will be a single database transaction session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all database models to inherit from
Base = declarative_base()

# Dependency to provide a database session per HTTP request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()