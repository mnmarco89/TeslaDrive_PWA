import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
def serve_tesla_public_key():
    path = "static/.well-known/appspecific/com.tesla.3p.public-key.pem"
    if os.path.exists(path):
        return FileResponse(path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Public key file not found")
