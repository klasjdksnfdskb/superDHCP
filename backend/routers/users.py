"""
用户管理路由 — 多用户/管理员 CRUD + 密码管理
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_db
from ..models.user import User, UserRole
from .auth import (
    get_current_user, require_admin, require_superadmin,
    hash_password, verify_password
)

router = APIRouter(prefix="/api/users", tags=["用户管理"])


# ─── Schemas ───

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
    force_change: bool = True


# ─── 路由 ───

@router.get("")
async def list_users(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取所有用户列表"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "require_password_change": u.require_password_change,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("")
async def create_user(
    req: UserCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建新用户"""
    # 检查用户名唯一
    exist = await db.execute(select(User).where(User.username == req.username))
    if exist.scalars().first():
        raise HTTPException(status_code=409, detail="Username already exists")

    new_user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.username,
        email=req.email,
        role=req.role,
    )
    db.add(new_user)
    await db.flush()

    return {
        "id": str(new_user.id),
        "username": new_user.username,
        "role": new_user.role.value,
        "message": "User created",
    }


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(u.id),
        "username": u.username,
        "display_name": u.display_name,
        "email": u.email,
        "role": u.role.value,
        "is_active": u.is_active,
        "require_password_change": u.require_password_change,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: UUID,
    req: UserUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # 只有 superadmin 可以修改角色
    if req.role is not None and req.role != u.role:
        if user.role != UserRole.SUPERADMIN:
            raise HTTPException(status_code=403, detail="Only superadmin can change roles")

    for field in ("display_name", "email", "role", "is_active"):
        val = getattr(req, field)
        if val is not None:
            setattr(u, field, val)

    await db.flush()
    return {"message": "User updated"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """删除用户 (仅超级管理员)"""
    if str(user.id) == str(user_id):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(u)
    await db.flush()
    return {"message": "User deleted"}


@router.put("/{user_id}/password")
async def reset_user_password(
    user_id: UUID,
    req: ResetPasswordRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员重置其他用户密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalars().first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # 超级管理员可以重置任何人，管理员只能重置 viewer
    if user.role == UserRole.ADMIN and u.role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Cannot reset superadmin password")

    u.hashed_password = hash_password(req.new_password)
    u.require_password_change = req.force_change
    await db.flush()

    return {"message": "Password reset successfully"}