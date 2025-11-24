import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from pipeline.distributed_runner import DistributedRunner


class DistributedRunnerTests(unittest.TestCase):
    def test_local_execution_and_checkpoint_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = DistributedRunner(
                backend="local",
                checkpoint_dir=tmpdir,
                run_id="testrun",
                resume=True,
            )

            values = list(range(6))
            results = runner.map(lambda x: x * x, values, stage_name="square", batch_size=2)
            self.assertEqual(results, [v * v for v in values])

            # Ensure checkpoints exist
            ckpts = sorted(Path(tmpdir, "testrun", "checkpoints").glob("square-*.json"))
            self.assertGreaterEqual(len(ckpts), 3)

            # Second run should hit resume path and avoid executing the function
            def _fail(_: int) -> int:  # pragma: no cover - used to ensure resume skip
                raise AssertionError("Function should not be executed when resuming")

            resumed = runner.map(_fail, values, stage_name="square", batch_size=2)
            self.assertEqual(resumed, results)

    def test_backend_fallback_when_ray_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = DistributedRunner(
                backend="ray",  # Ray likely unavailable in CI; should fall back to local
                checkpoint_dir=tmpdir,
                run_id="fallback",
            )
            values = [1, 2, 3]
            results = runner.map(lambda x: x + 1, values, stage_name="inc", batch_size=1)
            self.assertEqual(results, [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
