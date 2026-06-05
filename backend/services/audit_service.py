"""审计日志服务 — 统一审计写入入口"""

import logging
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from models.audit import AuditLog

logger = logging.getLogger(__name__)


async def audit_log(
    db: AsyncSession,
    user_id: str,
    username: str,
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    detail: Optional[Any] = None,
    ip_address: Optional[str] = None,
):
    """
    写入审计日志 (非阻塞，异常不抛出)

    Args:
        db: 数据库会话
        user_id: 操作用户 ID
        username: 操作用户名
        action: CREATE / UPDATE / DELETE
        resource: pool / subnet / lease / tag / user
        resource_id: 资源 ID (可选)
        detail: JSON-serializable 详情 (可选)
        ip_address: 客户端 IP (可选)
    """
    try:
        entry = AuditLog(
            user_id=str(user_id),
            username=username,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id else None,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        # 不 await flush — 由外层事务提交
        logger.debug(f"审计: {action} {resource}#{resource_id} by {username}")
    except Exception as e:
        logger.error(f"审计写入失败: {e}")
