from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.db import models

app = FastAPI(
    title="Micro Influencer Outreach API",
    description="AI-powered influencer discovery and outreach system",
    version="1.0.0"
)

@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "Micro Influencer Outreach System",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }