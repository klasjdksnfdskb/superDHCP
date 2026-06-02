"""
地址池 ORM 模型 — 支持多池 + VLAN 绑定 + 预留地址 + 子网划分
"""

import uuid
import ipaddress
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey,
    Index, Boolean, Text
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, ARRAY
from sqlalchemy.orm import relationship
from .database import Base


class AddressPool(Base):
    """
    地址池 — DHCP 地址分配的核心配置单元
    
    配置流程:
    1. 创建 Pool (名称、描述)
    2. 添加 Subnet (网段、掩码、网关、DNS)
    3. 设置 VLAN 绑定规则
    4. 配置排除范围 & 预留地址
    """

    __tablename__ = "address_pools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), unique=True, nullable=False, comment="地址池名称")
    description = Column(Text, nullable=True, comment="地址池描述")

    # ── VLAN 绑定 ──
    vlan_ids = Column(
        ARRAY(Integer), nullable=True,
        comment="绑定的 VLAN ID 列表，空数组表示匹配所有未绑定 VLAN"
    )
    vlan_fallback = Column(
        Boolean, default=False,
        comment="作为默认池 (当 VLAN 未匹配到任何池时使用)"
    )

    # ── 组织架构关联 ──
    tag_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_tags.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="关联的组织架构标签 (如: 深圳机房→3楼→机架A12)"
    )

    # ── 通用 DHCP 选项 ──
    domain_name = Column(String(255), nullable=True, comment="域名 (Option 15)")
    ntp_servers = Column(ARRAY(INET), nullable=True, comment="NTP 服务器 (Option 42)")
    bootfile = Column(String(255), nullable=True, comment="PXE 启动文件名 (Option 67)")
    next_server = Column(INET, nullable=True, comment="PXE TFTP 服务器 (Option 66)")

    # ── 状态 & 审计 ──
    enabled = Column(Boolean, default=True, comment="启用/禁用")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── 关系 ──
    subnets = relationship("Subnet", back_populates="pool", cascade="all, delete-orphan", lazy="selectin")
    reservations = relationship("AddressReservation", back_populates="pool", cascade="all, delete-orphan", lazy="selectin")
    leases = relationship("DHCPLease", back_populates="pool", lazy="selectin")
    tag = relationship("CustomTag", lazy="selectin")

    def __repr__(self):
        return f"<Pool {self.name} VLANs={self.vlan_ids}>"


class Subnet(Base):
    """
    子网 — 定义 IP 网段范围
    
    支持 IPv4 和 IPv6 子网
    """

    __tablename__ = "subnets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id = Column(
        UUID(as_uuid=True), ForeignKey("address_pools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # ── 网段定义 ──
    subnet = Column(INET, nullable=False, comment="网段地址 (如 10.0.0.0/24)")
    netmask = Column(String(45), nullable=False, comment="子网掩码 / 前缀长度")
    gateway = Column(INET, nullable=True, comment="默认网关")
    dns_servers = Column(ARRAY(INET), nullable=True, comment="DNS 服务器")

    # ── 地址范围 ──
    range_start = Column(INET, nullable=False, comment="可分配起始 IP")
    range_end = Column(INET, nullable=False, comment="可分配结束 IP")

    # ── DHCP 选项 ──
    ip_version = Column(Integer, default=4, comment="IP 版本: 4 或 6")
    lease_time = Column(Integer, nullable=True, comment="覆盖全局租期(秒)")
    option_data = Column(JSONB, nullable=True, comment="自定义 DHCP 选项")

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # ── 关系 ──
    pool = relationship("AddressPool", back_populates="subnets")
    excludes = relationship("AddressExclude", back_populates="subnet", cascade="all, delete-orphan", lazy="selectin")

    def get_network(self):
        """返回 ipaddress 网络对象"""
        if self.ip_version == 4:
            return ipaddress.IPv4Network(f"{self.subnet}/{self.netmask}")
        return ipaddress.IPv6Network(f"{self.subnet}/{self.netmask}")

    @property
    def total_addresses(self):
        """地址池总容量"""
        net = self.get_network()
        return net.num_addresses

    @property
    def available_range(self):
        """返回 (range_start, range_end) 作为 ipaddress 对象"""
        if self.ip_version == 4:
            return (ipaddress.IPv4Address(self.range_start),
                    ipaddress.IPv4Address(self.range_end))
        return (ipaddress.IPv6Address(self.range_start),
                ipaddress.IPv6Address(self.range_end))

    def __repr__(self):
        return f"<Subnet {self.subnet}/{self.netmask}>"


class AddressExclude(Base):
    """地址排除范围 — 池中需要跳过不分配的 IP 段"""

    __tablename__ = "address_excludes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subnet_id = Column(
        UUID(as_uuid=True), ForeignKey("subnets.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    exclude_start = Column(INET, nullable=False, comment="排除起始 IP")
    exclude_end = Column(INET, nullable=False, comment="排除结束 IP")
    reason = Column(String(255), nullable=True, comment="排除原因（如网关/服务器保留）")

    subnet = relationship("Subnet", back_populates="excludes")


class AddressReservation(Base):
    """
    预留地址 — 为特定 MAC 保留固定 IP
    
    适用于服务器、打印机等需要固定 IP 的设备
    """

    __tablename__ = "address_reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id = Column(
        UUID(as_uuid=True), ForeignKey("address_pools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    mac_address = Column(String(17), nullable=False, comment="绑定 MAC 地址")
    reserved_ipv4 = Column(INET, nullable=True, comment="保留的 IPv4 地址")
    reserved_ipv6 = Column(INET, nullable=True, comment="保留的 IPv6 地址")
    description = Column(Text, nullable=True, comment="备注（如打印机-三楼）")
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    pool = relationship("AddressPool", back_populates="reservations")

    # 索引：快速按 MAC 查找预留
    __table_args__ = (
        Index("idx_reservation_mac", "pool_id", "mac_address", unique=True),
    )

    def __repr__(self):
        return f"<Reservation MAC={self.mac_address} v4={self.reserved_ipv4}>"
