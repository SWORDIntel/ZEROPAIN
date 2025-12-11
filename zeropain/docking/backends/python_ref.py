from __future__ import annotations

import random
from typing import List

from ..types import DockingJobSpec, DockingPose


def run(job: DockingJobSpec, device: str = "CPU") -> List[DockingPose]:
    poses: List[DockingPose] = []
    rng = random.Random(42)
    for lig_idx, ligand in enumerate(job.ligands[: job.max_ligands]):
        for pose_id in range(job.poses_per_ligand):
            score = -7.0 + rng.random()  # placeholder score
            poses.append(
                DockingPose(
                    ligand_id=str(ligand),
                    pose_id=pose_id,
                    score=score,
                    backend="python_ref",
                    device=device,
                    rank=len(poses),
                )
            )
    return poses

