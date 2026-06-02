"""
自定义组织架构标签路由 — 多层树形标签 CRUD
"""

from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.tags import CustomTag, TagCategory
from models.user import User
from .auth import get_current_user, require_admin

router = APIRouter(prefix="/api/tags", tags=["组织架构标签"])


# ─── Schemas ───

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    parent_id: Optional[UUID] = None
    description: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0


class TagUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    parent_id: Optional[UUID] = None


class TagCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None
    max_depth: int = 10


# ─── 标签 CRUD ───

@router.get("")
async def list_tags(
    parent_id: Optional[UUID] = None,
    root_only: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取标签列表"""
    if root_only:
        result = await db.execute(
            select(CustomTag).where(CustomTag.parent_id.is_(None))
            .order_by(CustomTag.sort_order)
        )
    elif parent_id:
        result = await db.execute(
            select(CustomTag).where(CustomTag.parent_id == parent_id)
            .order_by(CustomTag.sort_order)
        )
    else:
        result = await db.execute(
            select(CustomTag).order_by(CustomTag.level, CustomTag.sort_order)
        )

    tags = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "parent_id": str(t.parent_id) if t.parent_id else None,
            "level": t.level,
            "description": t.description,
            "color": t.color,
            "sort_order": t.sort_order,
            "full_path": t.get_full_path(),
            "child_count": len(t.children) if t.children else 0,
        }
        for t in tags
    ]


@router.get("/tree")
async def get_tag_tree(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取完整标签树 (组织架构视图)

    返回嵌套 JSON 树形结构
    """
    roots_result = await db.execute(
        select(CustomTag).where(CustomTag.parent_id.is_(None))
        .order_by(CustomTag.sort_order)
    )
    roots = roots_result.scalars().all()

    async def build_node(tag: CustomTag) -> dict:
        # 获取子节点
        child_result = await db.execute(
            select(CustomTag).where(CustomTag.parent_id == tag.id)
            .order_by(CustomTag.sort_order)
        )
        children = child_result.scalars().all()

        return {
            "id": str(tag.id),
            "name": tag.name,
            "slug": tag.slug,
            "level": tag.level,
            "description": tag.description,
            "color": tag.color,
            "full_path": tag.get_full_path(),
            "children": [await build_node(child) for child in children],
        }

    return [await build_node(root) for root in roots]


@router.post("")
async def create_tag(
    req: TagCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建标签"""
    level = 0
    if req.parent_id:
        parent_result = await db.execute(
            select(CustomTag).where(CustomTag.id == req.parent_id)
        )
        parent = parent_result.scalars().first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent tag not found")
        level = parent.level + 1

    tag = CustomTag(
        name=req.name,
        slug=req.slug,
        parent_id=req.parent_id,
        level=level,
        description=req.description,
        color=req.color,
        sort_order=req.sort_order,
    )
    db.add(tag)
    await db.flush()

    return {
        "id": str(tag.id),
        "name": tag.name,
        "level": tag.level,
        "full_path": tag.get_full_path(),
    }


@router.put("/{tag_id}")
async def update_tag(
    tag_id: UUID,
    req: TagUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新标签"""
    result = await db.execute(select(CustomTag).where(CustomTag.id == tag_id))
    tag = result.scalars().first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if req.parent_id is not None and req.parent_id != tag.parent_id:
        # 移动节点：重新计算 level
        parent_result = await db.execute(
            select(CustomTag).where(CustomTag.id == req.parent_id)
        )
        parent = parent_result.scalars().first()
        if parent:
            tag.parent_id = req.parent_id
            tag.level = parent.level + 1

    for field in ("name", "slug", "description", "color", "sort_order"):
        val = getattr(req, field, None)
        if val is not None:
            setattr(tag, field, val)

    await db.flush()
    return {"message": "Tag updated", "full_path": tag.get_full_path()}


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除标签 (级联删除子标签, 租约标签置 NULL)"""
    result = await db.execute(select(CustomTag).where(CustomTag.id == tag_id))
    tag = result.scalars().first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    await db.delete(tag)
    await db.flush()
    return {"message": "Tag and children deleted"}


# ─── 标签分类 ───

@router.get("/categories")
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取标签分类列表"""
    result = await db.execute(select(TagCategory).order_by(TagCategory.sort_order))
    cats = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "max_depth": c.max_depth,
        }
        for c in cats
    ]


@router.post("/categories")
async def create_category(
    req: TagCategoryCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建标签分类"""
    cat = TagCategory(name=req.name, description=req.description, max_depth=req.max_depth)
    db.add(cat)
    await db.flush()
    return {"id": str(cat.id), "message": "Category created"}