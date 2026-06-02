"""
租约生命周期管理器

负责:
- 创建/更新/续租/释放租约记录
- 批量写入数据库 (性能优化)
- CSV 流式导出
- 多维度查询 (MAC/IP/VLAN/TAG/状态)
"""

import csv
import io
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.lease import DHCPLease, LeaseState, DHCPv6Mode
from models.pool import Subnet

logger = logging.getLogger(__name__)


class LeaseManager:
    """租约管理业务逻辑"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── 创建 & 更新租约 ───

    async def create_or_update_lease(
        self,
        mac_address: str,
        pool_id: UUID,
        subnet: Subnet,
        dhcpv4_address: str,
        lease_time: int,
        vlan_id: Optional[int] = None,
        hostname: Optional[str] = None,
        vendor_class: Optional[str] = None,
        option43: Optional[str] = None,
        circuit_id: Optional[str] = None,
        remote_id: Optional[str] = None,
        relay_agent: Optional[str] = None,
    ) -> DHCPLease:
        """创建或更新 DHCPv4 租约"""
        now = datetime.now(timezone.utc)
        lease_end = now + timedelta(seconds=lease_time)

        # 查找现有租约
        result = await self.session.execute(
            select(DHCPLease).where(DHCPLease.mac_address == mac_address)
        )
        lease = result.scalars().first()

        if lease:
            # 更新现有租约
            lease.dhcpv4_address = dhcpv4_address
            lease.dhcpv4_netmask = subnet.netmask
            lease.dhcpv4_gateway = str(subnet.gateway) if subnet.gateway else None
            lease.dhcpv4_lease_start = now
            lease.dhcpv4_lease_end = lease_end
            lease.dhcpv4_lease_time = lease_time
            lease.state = LeaseState.ACTIVE
        else:
            # 创建新租约
            lease = DHCPLease(
                mac_address=mac_address,
                dhcpv4_address=dhcpv4_address,
                dhcpv4_netmask=subnet.netmask,
                dhcpv4_gateway=str(subnet.gateway) if subnet.gateway else None,
                dhcpv4_lease_start=now,
                dhcpv4_lease_end=lease_end,
                dhcpv4_lease_time=lease_time,
                pool_id=pool_id,
                state=LeaseState.ACTIVE,
                first_seen=now,
            )
            self.session.add(lease)

        # 公共字段
        if vlan_id is not None:
            lease.vlan_id = vlan_id
        if hostname:
            lease.hostname = hostname
        if vendor_class:
            lease.client_vendor = vendor_class

        # Option 43/82
        if option43:
            lease.option43 = {"raw": option43}
        if circuit_id or remote_id:
            lease.option82 = {
                "circuit_id": circuit_id,
                "remote_id": remote_id,
            }
        if relay_agent:
            lease.relay_agent = relay_agent

        lease.last_updated = now
        await self.session.flush()
        return lease

    async def update_dhcpv6_lease(
        self,
        mac_address: Optional[str],
        duid: str,
        iaid: int,
        dhcpv6_address: str,
        lease_time: int,
        mode: str,
        pool_id: UUID,
    ):
        """更新 DHCPv6 有状态租约"""
        now = datetime.now(timezone.utc)
        lease_end = now + timedelta(seconds=lease_time)

        lease = await self._get_or_create_lease(mac_address, duid, pool_id)

        lease.dhcpv6_address = dhcpv6_address
        lease.dhcpv6_duid = duid
        lease.dhcpv6_iaid = iaid
        lease.dhcpv6_mode = DHCPv6Mode.STATEFUL
        lease.dhcpv6_lease_start = now
        lease.dhcpv6_lease_end = lease_end
        lease.dhcpv6_lease_time = lease_time
        lease.state = LeaseState.ACTIVE
        lease.last_updated = now

        await self.session.flush()

    async def update_dhcpv6_stateless(
        self,
        mac_address: Optional[str],
        duid: str,
        pool_id: UUID,
    ):
        """更新 DHCPv6 无状态记录"""
        now = datetime.now(timezone.utc)

        lease = await self._get_or_create_lease(mac_address, duid, pool_id)

        lease.dhcpv6_duid = duid
        lease.dhcpv6_mode = DHCPv6Mode.STATELESS
        lease.dhcpv6_lease_start = now
        lease.dhcpv6_lease_end = now + timedelta(seconds=86400)
        lease.last_updated = now
        lease.state = LeaseState.ACTIVE

        await self.session.flush()

    async def renew_dhcpv6(self, mac_address: Optional[str], duid: str, address: str):
        """续租 DHCPv6"""
        now = datetime.now(timezone.utc)

        lease = await self._get_or_create_lease(mac_address, duid)
        if lease and lease.dhcpv6_lease_end:
            # 延长租期
            lease.dhcpv6_lease_end = now + timedelta(seconds=(lease.dhcpv6_lease_time or 86400))
            lease.last_updated = now
            await self.session.flush()

    async def release_dhcpv6(self, mac_address: Optional[str], duid: str):
        """释放 DHCPv6 租约"""
        result = await self.session.execute(
            select(DHCPLease).where(
                DHCPLease.dhcpv6_duid == duid,
                DHCPLease.state == LeaseState.ACTIVE
            )
        )
        lease = result.scalars().first()
        if lease:
            lease.state = LeaseState.RELEASED
            lease.dhcpv6_lease_end = datetime.now(timezone.utc)
            await self.session.flush()

    async def _get_or_create_lease(
        self, mac_address: Optional[str], duid: str, pool_id: Optional[UUID] = None
    ) -> DHCPLease:
        """查找或创建租约记录"""
        if mac_address:
            result = await self.session.execute(
                select(DHCPLease).where(DHCPLease.mac_address == mac_address)
            )
            lease = result.scalars().first()
            if lease:
                return lease

        if duid:
            result = await self.session.execute(
                select(DHCPLease).where(DHCPLease.dhcpv6_duid == duid)
            )
            lease = result.scalars().first()
            if lease:
                return lease

        # 创建新记录
        lease = DHCPLease(
            mac_address=mac_address or f"DUID:{duid[:12]}",
            dhcpv6_duid=duid,
            pool_id=pool_id,
            first_seen=datetime.now(timezone.utc),
        )
        self.session.add(lease)
        return lease

    # ─── 查询 ───

    async def get_leases(
        self,
        page: int = 1,
        page_size: int = 50,
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
    ) -> Dict[str, Any]:
        """多维度租约查询 (分页)"""
        stmt = select(DHCPLease).options(
            selectinload(DHCPLease.pool),
            selectinload(DHCPLease.custom_tag),
        )

        # 过滤条件
        filters = []

        if mac:
            filters.append(DHCPLease.mac_address.ilike(f"%{mac}%"))
        if ipv4:
            filters.append(DHCPLease.dhcpv4_address.op(">>")(ipv4))
        if ipv6:
            filters.append(DHCPLease.dhcpv6_address.op(">>")(ipv6))
        if vlan_id is not None:
            filters.append(DHCPLease.vlan_id == vlan_id)
        if state:
            filters.append(DHCPLease.state == state)
        if tag_id:
            filters.append(DHCPLease.custom_tag_id == tag_id)
        if pool_id:
            filters.append(DHCPLease.pool_id == pool_id)
        if search:
            filters.append(or_(
                DHCPLease.mac_address.ilike(f"%{search}%"),
                DHCPLease.hostname.ilike(f"%{search}%"),
                DHCPLease.dhcpv4_address.cast(text("text")).ilike(f"%{search}%"),
            ))

        if filters:
            stmt = stmt.where(and_(*filters))

        # 排序
        sort_col = getattr(DHCPLease, sort_by, DHCPLease.last_updated)
        if sort_desc:
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        # 总数
        count_stmt = select(func.count()).select_from(DHCPLease)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.session.execute(stmt)
        leases = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": [self._lease_to_dict(l) for l in leases],
        }

    async def get_lease_by_mac(self, mac_address: str) -> Optional[Dict]:
        """根据 MAC 获取单条租约详情"""
        result = await self.session.execute(
            select(DHCPLease)
            .options(selectinload(DHCPLease.pool), selectinload(DHCPLease.custom_tag))
            .where(DHCPLease.mac_address == mac_address)
        )
        lease = result.scalars().first()
        return self._lease_to_dict(lease) if lease else None

    def _lease_to_dict(self, lease: DHCPLease) -> Dict:
        """租约 ORM → 字典"""
        tag_path = None
        if lease.custom_tag:
            tag_path = lease.custom_tag.get_full_path()

        return {
            "mac_address": lease.mac_address,
            # DHCPv4
            "dhcpv4_address": str(lease.dhcpv4_address) if lease.dhcpv4_address else None,
            "dhcpv4_netmask": str(lease.dhcpv4_netmask) if lease.dhcpv4_netmask else None,
            "dhcpv4_gateway": str(lease.dhcpv4_gateway) if lease.dhcpv4_gateway else None,
            "dhcpv4_dns": [str(d) for d in lease.dhcpv4_dns] if lease.dhcpv4_dns else None,
            "dhcpv4_lease_start": lease.dhcpv4_lease_start.isoformat() if lease.dhcpv4_lease_start else None,
            "dhcpv4_lease_end": lease.dhcpv4_lease_end.isoformat() if lease.dhcpv4_lease_end else None,
            "dhcpv4_lease_time": lease.dhcpv4_lease_time,
            # DHCPv6
            "dhcpv6_address": str(lease.dhcpv6_address) if lease.dhcpv6_address else None,
            "dhcpv6_prefix_len": lease.dhcpv6_prefix_len,
            "dhcpv6_duid": lease.dhcpv6_duid,
            "dhcpv6_iaid": lease.dhcpv6_iaid,
            "dhcpv6_mode": lease.dhcpv6_mode.value if lease.dhcpv6_mode else None,
            "dhcpv6_lease_start": lease.dhcpv6_lease_start.isoformat() if lease.dhcpv6_lease_start else None,
            "dhcpv6_lease_end": lease.dhcpv6_lease_end.isoformat() if lease.dhcpv6_lease_end else None,
            "dhcpv6_lease_time": lease.dhcpv6_lease_time,
            # Identity
            "vlan_id": lease.vlan_id,
            "hostname": lease.hostname,
            "client_vendor": lease.client_vendor,
            # Tags
            "option43": lease.option43,
            "option82": lease.option82,
            "option60": lease.option60,
            # Relations
            "pool_name": lease.pool.name if lease.pool else None,
            "pool_id": str(lease.pool_id) if lease.pool_id else None,
            "custom_tag_id": str(lease.custom_tag_id) if lease.custom_tag_id else None,
            "custom_tag_path": tag_path,
            # Status
            "state": lease.state.value if lease.state else None,
            "first_seen": lease.first_seen.isoformat() if lease.first_seen else None,
            "last_updated": lease.last_updated.isoformat() if lease.last_updated else None,
        }

    # ─── CSV 导出 ───

    async def export_csv(
        self,
        filters: Optional[Dict] = None,
        max_rows: int = 100000,
    ) -> str:
        """
        流式导出 CSV

        输出列:
        MAC, DHCPv4, Mask, Gateway, v4_Start, v4_End, v4_LeaseTime,
        DHCPv6, PrefixLen, DUID, IAID, v6_Mode, v6_Start, v6_End, v6_LeaseTime,
        VLAN, Hostname, Option43, Option82,
        CustomTag_Path, Pool_Name, State, FirstSeen, LastUpdated
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # 表头
        writer.writerow([
            "MAC地址",
            "IPv4地址", "子网掩码", "默认网关",
            "v4租约开始", "v4租约到期", "v4租期(秒)",
            "IPv6地址", "前缀长度", "DUID", "IAID",
            "v6获取方式", "v6租约开始", "v6租约到期", "v6租期(秒)",
            "VLAN ID", "主机名", "客户端厂商",
            "Option43", "Option82",
            "组织架构标签", "地址池",
            "状态", "首次发现", "最后更新",
        ])

        # 流式查询
        stmt = select(DHCPLease).options(
            selectinload(DHCPLease.pool),
            selectinload(DHCPLease.custom_tag),
        )

        if filters:
            flt = []
            if "vlan_id" in filters:
                flt.append(DHCPLease.vlan_id == filters["vlan_id"])
            if "state" in filters:
                flt.append(DHCPLease.state == filters["state"])
            if "pool_id" in filters:
                flt.append(DHCPLease.pool_id == filters["pool_id"])
            if flt:
                stmt = stmt.where(and_(*flt))

        stmt = stmt.order_by(DHCPLease.last_updated.desc()).limit(max_rows)

        result = await self.session.execute(stmt)
        row_count = 0

        for lease in result.scalars():
            tag_path = lease.custom_tag.get_full_path() if lease.custom_tag else ""

            writer.writerow([
                lease.mac_address,
                str(lease.dhcpv4_address) if lease.dhcpv4_address else "",
                str(lease.dhcpv4_netmask) if lease.dhcpv4_netmask else "",
                str(lease.dhcpv4_gateway) if lease.dhcpv4_gateway else "",
                lease.dhcpv4_lease_start.isoformat() if lease.dhcpv4_lease_start else "",
                lease.dhcpv4_lease_end.isoformat() if lease.dhcpv4_lease_end else "",
                lease.dhcpv4_lease_time or "",
                str(lease.dhcpv6_address) if lease.dhcpv6_address else "",
                lease.dhcpv6_prefix_len or "",
                lease.dhcpv6_duid or "",
                lease.dhcpv6_iaid or "",
                lease.dhcpv6_mode.value if lease.dhcpv6_mode else "",
                lease.dhcpv6_lease_start.isoformat() if lease.dhcpv6_lease_start else "",
                lease.dhcpv6_lease_end.isoformat() if lease.dhcpv6_lease_end else "",
                lease.dhcpv6_lease_time or "",
                lease.vlan_id or "",
                lease.hostname or "",
                lease.client_vendor or "",
                str(lease.option43) if lease.option43 else "",
                str(lease.option82) if lease.option82 else "",
                tag_path,
                lease.pool.name if lease.pool else "",
                lease.state.value if lease.state else "",
                lease.first_seen.isoformat() if lease.first_seen else "",
                lease.last_updated.isoformat() if lease.last_updated else "",
            ])
            row_count += 1

        logger.info(f"CSV 导出完成: {row_count} 条记录")
        return output.getvalue()

    # ─── 统计 ───

    async def get_global_stats(self) -> Dict:
        """获取全局统计数据"""
        # 总数
        total_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address))
        )
        total = total_result.scalar() or 0

        # 活跃数
        active_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address)).where(
                DHCPLease.state == LeaseState.ACTIVE
            )
        )
        active = active_result.scalar() or 0

        # 今日新增
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        new_today_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address)).where(
                DHCPLease.first_seen >= today
            )
        )
        new_today = new_today_result.scalar() or 0

        # VLAN 分布
        vlan_dist_result = await self.session.execute(
            select(DHCPLease.vlan_id, func.count(DHCPLease.mac_address))
            .where(DHCPLease.state == LeaseState.ACTIVE)
            .group_by(DHCPLease.vlan_id)
            .order_by(func.count(DHCPLease.mac_address).desc())
            .limit(20)
        )
        vlan_distribution = [
            {"vlan_id": vlan, "count": count}
            for vlan, count in vlan_dist_result.all()
        ]

        # v4/v6 统计
        v4_active_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address)).where(
                DHCPLease.state == LeaseState.ACTIVE,
                DHCPLease.dhcpv4_address.isnot(None)
            )
        )

        v6_stateful_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address)).where(
                DHCPLease.state == LeaseState.ACTIVE,
                DHCPLease.dhcpv6_mode == DHCPv6Mode.STATEFUL
            )
        )

        v6_stateless_result = await self.session.execute(
            select(func.count(DHCPLease.mac_address)).where(
                DHCPLease.state == LeaseState.ACTIVE,
                DHCPLease.dhcpv6_mode == DHCPv6Mode.STATELESS
            )
        )

        return {
            "total_leases": total,
            "active_leases": active,
            "expired_leases": total - active,
            "new_today": new_today,
            "v4_active": v4_active_result.scalar() or 0,
            "v6_stateful": v6_stateful_result.scalar() or 0,
            "v6_stateless": v6_stateless_result.scalar() or 0,
            "vlan_distribution": vlan_distribution,
        }
