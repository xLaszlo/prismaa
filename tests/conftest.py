import subprocess
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "example" / "schema.prisma"


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a fresh SQLite database from the example schema using prisma db push."""
    path = tmp_path_factory.mktemp("db") / "test.db"
    subprocess.run(
        [
            "npx",
            "--yes",
            "prisma",
            "db",
            "push",
            "--schema",
            str(SCHEMA_PATH),
            f"--url=file:{path}",
            "--skip-generate",
            "--accept-data-loss",
        ],
        check=True,
    )
    return path


@pytest.fixture
def db_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"
