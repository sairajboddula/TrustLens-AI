"""
API v1 Router

Aggregates all sub-routers and mounts them under the /api/v1 prefix
(which is applied by main.py when it includes this router).
"""

from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.kyc import router as kyc_router
from app.api.v1.endpoints.workflow import router as workflow_router

# Primary v1 router – main.py mounts this at /api/v1
api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(kyc_router)
api_router.include_router(documents_router)
api_router.include_router(admin_router)
api_router.include_router(workflow_router)
