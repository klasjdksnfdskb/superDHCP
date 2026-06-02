"""
管理员账户 ORM 模型 — 多用户 + 角色权限
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from .database import Base

import enum


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # 超级管理员：所有权限
    ADMIN = "admin"            # 管理员：管理池/租约/标签/用户
    VIEWER = "viewer"          # 观察者：只读权限


class User(Base):
    """管理员账户"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(128), nullable=True)
    email = Column(String(255), nullable=True)

    role = Column(
        SAEnum(UserRole, name="user_role_enum", create_type=False),
        default=UserRole.VIEWER, nullable=False
    )

    is_active = Column(Boolean, default=True, comment="账户启用/禁用")
    require_password_change = Column(Boolean, default=False, comment="强制修改密码")

    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} role={self.role}>"


class AuditLog(Base):
    """操作审计日志"""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    username = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, comment="操作类型: login/logout/create_pool/...")
    resource_type = Column(String(64), nullable=True, comment="资源类型: pool/lease/tag/user")
    resource_id = Column(String(255), nullable=True, comment="资源标识")
    detail = Column(String(1024), nullable=True, comment="操作详情 JSON")
    ip_address = Column(String(45), nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow,
        nullable=False, index=True
    )
