from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from connectors.sql_connector import SQLConnector
from core.snapshot_store import append_history, get_history

_RESULT_PILLAR = "freshness"


def check_freshness(
    connector: SQLConnector,
    table: str,
    date_column: str = "created_at",
    warning_multiplier: float = 2.0,
    critical_multiplier: float = 4.0,
) -> dict:
    """
    Mesure le délai depuis le dernier enregistrement.
    Alerte si le délai dépasse warning_multiplier × la moyenne historique.
    """
    now = datetime.now(timezone.utc)
    ts = now.isoformat()

    try:
        df = connector.execute_query(
            f"SELECT MAX({date_column}) AS last_update FROM {table}"
        )

        if df.empty or df.iloc[0]["last_update"] is None:
            return _result(table, "warning", None, "Aucun enregistrement ou colonne date vide.", ts)

        raw_value = df.iloc[0]["last_update"]
        last_update = _parse_datetime(raw_value)
        if last_update is None:
            return _result(table, "warning", None, f"Format de date non reconnu : {raw_value}", ts)

        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        delay_hours = (now - last_update).total_seconds() / 3600
        history = get_history(f"freshness:{table}")
        append_history(f"freshness:{table}", delay_hours)

        if not history:
            return _result(table, "ok", delay_hours, f"Délai actuel : {delay_hours:.2f}h (historique insuffisant).", ts)

        avg_delay = sum(history) / len(history)

        if delay_hours > avg_delay * critical_multiplier:
            status = "critical"
            msg = f"Délai {delay_hours:.2f}h >> {critical_multiplier}× la moyenne ({avg_delay:.2f}h)."
        elif delay_hours > avg_delay * warning_multiplier:
            status = "warning"
            msg = f"Délai {delay_hours:.2f}h > {warning_multiplier}× la moyenne ({avg_delay:.2f}h)."
        else:
            status = "ok"
            msg = f"Délai {delay_hours:.2f}h dans la norme (moy. {avg_delay:.2f}h)."

        return _result(table, status, delay_hours, msg, ts)

    except Exception as exc:
        logger.error(f"[freshness:{table}] Erreur inattendue : {exc}")
        return _result(table, "critical", None, f"Erreur lors du check : {exc}", ts)


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _result(table: str, status: str, value, message: str, ts: str) -> dict:
    return {
        "pillar": _RESULT_PILLAR,
        "table": table,
        "status": status,
        "value": value,
        "message": message,
        "timestamp": ts,
    }
