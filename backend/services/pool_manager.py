"""
地址池管理器 — 核心分配/回收/统计逻辑

负责:
- 查找匹配 VLAN 的地址池
- 从子网中分配 IP (排除已用+排除范围+预留)
- 回收过期 IP
- 统计池用量 (空闲/已用/总数)
"""

import ipaddress
import logging
from typing import Optional, List, Tuple, Dict
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.pool import AddressPool, Subnet, AddressExclude, AddressReservation
from models.lease import DHCPLease, LeaseState

logger = logging.getLogger(__name__)


class PoolManager:
    """地址池业务逻辑"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_pool_by_vlan(self, vlan_id: Optional[int]) -> Optional[AddressPool]:
        """
        根据 VLAN ID 查找匹配的地址池

        匹配策略:
        1. 精确匹配 VLAN ID
        2. 如果无匹配，使用 vlan_fallback=True 的默认池
        """
        # 精确匹配
        stmt = select(AddressPool).where(
            AddressPool.enabled == True,
            AddressPool.vlan_ids.contains([vlan_id]) if vlan_id is not None else True
        )
        result = await self.session.execute(stmt)
        pool = result.scalars().first()

        if pool:
            return pool

        # 回退到默认池
        if vlan_id is not None:
            stmt = select(AddressPool).where(
                AddressPool.enabled == True,
                AddressPool.vlan_fallback == True
            )
            result = await self.session.execute(stmt)
            pool = result.scalars().first()

        return pool

    async def get_pools_with_stats(self) -> List[Dict]:
        """获取所有地址池及其统计数据"""
        pools = (await self.session.execute(
            select(AddressPool).where(AddressPool.enabled == True)
        )).scalars().all()

        result = []
        for pool in pools:
            stats = await self.get_pool_stats(pool.id)
            result.append({
                "id": str(pool.id),
                "name": pool.name,
                "vlan_ids": pool.vlan_ids,
                "vlan_fallback": pool.vlan_fallback,
                "description": pool.description,
                "stats": stats,
                "subnet_count": len(pool.subnets),
                "reservation_count": len(pool.reservations),
            })

        return result

    async def get_pool_stats(self, pool_id: UUID) -> Dict:
        """计算指定地址池的用量统计"""
        # 获取池及其子网
        pool_result = await self.session.execute(
            select(AddressPool).where(AddressPool.id == pool_id)
        )
        pool = pool_result.scalars().first()
        if not pool:
            return {}

        total_capacity = 0
        total_used = 0
        total_reserved = 0
        total_excluded = 0
        subnet_details = []

        for subnet in pool.subnets:
            # 总容量 = range_end - range_start + 1
            start = ipaddress.ip_address(subnet.range_start)
            end = ipaddress.ip_address(subnet.range_end)
            capacity = int(end) - int(start) + 1
            total_capacity += capacity

            # 排除地址数
            excluded = 0
            for exc in subnet.excludes:
                exc_start = ipaddress.ip_address(exc.exclude_start)
                exc_end = ipaddress.ip_address(exc.exclude_end)
                excluded += int(exc_end) - int(exc_start) + 1
            total_excluded += excluded

            # 已用地址数
            used_result = await self.session.execute(
                select(func.count(DHCPLease.mac_address)).where(
                    DHCPLease.pool_id == pool_id,
                    DHCPLease.state == LeaseState.ACTIVE,
                    DHCPLease.dhcpv4_address.op(">>=")(subnet.subnet)
                )
            )
            used = used_result.scalar() or 0
            total_used += used

            subnet_details.append({
                "id": str(subnet.id),
                "subnet": str(subnet.subnet),
                "netmask": subnet.netmask,
                "gateway": str(subnet.gateway) if subnet.gateway else None,
                "range": f"{subnet.range_start} - {subnet.range_end}",
                "capacity": capacity,
                "used": used,
                "excluded": excluded,
                "available": capacity - used - excluded,
                "usage_percent": round((used / (capacity - excluded)) * 100, 2) if (capacity - excluded) > 0 else 0,
            })

        # 预留地址数
        res_result = await self.session.execute(
            select(func.count(AddressReservation.id)).where(
                AddressReservation.pool_id == pool_id,
                AddressReservation.enabled == True
            )
        )
        total_reserved = res_result.scalar() or 0

        total_free = total_capacity - total_used - total_excluded

        return {
            "total_capacity": total_capacity,
            "total_used": total_used,
            "total_free": total_free,
            "total_excluded": total_excluded,
            "total_reserved": total_reserved,
            "usage_percent": round((total_used / total_capacity) * 100, 2) if total_capacity > 0 else 0,
            "subnets": subnet_details,
        }

    async def allocate_ipv4(
        self, pool_id: UUID, mac_address: str, vlan_id: Optional[int] = None
    ) -> Optional[str]:
        """
        为指定 MAC 分配 IPv4 地址

        分配策略:
        1. 检查是否有预留地址
        2. 按子网顺序分配，跳过排除范围
        3. 跳过已分配且活跃的地址
        """
        # 检查预留
        reservation = (await self.session.execute(
            select(AddressReservation).where(
                AddressReservation.pool_id == pool_id,
                AddressReservation.mac_address == mac_address,
                AddressReservation.enabled == True
            )
        )).scalars().first()

        if reservation and reservation.reserved_ipv4:
            # 验证预留地址未被占用
            existing = (await self.session.execute(
                select(DHCPLease).where(
                    DHCPLease.dhcpv4_address == reservation.reserved_ipv4,
                    DHCPLease.state == LeaseState.ACTIVE,
                    DHCPLease.mac_address != mac_address
                )
            )).scalars().first()

            if not existing:
                logger.info(f"分配预留 IPv4: {reservation.reserved_ipv4} → MAC={mac_address}")
                return str(reservation.reserved_ipv4)

        # 遍历子网分配
        pool = (await self.session.execute(
            select(AddressPool).where(AddressPool.id == pool_id)
        )).scalars().first()

        for subnet in pool.subnets:
            if subnet.ip_version != 4:
                continue

            ip = await self._allocate_from_subnet(subnet, mac_address)
            if ip:
                return ip

        logger.warning(f"地址池 {pool.name} 无可分配 IPv4 地址")
        return None

    async def _allocate_from_subnet(self, subnet: Subnet, mac_address: str) -> Optional[str]:
        """从子网范围内分配 IP"""
        start = ipaddress.IPv4Address(subnet.range_start)
        end = ipaddress.IPv4Address(subnet.range_end)

        # 收集排除范围
        exclude_ranges = []
        for exc in subnet.excludes:
            exc_start = ipaddress.IPv4Address(exc.exclude_start)
            exc_end = ipaddress.IPv4Address(exc.exclude_end)
            exclude_ranges.append((int(exc_start), int(exc_end)))

        # 收集已分配的 IP
        active_ips_result = await self.session.execute(
            select(DHCPLease.dhcpv4_address).where(
                DHCPLease.state == LeaseState.ACTIVE,
                DHCPLease.mac_address != mac_address
            )
        )
        active_ips = set(str(ip) for ip, in active_ips_result.all() if ip)

        # 线性扫描分配 (50万+ 场景考虑改用 bitmap)
        for offset in range(int(end) - int(start) + 1):
            candidate = ipaddress.IPv4Address(int(start) + offset)
            candidate_int = int(candidate)
            candidate_str = str(candidate)

            # 跳过排除范围
            if any(lo <= candidate_int <= hi for lo, hi in exclude_ranges):
                continue

            # 跳过已分配
            if candidate_str in active_ips:
                continue

            return candidate_str

        return None

    async def release_ipv4(self, mac_address: str) -> bool:
        """释放指定 MAC 的 IPv4 租约"""
        result = await self.session.execute(
            select(DHCPLease).where(
                DHCPLease.mac_address == mac_address,
                DHCPLease.state == LeaseState.ACTIVE
            )
        )
        lease = result.scalars().first()
        if lease:
            lease.state = LeaseState.RELEASED
            lease.dhcpv4_lease_end = datetime.now(timezone.utc)
            await self.session.flush()
            logger.info(f"释放 IPv4 租约: MAC={mac_address}")
            return True
        return False

    async def allocate_ipv6(
        self, pool_id: UUID, client_id: str, vlan_id: Optional[int] = None
    ) -> Optional[str]:
        """
        为指定客户端分配 IPv6 地址
        
        从 IPv6 子网中按顺序分配
        """
        # 检查预留
        reservation = (await self.session.execute(
            select(AddressReservation).where(
                AddressReservation.pool_id == pool_id,
                AddressReservation.mac_address == client_id,
                AddressReservation.enabled == True
            )
        )).scalars().first()

        if reservation and reservation.reserved_ipv6:
            return str(reservation.reserved_ipv6)

        # 遍历 IPv6 子网
        pool = (await self.session.execute(
            select(AddressPool).where(AddressPool.id == pool_id)
        )).scalars().first()

        for subnet in pool.subnets:
            if subnet.ip_version != 6:
                continue

            # 收集已分配的 v6 地址
            active_v6_result = await self.session.execute(
                select(DHCPLease.dhcpv6_address).where(
                    DHCPLease.state == LeaseState.ACTIVE,
                    DHCPLease.dhcpv6_address.isnot(None)
                )
            )
            active_v6 = set(str(ip) for ip, in active_v6_result.all() if ip)

            # 从 range_start 开始分配
            start = ipaddress.IPv6Address(subnet.range_start)
            end = ipaddress.IPv6Address(subnet.range_end)

            for offset in range(int(end) - int(start) + 1):
                candidate = ipaddress.IPv6Address(int(start) + offset)
                candidate_str = str(candidate)

                if candidate_str not in active_v6:
                    return candidate_str

        logger.warning(f"地址池 无可分配 IPv6 地址")
        return None

    async def cleanup_expired(self) -> int:
        """清理过期租约，返回清理数量"""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(DHCPLease).where(
                DHCPLease.state == LeaseState.ACTIVE,
                DHCPLease.dhcpv4_lease_end < now
            )
        )
        expired = result.scalars().all()

        for lease in expired:
            lease.state = LeaseState.EXPIRED

        await self.session.flush()
        logger.info(f"清理过期租约: {len(expired)} 条")
        return len(expired)
