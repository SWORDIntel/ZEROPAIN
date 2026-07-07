import numpy as np
from src.opioid_optimization_framework import ProtocolConfig, CompoundDatabase, ProtocolOptimizer

db = CompoundDatabase()
optimizer = ProtocolOptimizer(db, use_multiprocessing=True)
compounds = [db.get_compound('SR-17018'), db.get_compound('SR-14968'), db.get_compound('Phenomorphan')]

test_protocols = [
    # Micro PHM, All SR
    ([30.0, 40.0, 0.1], [2, 1, 1]),
    ([30.0, 40.0, 0.05], [2, 1, 1]),
    ([30.0, 40.0, 0.01], [2, 1, 1]),
]

for doses, freqs in test_protocols:
    proto = ProtocolConfig(compounds=['SR-17018', 'SR-14968', 'Phenomorphan'], doses=doses, frequencies=freqs)
    metrics = optimizer._evaluate_protocol(proto, compounds, 500)
    score = (
        metrics['success_rate'] * 100 -
        metrics['tolerance_rate'] * 50 -
        metrics['addiction_rate'] * 30 -
        metrics['withdrawal_rate'] * 40
    )
    print(f"Doses: {doses}, Score: {score:.2f}, Analgesia: {metrics['avg_analgesia']:.4f}, Tol: {metrics['tolerance_rate']:.4f}, SideEff: {metrics['avg_side_effects']:.4f}")
