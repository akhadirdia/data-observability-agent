from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from connectors.sql_connector import SQLConnector
from core.snapshot_store import append_history, get_history

_RESULT_PILLAR = "volume"


def check_volume(
    connector: SQLConnector,
    table: str,
    warning_pct: float = 0.20,
    critical_pct: float = 0.50,
) -> dict:
    """
    Vérifie que le nombre de lignes est cohérent avec l'historique.
    Alerte si la variation dépasse warning_pct (défaut 20%) ou critical_pct (50%).
    """
    ts = datetime.now(timezone.utc).isoformat()

    try:
        count = connector.get_row_count(table)
        if count is None:
            return _result(table, "critical", None, "Impossible de compter les lignes.", ts)

        history = get_history(f"volume:{table}")
        append_history(f"volume:{table}", float(count))

        if not history:
            return _result(table, "ok", count, f"{count} lignes (historique insuffisant).", ts)

        avg = sum(history) / len(history)

        if avg == 0:
            status = "warning" if count == 0 else "ok"
            return _result(table, status, count, f"{count} lignes (moyenne historique à 0).", ts)

        variation = abs(count - avg) / avg

        if variation > critical_pct:
            status = "critical"
            msg = f"{count} lignes — variation {variation:.0%} >> seuil critique ({critical_pct:.0%}). Moy. : {avg:.0f}."
        elif variation > warning_pct:
            status = "warning"
            msg = f"{count} lignes — variation {variation:.0%} > seuil ({warning_pct:.0%}). Moy. : {avg:.0f}."
        else:
            status = "ok"
            msg = f"{count} lignes — variation {variation:.0%} dans la norme (moy. {avg:.0f})."

        return _result(table, status, count, msg, ts)

    except Exception as exc:
        logger.error(f"[volume:{table}] Erreur inattendue : {exc}")
        return _result(table, "critical", None, f"Erreur lors du check : {exc}", ts)


def _result(table: str, status: str, value, message: str, ts: str) -> dict:
    return {
        "pillar": _RESULT_PILLAR,
        "table": table,
        "status": status,
        "value": value,
        "message": message,
        "timestamp": ts,
    }
