"""
租约 ORM 模型 — superDHCP 核心数据表
以 MAC 地址作为基准条目，一行关联 DHCPv4 和 DHCPv6 全量信息
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime,
    ForeignKey, Index, Enum as SAEnum, Text
)
from sqlalchemy.dialects.postgresql import INET, UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from .database import Base

import enum


class LeaseState(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"
    DECLINED = "declined"


class DHCPv6Mode(str, enum.Enum):
    STATEFUL = "stateful"        # 有状态自动分配 (通过 DHCPv6 服务器)
    STATELESS = "stateless"      # 无状态自动分配 (RA + DHCPv6 仅信息)
    SLAAC = "slaac"              # SLAAC (仅 RA，无 DHCPv6 参与)
    MANUAL = "manual"            # 手动配置


class DHCPLease(Base):
    """
    DHCP 租约主表 — 一条记录 = 一个终端用户
    
    ┌─ DHCPv4 字段 ──────────────────
    │  地址/掩码/网关/DNS/租期
    │
    ├─ DHCPv6 字段 ──────────────────
    │  地址/前缀/DUID/IAID/模式/租期
    │
    ├─ 标识字段 ─────────────────────
    │  MAC / VLAN / 主机名
    │
    ├─ 扩展字段 ─────────────────────
    │  Option43/82 / 自定义标签 / 关联地址池
    │
    └─ 审计字段 ─────────────────────
       状态 / 首次发现 / 最后更新
    """

    __tablename__ = "dhcp_leases"

    # ── 主键：MAC 地址作为基准 ──
    mac_address = Column(
        String(17), primary_key=True,
        comment="MAC 地址 (xx:xx:xx:xx:xx:xx) — 基准条目"
    )

    # ── DHCPv4 信息 ──
    dhcpv4_address = Column(INET, nullable=True, comment="分配的 IPv4 地址")
    dhcpv4_netmask = Column(INET, nullable=True, comment="IPv4 子网掩码")
    dhcpv4_gateway = Column(INET, nullable=True, comment="IPv4 默认网关")
    dhcpv4_dns = Column(ARRAY(INET), nullable=True, comment="IPv4 DNS 服务器列表")
    dhcpv4_lease_start = Column(DateTime(timezone=True), nullable=True, comment="v4 租约开始时间")
    dhcpv4_lease_end = Column(DateTime(timezone=True), nullable=True, comment="v4 租约到期时间")
    dhcpv4_lease_time = Column(Integer, nullable=True, comment="v4 租期(秒)")

    # ── DHCPv6 信息 ──
    dhcpv6_address = Column(INET, nullable=True, comment="分配的 IPv6 地址")
    dhcpv6_prefix_len = Column(Integer, nullable=True, comment="IPv6 前缀长度")
    dhcpv6_duid = Column(String(128), nullable=True, comment="DHCPv6 DUID (客户端唯一标识)")
    dhcpv6_iaid = Column(Integer, nullable=True, comment="IAID (身份关联标识)")
    dhcpv6_mode = Column(
        SAEnum(DHCPv6Mode, name="dhcpv6_mode_enum", create_type=False),
        nullable=True,
        comment="DHCPv6 获取方式: stateful/stateless/slaac/manual"
    )
    dhcpv6_lease_start = Column(DateTime(timezone=True), nullable=True, comment="v6 租约开始时间")
    dhcpv6_lease_end = Column(DateTime(timezone=True), nullable=True, comment="v6 租约到期时间")
    dhcpv6_lease_time = Column(Integer, nullable=True, comment="v6 租期(秒)")

    # ── 客户端标识 ──
    vlan_id = Column(Integer, nullable=True, index=True, comment="客户端 VLAN ID")
    hostname = Column(String(255), nullable=True, comment="客户端主机名 (Option 12)")
    client_vendor = Column(String(128), nullable=True, comment="客户端厂商 (Option 60)")
    relay_agent = Column(INET, nullable=True, comment="DHCP 中继代理 IP")

    # ── 扩展标签 ──
    option43 = Column(JSONB, nullable=True, comment="Option 43 (厂商自定义信息)")
    option82 = Column(JSONB, nullable=True, comment="Option 82 (中继代理信息: Circuit/Remote ID)")
    option60 = Column(Text, nullable=True, comment="Option 60 (Vendor Class Identifier)")

    # ── 关联 ──
    pool_id = Column(
        UUID(as_uuid=True), ForeignKey("address_pools.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="所属地址池 ID"
    )
    custom_tag_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_tags.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="自定义组织架构标签 ID"
    )

    # ── 状态 & 审计 ──
    state = Column(
        SAEnum(LeaseState, name="lease_state_enum", create_type=False),
        default=LeaseState.ACTIVE, nullable=False, index=True,
        comment="租约状态"
    )
    first_seen = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
        comment="首次发现时间"
    )
    last_updated = Column(
        DateTime(timezone=True), default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False, comment="最后更新时间"
    )

    # ── 关系 ──
    pool = relationship("AddressPool", back_populates="leases", lazy="selectin")
    custom_tag = relationship("CustomTag", back_populates="leases", lazy="selectin")

    # ── 综合索引 ──
    __table_args__ = (
        Index("idx_leases_v4_ip", "dhcpv4_address"),
        Index("idx_leases_v6_ip", "dhcpv6_address"),
        Index("idx_leases_vlan_pool", "vlan_id", "pool_id"),
        Index("idx_leases_state_expire", "state", "dhcpv4_lease_end"),
        Index("idx_leases_tag", "custom_tag_id"),
        Index("idx_leases_last_updated", "last_updated"),
    )

    def __repr__(self):
        return f"<Lease MAC={self.mac_address} v4={self.dhcpv4_address} v6={self.dhcpv6_address}>"