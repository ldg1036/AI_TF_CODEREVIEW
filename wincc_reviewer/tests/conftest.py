"""공통 테스트 fixture."""

from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """프로젝트 루트 디렉터리를 반환합니다."""
    return Path(__file__).parent.parent


@pytest.fixture
def config_dir(project_root: Path) -> Path:
    """config 디렉터리를 반환합니다."""
    return project_root.parent / "config"


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """schemas 디렉터리를 반환합니다."""
    return project_root / "schemas"


@pytest.fixture
def fixtures_dir() -> Path:
    """테스트 fixture 디렉터리를 반환합니다."""
    return Path(__file__).parent / "fixtures"
