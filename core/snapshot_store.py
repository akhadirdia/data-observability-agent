from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_STORE_PATH = Path(".obs_snapshots.json")


def _load() -> dict:
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"Snapshot store illisible : {exc}")
        return {}


def _save(data: dict) -> None:
    try:
        _STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.error(f"Impossible d'écrire le snapshot store : {exc}")


def append_history(key: str, value: float, max_entries: int = 30) -> None:
    """Ajoute une valeur à l'historique d'une clé (rolling window)."""
    data = _load()
    history: list[dict] = data.get(key, [])
    history.append({"value": value, "ts": datetime.now(timezone.utc).isoformat()})
    data[key] = history[-max_entries:]
    _save(data)


def get_history(key: str) -> list[float]:
    """Retourne les valeurs historiques d'une clé."""
    data = _load()
    return [entry["value"] for entry in data.get(key, [])]


def set_snapshot(key: str, snapshot: Any) -> None:
    """Stocke un snapshot arbitraire (schéma, etc.)."""
    data = _load()
    data[key] = {"snapshot": snapshot, "ts": datetime.now(timezone.utc).isoformat()}
    _save(data)


def get_snapshot(key: str) -> Any | None:
    """Retourne le snapshot stocké ou None."""
    data = _load()
    entry = data.get(key)
    return entry["snapshot"] if entry else None
