# Language: Python (services/ai-agent/main.py)
import os
import uuid
import time
from typing import Optional
from fastapi import FastAPI, APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# LangChain Bedrock integration
from langchain_aws import ChatBedrock
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

app = FastAPI(
    title="Finance Support AI Agent API",
    version="1.0.0",
    docs_url="/agent/docs",
    openapi_url="/agent/openapi.json"
)

# Mount all routes under /agent to match AWS ALB Ingress prefix routing
agent_router = APIRouter(prefix="/agent")

# ----------------- Prometheus AgentOps Metrics -----------------
AGENT_REQUEST_COUNT = Counter(
    "ai_agent_requests_total",
    "Total queries handled by the support AI agent",
    ["status"]
)

AGENT_INFERENCE_LATENCY = Histogram(
    "ai_agent_inference_duration_seconds",
    "Time spent in LLM inference and tool execution",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

AGENT_TOOL_CALL_COUNT = Counter(
    "ai_agent_tool_calls_total",
    "Total database diagnostic tool calls",
    ["tool_name", "status"]
)

# ----------------- Database Setup -----------------
DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    "postgresql://postgres:postgres@db:5432/finance_db"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ----------------- Agent Tools -----------------
@tool
def get_transaction_details(transaction_id: str) -> str:
    """Queries the database to fetch transaction status, amount, sender, and recipient by UUID."""
    db = SessionLocal()
    try:
        query = text(
            "SELECT id, amount, type, status, sender_id, recipient_id, timestamp "
            "FROM transactions WHERE id = :tx_id"
        )
        result = db.execute(query, {"tx_id": transaction_id.strip()}).mappings().first()
        AGENT_TOOL_CALL_COUNT.labels(tool_name="get_transaction_details", status="success").inc()
        if not result:
            return f"Transaction ID '{transaction_id}' was not found in the database."
        return (
            f"Transaction Record: ID={result['id']}, Amount=${result['amount']}, "
            f"Type={result['type']}, Status={result['status']}, "
            f"Sender={result['sender_id']}, Recipient={result['recipient_id']}, Time={result['timestamp']}"
        )
    except Exception as err:
        AGENT_TOOL_CALL_COUNT.labels(tool_name="get_transaction_details", status="error").inc()
        return f"Database query failure: {str(err)}"
    finally:
        db.close()

@tool
def analyze_account_failures(user_id: str) -> str:
    """Analyzes recent failed or pending transactions for a customer account ID."""
    db = SessionLocal()
    try:
        query = text(
            "SELECT id, amount, type, status, timestamp FROM transactions "
            "WHERE (sender_id = :uid OR recipient_id = :uid) AND status != 'completed' "
            "ORDER BY timestamp DESC LIMIT 5"
        )
        rows = db.execute(query, {"uid": user_id.strip()}).mappings().all()
        AGENT_TOOL_CALL_COUNT.labels(tool_name="analyze_account_failures", status="success").inc()
        if not rows:
            return f"Account '{user_id}' has no recent failed or pending transactions."
        summary = [
            f"ID: {r['id']}, Amount: ${r['amount']}, Status: {r['status']}, Time: {r['timestamp']}"
            for r in rows
        ]
        return f"Recent uncompleted transactions for account {user_id}:\n" + "\n".join(summary)
    except Exception as err:
        AGENT_TOOL_CALL_COUNT.labels(tool_name="analyze_account_failures", status="error").inc()
        return f"Diagnostic tool failure: {str(err)}"
    finally:
        db.close()

tools = [get_transaction_details, analyze_account_failures]

# ----------------- LLM Setup -----------------
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    region_name=AWS_REGION,
    model_kwargs={"temperature": 0.0, "max_tokens": 1024}
)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an internal Tier-2 Customer Support and DevOps AI Assistant for the Payments Platform. "
        "Diagnose transaction anomalies, inspect database records, and summarize root causes for human support agents. "
        "Base your responses strictly on the output of your tools."
    ),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ----------------- Schemas & Routes -----------------
class SupportQuery(BaseModel):
    query: str = Field(..., description="The support query or transaction check to analyze")
    session_id: Optional[str] = Field(default=None, description="Optional support session identifier")

class SupportResponse(BaseModel):
    response: str
    session_id: str
    latency_ms: float

@agent_router.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "support-ai-agent"}

@agent_router.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {str(e)}")

@agent_router.post("/chat", response_model=SupportResponse)
def handle_support_query(payload: SupportQuery):
    session_id = payload.session_id or str(uuid.uuid4())
    start_time = time.time()
    try:
        with AGENT_INFERENCE_LATENCY.time():
            result = agent_executor.invoke({"input": payload.query})
        
        AGENT_REQUEST_COUNT.labels(status="success").inc()
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return SupportResponse(
            response=result["output"],
            session_id=session_id,
            latency_ms=duration_ms
        )
    except Exception as e:
        AGENT_REQUEST_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=f"Agent inference failed: {str(e)}")

@agent_router.get("/metrics")
def get_metrics():
    """Exposes Prometheus AgentOps scrape target at /agent/metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Register router with FastAPI
app.include_router(agent_router)