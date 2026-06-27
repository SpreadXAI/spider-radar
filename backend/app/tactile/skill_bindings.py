"""Resolve merged skill bindings for per-account Tactile agents."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AccountSkillBinding, SocialAccount
from app.tactile.client import TactileClient


def template_skill_bindings(settings: Settings, client: TactileClient) -> list[dict[str, int]]:
    if settings.tactile_template_agent_id:
        detail = client.get_agent(settings.tactile_template_agent_id)
        bindings = detail.get("bindings") or {}
        skills = bindings.get("skills") or []
        return [{"skill_id": int(s["skill_id"]), "version_id": int(s["version_id"])} for s in skills]
    if settings.tactile_template_skill_id and settings.tactile_template_skill_version_id:
        return [
            {
                "skill_id": settings.tactile_template_skill_id,
                "version_id": settings.tactile_template_skill_version_id,
            }
        ]
    return []


def account_skill_bindings(db: Session, account_id: int) -> list[dict[str, int]]:
    rows = (
        db.query(AccountSkillBinding)
        .filter(AccountSkillBinding.account_id == account_id, AccountSkillBinding.enabled.is_(True))
        .order_by(AccountSkillBinding.sort_order, AccountSkillBinding.id)
        .all()
    )
    return [{"skill_id": row.skill_id, "version_id": row.version_id} for row in rows]


def merged_skill_bindings(
    settings: Settings,
    client: TactileClient,
    db: Session,
    account: SocialAccount,
) -> list[dict[str, int]]:
    """Platform layer first; account layer overrides same skill_id."""
    by_id: dict[int, dict[str, int]] = {}
    for item in template_skill_bindings(settings, client):
        by_id[int(item["skill_id"])] = item
    for item in account_skill_bindings(db, account.id):
        by_id[int(item["skill_id"])] = item
    return list(by_id.values())
