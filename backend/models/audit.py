"""审计日志模型 — 记录所有 CRUD 操作"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON
from models.database import Base


class AuditLog(Base):
    """操作审计日志"""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    user_id = Column(String(36), nullable=False, index=True, comment="操作用户 ID")
    username = Column(String(64), nullable=False, comment="操作用户名")
    action = Column(String(32), nullable=False, index=True, comment="操作类型: CREATE/UPDATE/DELETE")
    resource = Column(String(64), nullable=False, index=True, comment="资源类型: pool/subnet/lease/tag/user")
    resource_id = Column(String(36), nullable=True, comment="资源 ID")
    detail = Column(JSON, nullable=True, comment="操作详情 (JSON)")
    ip_address = Column(String(45), nullable=True, comment="客户端 IP")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} {self.resource}#{self.resource_id} by {self.username}>"
