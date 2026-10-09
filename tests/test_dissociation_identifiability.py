import numpy as np

from research.dissociation.identifiability import analyze_identifiability


def test_identifiability_detects_parallel_parameter_effects():
    jacobian = np.array(
        [
            [1.0, 2.0, 0.0],
            [2.0, 4.0, 1.0],
            [3.0, 6.0, 0.0],
            [4.0, 8.0, -1.0],
        ]
    )
    summary, sensitivities, cosine = analyze_identifiability(
        jacobian,
        ["a", "b", "c"],
        confounding_threshold=0.95,
    )

    pairs = {
        (row["parameter_a"], row["parameter_b"])
        for row in summary.highly_confounded_pairs
    }
    assert ("a", "b") in pairs
    assert abs(cosine[0, 1]) > 0.99
    assert sensitivities["b"] > sensitivities["a"]
    assert summary.numerical_rank == 2
