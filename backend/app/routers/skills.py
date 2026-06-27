"""Skill catalog, account bindings, batch install, and skill authoring."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AccountSkillBinding, SkillLayer, SocialAccount, User
from app.routers.app import _active_workspace, _workspace_account
from app.schemas import (
    AccountSkillBindingOut,
    BatchSkillInstallRequest,
    BatchSkillInstallResult,
    SkillCatalogOut,
    SkillCatalogSkill,
    SkillCreateSessionOut,
    SkillCreateSessionRequest,
)
from app.tactile.client import TactileClient, TactileError
from app.tactile.skill_sync import install_skill_on_accounts, sync_account_skills_to_agent

router = APIRouter(prefix="/skills", tags=["skills"])


def _skill_summary(item: dict) -> SkillCatalogSkill:
    return SkillCatalogSkill(
        id=int(item["id"]),
        slug=item.get("slug", ""),
        name=item.get("name", ""),
        description=item.get("description", ""),
        layer=SkillLayer.workspace,
        current_version_id=item.get("current_version_id"),
        current_version=item.get("current_version"),
        workspace_id=item.get("workspace_id"),
    )


@router.get("/catalog", response_model=SkillCatalogOut)
def list_skill_catalog(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SkillCatalogOut:
    del db, current_user
    settings = get_settings()
    if not settings.tactile_workspace_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Tactile not configured")
    client = TactileClient(settings)
    try:
        data = client.list_workspace_skills(settings.tactile_workspace_id)
    except TactileError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    platform: list[SkillCatalogSkill] = []
    if settings.tactile_template_skill_id and settings.tactile_template_skill_version_id:
        platform.append(
            SkillCatalogSkill(
                id=settings.tactile_template_skill_id,
                slug="platform-base",
                name="Platform Twitter Ops (template)",
                description="Base layer skill copied from platform template agent.",
                layer=SkillLayer.platform,
                current_version_id=settings.tactile_template_skill_version_id,
                current_version=None,
                workspace_id=settings.tactile_workspace_id,
            )
        )

    workspace_items = [_skill_summary(s) for s in (data.get("workspace") or [])]
    mine_items = [_skill_summary(s) for s in (data.get("mine") or [])]
    return SkillCatalogOut(platform=platform, workspace=workspace_items, mine=mine_items)


@router.get("/my/accounts/{account_id}/bindings", response_model=list[AccountSkillBindingOut])
def list_account_skills(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AccountSkillBindingOut]:
    _workspace_account(db, current_user, account_id)
    rows = (
        db.query(AccountSkillBinding)
        .filter(AccountSkillBinding.account_id == account_id)
        .order_by(AccountSkillBinding.sort_order, AccountSkillBinding.id)
        .all()
    )
    return [AccountSkillBindingOut.model_validate(r) for r in rows]


@router.post("/batch-install", response_model=BatchSkillInstallResult)
def batch_install_skill(
    payload: BatchSkillInstallRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> BatchSkillInstallResult:
    settings = get_settings()
    ws = _active_workspace(db, current_user)
    account_ids: list[int] = []
    for aid in payload.account_ids:
        account = _workspace_account(db, current_user, aid)
        if account.workspace_id != ws.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not in workspace")
        account_ids.append(aid)

    slug = payload.slug
    name = payload.name
    if not slug or not name:
        client = TactileClient(settings)
        try:
            detail = client.get_skill(payload.skill_id)
            slug = slug or detail.get("slug", "")
            name = name or detail.get("name", "")
        except TactileError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    try:
        affected = install_skill_on_accounts(
            db,
            settings,
            account_ids=account_ids,
            skill_id=payload.skill_id,
            version_id=payload.version_id,
            slug=slug,
            name=name,
            layer=payload.layer,
            inputs_json=payload.inputs_json,
            outputs_json=payload.outputs_json,
        )
    except TactileError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    return BatchSkillInstallResult(
        skill_id=payload.skill_id,
        version_id=payload.version_id,
        account_ids=affected,
        installed_count=len(affected),
    )


@router.post("/create-session", response_model=SkillCreateSessionOut)
def start_skill_create_session(
    payload: SkillCreateSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SkillCreateSessionOut:
    del db
    settings = get_settings()
    agent_id = settings.tactile_skill_creator_agent_id
    if not agent_id or not settings.tactile_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skill creator agent not configured (TACTILE_SKILL_CREATOR_AGENT_ID)",
        )

    account_hint = ""
    if payload.account_id:
        account_hint = f"\nTarget account id: {payload.account_id}"

    content = (
        f"Create a new Tactile skill for Spider Radar account nurturing.\n\n"
        f"Skill goal:\n{payload.prompt.strip()}\n"
        f"{account_hint}\n\n"
        f"Use skill-creator to draft SKILL.md with clear inputs and outputs, "
        f"then use tactile-ops to upload to Skill Plaza for workspace {settings.tactile_workspace_id}."
    )
    client = TactileClient(settings)
    try:
        work = client.create_work(
            workspace_id=settings.tactile_workspace_id,
            agent_id=agent_id,
            name=payload.title or "Spider Radar Skill Authoring",
            content=content,
        )
    except TactileError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    return SkillCreateSessionOut(
        tactile_work_id=work.get("id"),
        tactile_session_id=work.get("session_id"),
        message="Skill authoring session started in Tactile",
    )


@router.post("/my/accounts/{account_id}/sync-skills")
def sync_account_skills(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    account = _workspace_account(db, current_user, account_id)
    settings = get_settings()
    try:
        sync_account_skills_to_agent(db, settings, account)
    except TactileError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc
    return {"status": "synced"}
