"""
自定义组织架构标签 ORM 模型 — 多层树形结构

设计理念:
- 服务端内部标签体系，客户端完全无感知
- 无限层级嵌套（如: 中国→省→市→区→机房→机架→交换机端口）
- 通过 Web 管理界面创建和编辑标签树
- 支持 CSV 导出时包含完整标签路径
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base


class CustomTag(Base):
    """
    自定义组织架构标签 — 支持多层嵌套
    
    使用 parent_id 自引用实现无限层级树：
        root (中国)
         ├─ child (广东省)
         │   ├─ grandchild (深圳市)
         │   │   └─ great-grandchild (南山区)
         │   └─ grandchild (广州市)
         └─ child (北京市)
    """

    __tablename__ = "custom_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, comment="标签名称")
    slug = Column(String(128), nullable=False, comment="标签唯一标识符 (URL-safe)")

    # ── 树形结构 ──
    parent_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_tags.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="父标签 ID (null = 根节点)"
    )
    level = Column(Integer, default=0, comment="层级深度 (0 = 根节点)")

    # ── 元数据 ──
    description = Column(Text, nullable=True, comment="标签描述")
    color = Column(String(7), nullable=True, comment="Web 显示颜色 (hex, 如 #FF5733)")
    icon = Column(String(64), nullable=True, comment="图标名称 (可选)")

    # ── 排序 ──
    sort_order = Column(Integer, default=0, comment="同级排序权重")

    # ── 审计 ──
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── 自引用关系 ──
    parent = relationship("CustomTag", remote_side=[id], back_populates="children")
    children = relationship(
        "CustomTag", back_populates="parent",
        cascade="all, delete-orphan",
        order_by="CustomTag.sort_order"
    )

    # ── 反向关系：租约 ──
    leases = relationship("DHCPLease", back_populates="custom_tag")

    __table_args__ = (
        UniqueConstraint("parent_id", "slug", name="uq_tag_slug_under_parent"),
    )

    def get_full_path(self) -> str:
        """获取完整标签路径，如 中国/广东省/深圳市/南山区"""
        parts = []
        node = self
        while node:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts))

    def get_ancestors(self):
        """获取所有祖先节点"""
        ancestors = []
        node = self.parent
        while node:
            ancestors.append(node)
            node = node.parent
        return list(reversed(ancestors))

    def __repr__(self):
        return f"<Tag {self.get_full_path()}>"


class TagCategory(Base):
    """
    标签分类 — 预定义顶层分类
    
    示例分类:
    - 地域位置 (国家/省份/城市/区县/街道)
    - 机房设施 (数据中心/机房/机柜/U位)
    - 业务归属 (部门/团队/项目)
    - 设备类型 (服务器/终端/IoT)
    """

    __tablename__ = "tag_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True, nullable=False, comment="分类名称")
    description = Column(Text, nullable=True)
    root_tag_id = Column(
        UUID(as_uuid=True), ForeignKey("custom_tags.id", ondelete="SET NULL"),
        nullable=True, comment="关联的根标签"
    )
    max_depth = Column(Integer, default=10, comment="最大层级深度")
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)