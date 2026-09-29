import os
import sys
import tempfile
from pathlib import Path

import pytest

# Tests run against a throw-away SQLite database and without Redis, so they
# need no running infrastructure (ideal for the CI "test" stage).
_db_file = Path(tempfile.gettempdir()) / "taskmanager_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}"
os.environ.pop("REDIS_HOST", None)
os.environ["DB_CONNECT_RETRIES"] = "1"

# Make the "backend" package importable when pytest runs from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.database import Base, engine  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:  # runs the lifespan -> creates tables
        yield test_client
    Base.metadata.drop_all(bind=engine)
