from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.container import AppContainer


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("application container is not initialized")
    return container


def _extract_token(request: Request) -> str:
    header = str(request.headers.get("authorization") or "").strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return str(request.headers.get("x-api-token") or "").strip()


def require_request_auth(
    request: Request,
    container: AppContainer = Depends(get_container),
) -> None:
    expected = str(container.settings.auth.api_token or "").strip()
    if not expected:
        return
    provided = _extract_token(request)
    if provided == expected:
        return
    raise HTTPException(status_code=401, detail="auth_required")
