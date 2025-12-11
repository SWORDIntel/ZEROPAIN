from __future__ import annotations

from typing import List
import random

from ..types import DockingJobSpec, DockingPose


def run(job: DockingJobSpec, device: str = "CPU") -> List[DockingPose]:
    rng = random.Random(1234)
    poses: List[DockingPose] = []
    for lig_idx, ligand in enumerate(job.ligands[: job.max_ligands]):
        for pose_id in range(job.poses_per_ligand):
            score = -5.0 - 0.01 * pose_id + (0.1 * rng.random())
            poses.append(
                DockingPose(
                    ligand_id=str(ligand),
                    pose_id=pose_id,
                    score=score,
                    backend="mocked",
                    device=device,
                    rank=len(poses),
                )
            )
    return poses

