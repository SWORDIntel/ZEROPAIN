"""
Vector ingestion for docking results.
Pushes textual embeddings of poses/scores into the AI vector DB (Chroma) when available.
Falls back to no-op if embedding model or vector store is unavailable.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from ai.brain.vectors.chromadb_backend import (
        ChromaDBBackend,
        VectorMetadata,
        CHROMADB_AVAILABLE,
    )
    VECTOR_AVAILABLE = CHROMADB_AVAILABLE
except Exception:
    VECTOR_AVAILABLE = False
    ChromaDBBackend = None  # type: ignore
    VectorMetadata = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    EMBEDDING_AVAILABLE = True
except Exception:
    EMBEDDING_AVAILABLE = False
    SentenceTransformer = None  # type: ignore


DEFAULT_COLLECTION = "docking_poses_v1"
DEFAULT_PERSIST = str(Path.home() / ".dsmil" / "docking_vectors")
DEFAULT_EMBEDDER = "all-MiniLM-L6-v2"


class DockingVectorIngest:
    def __init__(self, collection: str = DEFAULT_COLLECTION, persist_path: str | None = DEFAULT_PERSIST, embedder_name: str = DEFAULT_EMBEDDER):
        self.enabled = VECTOR_AVAILABLE and EMBEDDING_AVAILABLE
        if not self.enabled:
            logger.debug("Vector ingestion disabled (missing vector store or embeddings)")
            return
        self.backend = ChromaDBBackend(persist_path=persist_path)
        self.collection = collection
        try:
            self.embedder = SentenceTransformer(embedder_name)
        except Exception as exc:
            logger.warning(f"Embedding model load failed: {exc}")
            self.embedder = None
            self.enabled = False

    def _embed(self, text: str) -> List[float] | None:
        if not self.enabled or not self.embedder:
            return None
        try:
            return self.embedder.encode(text).tolist()
        except Exception as exc:
            logger.debug(f"Embed failed: {exc}")
            return None

    def ingest(self, job_id: str, poses: List[Dict[str, Any]], telemetry: Dict[str, Any], artifacts: Dict[str, str]) -> bool:
        if not self.enabled:
            return False
        successes = 0
        for p in poses:
            text = (
                f"job {job_id} ligand {p.get('ligand_id')} pose {p.get('pose_id')} "
                f"score {p.get('score')} backend {p.get('backend')} device {p.get('device')} "
                f"rank {p.get('rank')}"
            )
            vec = self._embed(text)
            if not vec:
                continue
            meta = VectorMetadata(
                source="zeropain.docking",
                entity_ids=[job_id, str(p.get("ligand_id")), str(p.get("pose_id"))],
                tags=["docking", p.get("backend", ""), p.get("device", "")],
                vector_type="docking_pose",
                confidence=1.0,
                extra={
                    "score": p.get("score"),
                    "backend": p.get("backend"),
                    "device": p.get("device"),
                    "rank": p.get("rank"),
                    "artifacts": artifacts,
                    "telemetry": telemetry,
                },
            )
            ok = self.backend.add_vector(
                vector_id=f"dock-{job_id}-{p.get('ligand_id')}-{p.get('pose_id')}",
                vector=vec,
                metadata=meta,
                collection=self.collection,
            )
            if ok:
                successes += 1
        return successes > 0


def ingest_docking_vectors(job_id: str, poses: List[Any], telemetry: Dict[str, Any], artifacts: Dict[str, str]) -> bool:
    ingestor = DockingVectorIngest()
    # Pose objects may be dataclasses; convert to dict
    pose_dicts = []
    for p in poses:
        if hasattr(p, "__dict__"):
            pose_dicts.append(p.__dict__)
        elif isinstance(p, dict):
            pose_dicts.append(p)
    return ingestor.ingest(job_id, pose_dicts, telemetry, artifacts)

