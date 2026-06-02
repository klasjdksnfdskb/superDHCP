"""
仪表盘路由 — 实时 Dashboard 数据
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_db
from ..models.user import User
from ..services.lease_manager import LeaseManager
from ..services.pool_manager import PoolManager
from .auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取全局 Dashboard 统计数据"""
    lease_mgr = LeaseManager(db)
    pool_mgr = PoolManager(db)

    stats = await lease_mgr.get_global_stats()
    pools = await pool_mgr.get_pools_with_stats()

    return {
        **stats,
        "pools": pools,
        "pool_summary": {
            "count": len(pools),
            "total_capacity": sum(p["stats"].get("total_capacity", 0) for p in pools),
            "total_used": sum(p["stats"].get("total_used", 0) for p in pools),
            "total_free": sum(p["stats"].get("total_free", 0) for p in pools),
        },
    }


@router.get("/activity")
async def get_activity(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取最近 DHCP 活动摘要"""
    from ..models.lease import DHCPLease, LeaseState
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)

    # 最近1小时新增
    one_hour_ago = now - timedelta(hours=1)
    new_result = await db.execute(
        select(func.count(DHCPLease.mac_address)).where(
            DHCPLease.first_seen >= one_hour_ago
        )
    )

    # 最近24小时
    one_day_ago = now - timedelta(days=1)
    day_result = await db.execute(
        select(func.count(DHCPLease.mac_address)).where(
            DHCPLease.last_updated >= one_day_ago
        )
    )

    return {
        "new_last_hour": new_result.scalar() or 0,
        "active_last_24h": day_result.scalar() or 0,
        "server_time": now.isoformat(),
        "dhcpv4_enabled": True,
        "dhcpv6_enabled": True,
    }