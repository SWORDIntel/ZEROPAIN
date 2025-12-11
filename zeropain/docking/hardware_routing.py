from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict

from .types import DockingJobSpec

try:
    # DSMIL intelligent router
    from ai.hardware import IntelligentWorkloadRouter, WorkloadRequest, WorkloadType  # type: ignore
    ROUTER_AVAILABLE = True
except Exception:
    ROUTER_AVAILABLE = False
    IntelligentWorkloadRouter = None  # type: ignore
    WorkloadRequest = None  # type: ignore
    WorkloadType = None  # type: ignore


@dataclass
class DockingHardwareProfile:
    cpu_cores: int = 0
    avx2: bool = False
    arc_gpu: bool = False
    npu_available: bool = False
    router_ready: bool = False


def detect_hardware_profile() -> DockingHardwareProfile:
    try:
        import psutil  # type: ignore
        cores = psutil.cpu_count(logical=True) or 0
    except Exception:
        cores = 0
    return DockingHardwareProfile(cpu_cores=cores, avx2=False, arc_gpu=False, npu_available=False, router_ready=ROUTER_AVAILABLE)


def _build_request(job: DockingJobSpec) -> Optional["WorkloadRequest"]:
    if not ROUTER_AVAILABLE:
        return None
    # Approximate workload size by ligands * poses_per_ligand
    batch_size = max(1, min(job.max_ligands, len(job.ligands)) * job.poses_per_ligand)
    return WorkloadRequest(
        workload_id=job.job_id,
        workload_type=WorkloadType.CNN_CLASSIFICATION,  # treat docking scoring as heavy numeric compute
        model_name=job.backend or "docking",
        batch_size=batch_size,
        input_shape=(batch_size,),
        security_layer=3,
        framework="native",
        quantization="fp32",
    )


def select_backend(job: DockingJobSpec, profile: Optional[DockingHardwareProfile] = None) -> Tuple[str, str, Dict]:
    """
    Returns (backend, device, routing_meta)
    backend: python_ref|c_native|openvino_ml|mocked
    device: CPU|GPU|NPU|AUTO
    """
    routing_meta: Dict = {}

    # User override
    if job.backend:
        return job.backend, (job.hardware or "AUTO" if job.backend != "mocked" else "CPU"), routing_meta

    profile = profile or detect_hardware_profile()

    # Router path
    if ROUTER_AVAILABLE:
        router = IntelligentWorkloadRouter(power_budget_w=150.0)
        req = _build_request(job)
        if req:
            try:
                decision = router.route_workload(req)
                if decision:
                    accel = decision.accelerator_id.value if hasattr(decision.accelerator_id, "value") else str(decision.accelerator_id)
                    routing_meta = {
                        "accelerator": accel,
                        "estimated_latency_ms": getattr(decision, "estimated_latency_ms", None),
                        "power_impact_w": getattr(decision, "power_impact_w", None),
                    }
                    if "NPU" in accel.upper():
                        return "openvino_ml", "NPU", routing_meta
                    if "GPU" in accel.upper() or "ARC" in accel.upper():
                        return "c_native", "GPU", routing_meta
                    return "python_ref", "CPU", routing_meta
            except Exception as e:
                routing_meta["router_error"] = str(e)

    # Heuristic fallback
    if profile.arc_gpu:
        return "c_native", "GPU", routing_meta
    return "python_ref", "CPU", routing_meta

