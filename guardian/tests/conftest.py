import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

import sample_context  # noqa: E402


@pytest.fixture(scope="session")
def ctx(tmp_path_factory) -> Path:
    return sample_context.build(tmp_path_factory.mktemp("context"))
