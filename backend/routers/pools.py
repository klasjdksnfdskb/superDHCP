"""
地址池管理路由 — CRUD + 子网管理 + 预留地址
"""

from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.pool import AddressPool, Subnet, AddressExclude, AddressReservation
from models.user import User
from services.pool_manager import PoolManager
from .auth import get_current_user, require_admin

router = APIRouter(prefix="/api/pools", tags=["地址池管理"])


# ─── Pydantic Schemas ───

class SubnetCreate(BaseModel):
    subnet: str = Field(..., description="网段 (如 10.0.1.0)")
    netmask: str = Field(..., description="掩码/前缀长度 (如 24)")
    gateway: Optional[str] = None
    dns_servers: Optional[List[str]] = None
    range_start: str = Field(..., description="可分配起始 IP")
    range_end: str = Field(..., description="可分配结束 IP")
    ip_version: int = Field(default=4, ge=4, le=6)
    lease_time: Optional[int] = None
    option_data: Optional[dict] = None


class PoolCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    description: Optional[str] = None
    vlan_ids: Optional[List[int]] = None
    vlan_fallback: bool = False
    tag_id: Optional[str] = None  # UUID of CustomTag
    domain_name: Optional[str] = None
    ntp_servers: Optional[List[str]] = None
    bootfile: Optional[str] = None
    next_server: Optional[str] = None
    # 创建时可以同时定义子网
    subnets: Optional[List[SubnetCreate]] = None


class PoolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vlan_ids: Optional[List[int]] = None
    vlan_fallback: Optional[bool] = None
    domain_name: Optional[str] = None
    enabled: Optional[bool] = None


class ExcludeCreate(BaseModel):
    exclude_start: str
    exclude_end: str
    reason: Optional[str] = None


class ReservationCreate(BaseModel):
    mac_address: str = Field(..., min_length=12, max_length=17)
    reserved_ipv4: Optional[str] = None
    reserved_ipv6: Optional[str] = None
    description: Optional[str] = None


# ─── 路由 ───

