from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import get_container
from app.container import AppContainer

router = APIRouter(prefix="/v1/tools", tags=["tools"])


class ToolIn(BaseModel):
    tool_name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="v1", max_length=100)
    input_schema_json: dict[str, object] = Field(default_factory=dict)
    output_schema_json: dict[str, object] = Field(default_factory=dict)
    policy_json: dict[str, object] = Field(default_factory=dict)
    allowed_channels: list[str] = Field(default_factory=list)
    approval_default: str = Field(default="none", max_length=100)
    enabled: bool = True


class ToolOut(BaseModel):
    tool_name: str
    version: str
    input_schema_json: dict[str, object]
    output_schema_json: dict[str, object]
    policy_json: dict[str, object]
    allowed_channels: list[str]
    approval_default: str
    enabled: bool
    updated_at: str


@router.post("/registry")
def upsert_tool(
    body: ToolIn,
    container: AppContainer = Depends(get_container),
) -> ToolOut:
    row = container.tool_runtime.upsert_tool(
        tool_name=body.tool_name,
        version=body.version,
        input_schema_json=body.input_schema_json,
        output_schema_json=body.output_schema_json,
        policy_json=body.policy_json,
        allowed_channels=tuple(body.allowed_channels),
        approval_default=body.approval_default,
        enabled=body.enabled,
    )
    return ToolOut(
        tool_name=row.tool_name,
        version=row.version,
        input_schema_json=row.input_schema_json,
        output_schema_json=row.output_schema_json,
        policy_json=row.policy_json,
        allowed_channels=list(row.allowed_channels),
        approval_default=row.approval_default,
        enabled=row.enabled,
        updated_at=row.updated_at,
    )


@router.get("/registry")
def list_enabled_tools(
    limit: int = Query(default=100, ge=1, le=500),
    container: AppContainer = Depends(get_container),
) -> list[ToolOut]:
    rows = container.tool_runtime.list_enabled_tools(limit=limit)
    return [
        ToolOut(
            tool_name=r.tool_name,
            version=r.version,
            input_schema_json=r.input_schema_json,
            output_schema_json=r.output_schema_json,
            policy_json=r.policy_json,
            allowed_channels=list(r.allowed_channels),
            approval_default=r.approval_default,
            enabled=r.enabled,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/registry/{tool_name}")
def get_tool(
    tool_name: str,
    container: AppContainer = Depends(get_container),
) -> ToolOut:
    row = container.tool_runtime.get_tool(tool_name)
    if not row:
        raise HTTPException(status_code=404, detail="tool_not_found")
    return ToolOut(
        tool_name=row.tool_name,
        version=row.version,
        input_schema_json=row.input_schema_json,
        output_schema_json=row.output_schema_json,
        policy_json=row.policy_json,
        allowed_channels=list(row.allowed_channels),
        approval_default=row.approval_default,
        enabled=row.enabled,
        updated_at=row.updated_at,
    )
