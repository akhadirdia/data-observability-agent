from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from connectors.sql_connector import SQLConnector
from core.snapshot_store import get_snapshot, set_snapshot

_RESULT_PILLAR = "schema"


def check_schema(connector: SQLConnector, table: str) -> dict:
    """
    Compare le schéma actuel au snapshot précédent.
    Alerte sur tout ajout, suppression ou changement de type de colonne.
    """
    ts = datetime.now(timezone.utc).isoformat()

    try:
        current_cols = connector.get_column_metadata(table)
        if not current_cols:
            return _result(table, "critical", {}, "Impossible de récupérer le schéma actuel.", ts)

        current_schema = {col["name"]: col["type"] for col in current_cols}
        snapshot_key = f"schema:{table}"
        previous_schema: dict | None = get_snapshot(snapshot_key)

        set_snapshot(snapshot_key, current_schema)

        if previous_schema is None:
            return _result(
                table, "ok", current_schema,
                f"Premier snapshot enregistré ({len(current_schema)} colonnes).", ts
            )

        added = [c for c in current_schema if c not in previous_schema]
        removed = [c for c in previous_schema if c not in current_schema]
        type_changed = [
            c for c in current_schema
            if c in previous_schema and current_schema[c] != previous_schema[c]
        ]

        changes: list[str] = []
        if added:
            changes.append(f"Colonnes ajoutées : {added}")
        if removed:
            changes.append(f"Colonnes supprimées : {removed}")
        if type_changed:
            changes.append(
                "Types modifiés : "
                + ", ".join(f"{c} ({previous_schema[c]} → {current_schema[c]})" for c in type_changed)
            )

        if changes:
            return _result(table, "critical", current_schema, " | ".join(changes), ts)

        return _result(table, "ok", current_schema, f"Schéma inchangé ({len(current_schema)} colonnes).", ts)

    except Exception as exc:
        logger.error(f"[schema:{table}] Erreur inattendue : {exc}")
        return _result(table, "critical", {}, f"Erreur lors du check : {exc}", ts)


def _result(table: str, status: str, value, message: str, ts: str) -> dict:
    return {
        "pillar": _RESULT_PILLAR,
        "table": table,
        "status": status,
        "value": value,
        "message": message,
        "timestamp": ts,
    }
