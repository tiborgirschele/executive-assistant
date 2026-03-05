from __future__ import annotations

from typing import Dict

from app.domain.models import Artifact


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._rows: Dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self._rows[artifact.artifact_id] = artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._rows.get(str(artifact_id or ""))
