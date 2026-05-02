import subprocess
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "schema.prisma"
GENERATED_PATH = Path(__file__).parent / "prisma"


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a fresh SQLite database from the fixture schema using prisma db push."""
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
            "--accept-data-loss",
        ],
        check=True,
    )
    return path


@pytest.fixture(scope="session")
def db_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def db(db_url: str):
    """Connected Prisma client, disconnected after each test."""
    from prisma import Prisma

    client = Prisma()
    await client.connect(db_url)
    yield client
    await client.disconnect()
