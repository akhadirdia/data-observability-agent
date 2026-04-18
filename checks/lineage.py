from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

_RESULT_PILLAR = "lineage"
_LINEAGE_FILE = Path("lineage.yml")


def _load_lineage() -> dict:
    if not _LINEAGE_FILE.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(_LINEAGE_FILE.read_text(encoding="utf-8")) or {}
    except ImportError:
        # yaml non installé : fallback JSON-like sans dépendance
        logger.warning("PyYAML non installé — lignage indisponible. Installer avec : pip install pyyaml")
        return {}
    except Exception as exc:
        logger.error(f"Impossible de lire lineage.yml : {exc}")
        return {}


def get_upstream_tables(table: str) -> list[str]:
    """Retourne les tables en amont de la table donnée."""
    lineage = _load_lineage()
    return lineage.get(table, {}).get("upstream", [])


def get_downstream_tables(table: str) -> list[str]:
    """Retourne les tables en aval de la table donnée."""
    lineage = _load_lineage()
    return lineage.get(table, {}).get("downstream", [])


def check_lineage(table: str) -> dict:
    """
    Retourne le contexte de lignage d'une table depuis lineage.yml.
    Statut 'warning' si la table n'est pas déclarée dans le fichier.
    """
    ts = datetime.now(timezone.utc).isoformat()

    lineage = _load_lineage()

    if not _LINEAGE_FILE.exists():
        return _result(
            table, "ok", {},
            "lineage.yml absent — lignage non configuré (normal en MVP).", ts
        )

    if table not in lineage:
        return _result(
            table, "warning", {},
            f"Table '{table}' non déclarée dans lineage.yml.", ts
        )

    upstream = lineage[table].get("upstream", [])
    downstream = lineage[table].get("downstream", [])
    value = {"upstream": upstream, "downstream": downstream}
    msg = f"{len(upstream)} table(s) en amont, {len(downstream)} en aval."

    return _result(table, "ok", value, msg, ts)


def _result(table: str, status: str, value, message: str, ts: str) -> dict:
    return {
        "pillar": _RESULT_PILLAR,
        "table": table,
        "status": status,
        "value": value,
        "message": message,
        "timestamp": ts,
    }