@router.get("")
async def list_pools(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有地址池列表 (含统计)"""
    pool_mgr = PoolManager(db)
    return await pool_mgr.get_pools_with_stats()


@router.post("")
async def create_pool(
    req: PoolCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建地址池，可选包含子网配置"""
    existing = await db.execute(
        select(AddressPool).where(AddressPool.name == req.name)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Pool name already exists")

    # 验证 tag_id
    tag_uuid = None
    if req.tag_id:
        try:
            tag_uuid = UUID(req.tag_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tag_id")

    pool = AddressPool(
        name=req.name,
        description=req.description,
        vlan_ids=req.vlan_ids or [],
        vlan_fallback=req.vlan_fallback,
        tag_id=tag_uuid,
        domain_name=req.domain_name,
        ntp_servers=req.ntp_servers,
        bootfile=req.bootfile,
        next_server=req.next_server,
    )
    db.add(pool)
    await db.flush()

    # 可选：创建时直接添加子网
    created_subnets = []
    if req.subnets:
        for sn in req.subnets:
            subnet = Subnet(
                pool_id=pool.id,
                subnet=sn.subnet,
                netmask=sn.netmask,
                gateway=sn.gateway,
                dns_servers=sn.dns_servers,
                range_start=sn.range_start,
                range_end=sn.range_end,
                ip_version=sn.ip_version,
                lease_time=sn.lease_time,
                option_data=sn.option_data,
            )
            db.add(subnet)
            created_subnets.append(str(subnet.id))
        await db.flush()

    return {
        "id": str(pool.id),
        "name": pool.name,
        "subnets": created_subnets,
        "message": "Pool created"
    }


@router.get("/{pool_id}")
async def get_pool(
    pool_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取地址池详情 (含子网、排除、预留)"""
    result = await db.execute(
        select(AddressPool).where(AddressPool.id == pool_id)
    )
    pool = result.scalars().first()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    pool_mgr = PoolManager(db)
    stats = await pool_mgr.get_pool_stats(pool.id)

    return {
        "id": str(pool.id),
        "name": pool.name,
        "description": pool.description,
        "vlan_ids": pool.vlan_ids,
        "vlan_fallback": pool.vlan_fallback,
        "tag_id": str(pool.tag_id) if pool.tag_id else None,
        "tag_name": pool.tag.name if pool.tag else None,
        "domain_name": pool.domain_name,
        "enabled": pool.enabled,
        "stats": stats,
        "subnets": [
            {
                "id": str(s.id),
                "subnet": str(s.subnet),
                "netmask": s.netmask,
                "gateway": str(s.gateway) if s.gateway else None,
                "dns_servers": [str(d) for d in s.dns_servers] if s.dns_servers else None,
                "range_start": str(s.range_start),
                "range_end": str(s.range_end),
                "ip_version": s.ip_version,
                "lease_time": s.lease_time,
                "excludes": [
                    {"id": str(e.id), "start": str(e.exclude_start),
                     "end": str(e.exclude_end), "reason": e.reason}
                    for e in s.excludes
                ],
            }
            for s in pool.subnets
        ],
        "reservations": [
            {
                "id": str(r.id),
                "mac_address": r.mac_address,
                "reserved_ipv4": str(r.reserved_ipv4) if r.reserved_ipv4 else None,
                "reserved_ipv6": str(r.reserved_ipv6) if r.reserved_ipv6 else None,
                "description": r.description,
                "enabled": r.enabled,
            }
            for r in pool.reservations
        ],
    }


@router.put("/{pool_id}")
async def update_pool(
    pool_id: UUID,
    req: PoolUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新地址池"""
    result = await db.execute(select(AddressPool).where(AddressPool.id == pool_id))
    pool = result.scalars().first()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(pool, field, value)

    await db.flush()
    return {"message": "Pool updated"}


@router.delete("/{pool_id}")
async def delete_pool(
    pool_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除地址池"""
    result = await db.execute(select(AddressPool).where(AddressPool.id == pool_id))
    pool = result.scalars().first()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    await db.delete(pool)
    await db.flush()
    return {"message": "Pool deleted"}


# ─── 子网管理 ───

@router.post("/{pool_id}/subnets")
async def add_subnet(
    pool_id: UUID,
    req: SubnetCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """为地址池添加子网"""
    result = await db.execute(select(AddressPool).where(AddressPool.id == pool_id))
    pool = result.scalars().first()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    subnet = Subnet(
        pool_id=pool.id,
        subnet=req.subnet,
        netmask=req.netmask,
        gateway=req.gateway,
        dns_servers=req.dns_servers,
        range_start=req.range_start,
        range_end=req.range_end,
        ip_version=req.ip_version,
        lease_time=req.lease_time,
        option_data=req.option_data,
    )
    db.add(subnet)
    await db.flush()
    return {"id": str(subnet.id), "message": "Subnet added"}


@router.delete("/{pool_id}/subnets/{subnet_id}")
async def delete_subnet(
    pool_id: UUID,
    subnet_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除子网"""
    result = await db.execute(select(Subnet).where(Subnet.id == subnet_id))
    subnet = result.scalars().first()
    if not subnet:
        raise HTTPException(status_code=404, detail="Subnet not found")

    await db.delete(subnet)
    await db.flush()
    return {"message": "Subnet deleted"}


# ─── 排除范围 ───

@router.post("/subnets/{subnet_id}/excludes")
async def add_exclude(
    subnet_id: UUID,
    req: ExcludeCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """添加地址排除范围"""
    exclude = AddressExclude(
        subnet_id=subnet_id,
        exclude_start=req.exclude_start,
        exclude_end=req.exclude_end,
        reason=req.reason,
    )
    db.add(exclude)
    await db.flush()
    return {"id": str(exclude.id), "message": "Exclude range added"}


@router.delete("/excludes/{exclude_id}")
async def delete_exclude(
    exclude_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除排除范围"""
    result = await db.execute(select(AddressExclude).where(AddressExclude.id == exclude_id))
    exc = result.scalars().first()
    if not exc:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(exc)
    await db.flush()
    return {"message": "Exclude range deleted"}


# ─── 预留地址 ───

@router.post("/{pool_id}/reservations")
async def add_reservation(
    pool_id: UUID,
    req: ReservationCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """添加预留地址"""
    reservation = AddressReservation(
        pool_id=pool_id,
        mac_address=req.mac_address,
        reserved_ipv4=req.reserved_ipv4,
        reserved_ipv6=req.reserved_ipv6,
        description=req.description,
    )
    db.add(reservation)
    await db.flush()
    return {"id": str(reservation.id), "message": "Reservation added"}


@router.delete("/reservations/{reservation_id}")
async def delete_reservation(
    reservation_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除预留"""
    result = await db.execute(select(AddressReservation).where(AddressReservation.id == reservation_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(r)
    await db.flush()
    return {"message": "Reservation deleted"}