from __future__ import annotations

import os
import uuid

import pytest

from app.domain.models import Artifact
from app.repositories.artifacts_postgres import PostgresArtifactRepository


def test_postgres_artifact_roundtrip_persists_across_repo_reinit(tmp_path) -> None:
    db_url = (os.environ.get("EA_TEST_DATABASE_URL") or "").strip()
    if not db_url:
        pytest.skip("EA_TEST_DATABASE_URL is not set")
    repo = PostgresArtifactRepository(
        database_url=db_url,
        artifacts_dir=str(tmp_path / "artifact_store"),
        tenant_id="test-tenant",
    )
    artifact = Artifact(
        artifact_id=str(uuid.uuid4()),
        kind="rewrite_note",
        content="postgres durable content",
        execution_session_id=str(uuid.uuid4()),
    )
    repo.save(artifact)

    repo2 = PostgresArtifactRepository(
        database_url=db_url,
        artifacts_dir=str(tmp_path / "artifact_store"),
        tenant_id="test-tenant",
    )
    loaded = repo2.get(artifact.artifact_id)
    assert loaded is not None
    assert loaded.artifact_id == artifact.artifact_id
    assert loaded.content == "postgres durable content"
