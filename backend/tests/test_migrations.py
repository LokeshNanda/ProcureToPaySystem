import os
import subprocess
import sys


def test_alembic_upgrade_head_runs():
    env = {**os.environ, "DATABASE_URL": "postgresql+asyncpg://openp2p:openp2p@localhost:5433/openp2p"}
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
