"""Пути репозитория. Секретов и весов здесь нет."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sample_calls_path() -> Path:
    return repo_root() / "examples" / "crm" / "sample-calls.json"


def default_library_path() -> Path:
    return repo_root() / "data" / "train" / "library.json"
