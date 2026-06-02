"""
Routers package — API 路由层
"""

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .pools import router as pools_router
from .leases import router as leases_router
from .tags import router as tags_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "pools_router",
    "leases_router",
    "tags_router",
    "users_router",
]
