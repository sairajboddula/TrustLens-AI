"""
API v1 package – re-exports the main api_router.
"""

from app.api.v1.router import api_router

__all__ = ["api_router"]
