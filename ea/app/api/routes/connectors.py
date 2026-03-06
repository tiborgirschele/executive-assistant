from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import RequestContext, get_container, get_request_context, resolve_principal_id
from app.container import AppContainer

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


class ConnectorBindingIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    connector_name: str = Field(min_length=1, max_length=100)
    external_account_ref: str = Field(min_length=1, max_length=200)
    scope_json: dict[str, object] = Field(default_factory=dict)
    auth_metadata_json: dict[str, object] = Field(default_factory=dict)
    status: str = Field(default="enabled", max_length=50)


class ConnectorStatusIn(BaseModel):
    status: str = Field(min_length=1, max_length=50)


class ConnectorBindingOut(BaseModel):
    binding_id: str
    principal_id: str
    connector_name: str
    external_account_ref: str
    scope_json: dict[str, object]
    auth_metadata_json: dict[str, object]
    status: str
    created_at: str
    updated_at: str


@router.post("/bindings")
def upsert_binding(
    body: ConnectorBindingIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorBindingOut:
    row = container.tool_runtime.upsert_connector_binding(
        principal_id=resolve_principal_id(body.principal_id, context),
        connector_name=body.connector_name,
        external_account_ref=body.external_account_ref,
        scope_json=body.scope_json,
        auth_metadata_json=body.auth_metadata_json,
        status=body.status,
    )
    return ConnectorBindingOut(
        binding_id=row.binding_id,
        principal_id=row.principal_id,
        connector_name=row.connector_name,
        external_account_ref=row.external_account_ref,
        scope_json=row.scope_json,
        auth_metadata_json=row.auth_metadata_json,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/bindings")
def list_bindings(
    principal_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[ConnectorBindingOut]:
    rows = container.tool_runtime.list_connector_bindings(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
    )
    return [
        ConnectorBindingOut(
            binding_id=r.binding_id,
            principal_id=r.principal_id,
            connector_name=r.connector_name,
            external_account_ref=r.external_account_ref,
            scope_json=r.scope_json,
            auth_metadata_json=r.auth_metadata_json,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/bindings/{binding_id}/status")
def set_binding_status(
    binding_id: str,
    body: ConnectorStatusIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> ConnectorBindingOut:
    existing = container.tool_runtime.get_connector_binding(binding_id)
    if not existing or existing.principal_id != context.principal_id:
        raise HTTPException(status_code=404, detail="binding_not_found")
    row = container.tool_runtime.set_connector_binding_status(binding_id, body.status)
    if not row:
        raise HTTPException(status_code=404, detail="binding_not_found")
    return ConnectorBindingOut(
        binding_id=row.binding_id,
        principal_id=row.principal_id,
        connector_name=row.connector_name,
        external_account_ref=row.external_account_ref,
        scope_json=row.scope_json,
        auth_metadata_json=row.auth_metadata_json,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
