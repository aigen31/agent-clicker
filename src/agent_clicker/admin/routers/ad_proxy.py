"""Ad-proxy-config REST router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent_clicker.admin.dependencies import get_ad_proxy_repo
from agent_clicker.admin.schemas import AdProxyConfigOut, AdProxyConfigUpsert
from agent_clicker.db.repository import AdProxyRepository

router = APIRouter(prefix="/api/ad-proxy", tags=["ad-proxy"])


@router.get("", response_model=list[AdProxyConfigOut])
async def list_configs(repo: AdProxyRepository = Depends(get_ad_proxy_repo)) -> list[AdProxyConfigOut]:
    dtos = await repo.list_all()
    return [AdProxyConfigOut.from_dto(d) for d in dtos]


@router.get("/{ad_id}", response_model=AdProxyConfigOut)
async def get_config(
    ad_id: int, repo: AdProxyRepository = Depends(get_ad_proxy_repo)
) -> AdProxyConfigOut:
    dto = await repo.get_by_ad_id(ad_id)
    if dto is None:
        raise HTTPException(status_code=404, detail="ad proxy config not found")
    return AdProxyConfigOut.from_dto(dto)


@router.put("/{ad_id}", response_model=AdProxyConfigOut)
async def upsert_config(
    ad_id: int,
    body: AdProxyConfigUpsert,
    repo: AdProxyRepository = Depends(get_ad_proxy_repo),
) -> AdProxyConfigOut:
    dto = await repo.upsert(
        ad_id=ad_id,
        proxy_host=body.proxy_host,
        proxy_port=body.proxy_port,
        proxy_login=body.proxy_login,
        proxy_password=body.proxy_password,
    )
    return AdProxyConfigOut.from_dto(dto)


@router.delete("/{ad_id}", status_code=204)
async def delete_config(
    ad_id: int, repo: AdProxyRepository = Depends(get_ad_proxy_repo)
) -> None:
    removed = await repo.delete(ad_id)
    if not removed:
        raise HTTPException(status_code=404, detail="ad proxy config not found")
