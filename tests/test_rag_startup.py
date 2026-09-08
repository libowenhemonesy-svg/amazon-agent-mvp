import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_app_starts_when_embedding_model_is_unavailable(tmp_path: Path):
    environment = os.environ | {"RAG_EMBEDDING_MODEL": str(tmp_path / "missing-model")}

    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app; print(app.title)"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Amazon Agent MVP" in result.stdout
