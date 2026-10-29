from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="SKYGRID API", version="0.1.0")

allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "skygrid-api"}

@app.get("/")
def root():
    return {"name": "SKYGRID", "message": "Your Files. Your Space.", "docs": "/docs"}

@app.get("/ready")
def ready():
    # Expand this when database and storage providers are configured.
    return JSONResponse({"ready": True, "database": "not_configured", "storage": "not_configured"})
