"""
租约管理路由 — 查询 / 导出 / 统计 / 操作
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from models.database import get_db
from models.user import User
from services.lease_manager import LeaseManager
from .auth import get_current_user, require_admin

router = APIRouter(prefix="/api/leases", tags=["租约管理"])


@router.get("")
async def list_leases(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    mac: Optional[str] = None,
    ipv4: Optional[str] = None,
    ipv6: Optional[str] = None,
    vlan_id: Optional[int] = None,
    state: Optional[str] = None,
    tag_id: Optional[UUID] = None,
    pool_id: Optional[UUID] = None,
    search: Optional[str] = None,
    sort_by: str = "last_updated",
    sort_desc: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    多维度租约查询 (分页)

    支持筛选: MAC / IPv4 / IPv6 / VLAN / 状态 / 标签 / 地址池 / 模糊搜索
    """
    lease_mgr = LeaseManager(db)
    return await lease_mgr.get_leases(
        page=page,
        page_size=page_size,
        mac=mac,
        ipv4=ipv4,
        ipv6=ipv6,
        vlan_id=vlan_id,
        state=state,
        tag_id=tag_id,
        pool_id=pool_id,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


@router.get("/export")
async def export_csv(
    vlan_id: Optional[int] = None,
    state: Optional[str] = "active",
    pool_id: Optional[UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出租约 CSV

    输出含所有字段: MAC, DHCPv4/v6 地址, 租期, DUID, 获取方式, 组织架构标签等
    """
    lease_mgr = LeaseManager(db)
    filters = {}
    if vlan_id:
        filters["vlan_id"] = vlan_id
    if state:
        filters["state"] = state
    if pool_id:
        filters["pool_id"] = pool_id

    csv_content = await lease_mgr.export_csv(filters=filters)

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=dhcp_leases_export.csv",
            "Content-Type": "text/csv; charset=utf-8-sig",
        }
    )


@router.get("/{mac_address}")
async def get_lease(
    mac_address: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单条租约详情 (按 MAC)"""
    lease_mgr = LeaseManager(db)
    lease = await lease_mgr.get_lease_by_mac(mac_address)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


@router.post("/{mac_address}/release")
async def release_lease(
    mac_address: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """手动释放租约"""
    from services.pool_manager import PoolManager
    pool_mgr = PoolManager(db)
    success = await pool_mgr.release_ipv4(mac_address)
    if success:
        return {"message": f"Lease for MAC={mac_address} released"}
    raise HTTPException(status_code=404, detail="No active lease found")


@router.get("/stats/summary")
async def get_lease_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取租约统计摘要"""
    lease_mgr = LeaseManager(db)
    return await lease_mgr.get_global_stats()