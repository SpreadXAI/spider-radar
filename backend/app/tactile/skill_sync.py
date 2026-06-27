"""Sync account skill bindings to Tactile per-account agents."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AccountSkillBinding, SkillLayer, SocialAccount
from app.tactile.client import TactileClient, TactileError
from app.tactile.skill_bindings import merged_skill_bindings


def sync_account_skills_to_agent(db: Session, settings: Settings, account: SocialAccount) -> None:
    from app.tactile.agent_provision import ensure_account_agent

    agent_id = ensure_account_agent(db, settings, account)
    client = TactileClient(settings)
    skills = merged_skill_bindings(settings, client, db, account)
    client.update_agent_bindings(agent_id, {"skills": skills})


def install_skill_on_accounts(
    db: Session,
    settings: Settings,
    *,
    account_ids: list[int],
    skill_id: int,
    version_id: int,
    slug: str,
    name: str,
    layer: SkillLayer = SkillLayer.account,
    inputs_json: str | None = None,
    outputs_json: str | None = None,
) -> list[int]:
    """Batch install skill binding on accounts; sync each agent. Returns affected account ids."""
    affected: list[int] = []
    for account_id in account_ids:
        account = db.get(SocialAccount, account_id)
        if account is None:
            continue
        row = (
            db.query(AccountSkillBinding)
            .filter(AccountSkillBinding.account_id == account_id, AccountSkillBinding.skill_id == skill_id)
            .first()
        )
        if row is None:
            row = AccountSkillBinding(
                account_id=account_id,
                skill_id=skill_id,
                version_id=version_id,
                slug=slug,
                name=name,
                layer=layer,
                inputs_json=inputs_json,
                outputs_json=outputs_json,
            )
            db.add(row)
        else:
            row.version_id = version_id
            row.slug = slug
            row.name = name
            row.layer = layer
            row.enabled = True
            if inputs_json is not None:
                row.inputs_json = inputs_json
            if outputs_json is not None:
                row.outputs_json = outputs_json
        db.flush()
        try:
            sync_account_skills_to_agent(db, settings, account)
        except TactileError as exc:
            raise TactileError(exc.status, f"account {account_id} (@{account.handle}): {exc.detail}") from exc
        affected.append(account_id)
    db.commit()
    return affected
