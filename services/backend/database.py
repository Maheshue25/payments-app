import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Format: postgresql://<username>:<password>@<host>:<port>/<database_name>
# Replace these with your actual PostgreSQL credentials
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/finance_db"
)

# Creates the engine that manages connections to PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)

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