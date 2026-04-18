from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from loguru import logger

from connectors.sql_connector import SQLConnector
from core.snapshot_store import append_history, get_history

_RESULT_PILLAR = "distribution"
_NULL_SIGMA_THRESHOLD = 2.0


def check_distribution(
    connector: SQLConnector,
    table: str,
    null_rate_threshold: float = 0.50,
) -> dict:
    """
    Calcule les statistiques de distribution pour chaque colonne numérique.
    Alerte si le taux de nulls dépasse null_rate_threshold ou la moyenne historique + 2σ.
    """
    ts = datetime.now(timezone.utc).isoformat()

    try:
        cols_meta = connector.get_column_metadata(table)
        if not cols_meta:
            return _result(table, "critical", {}, "Impossible de récupérer les colonnes.", ts)

        total_df = connector.execute_query(f"SELECT COUNT(*) AS cnt FROM {table}")
        total = int(total_df.iloc[0]["cnt"]) if not total_df.empty else 0

        if total == 0:
            return _result(table, "warning", {}, "Table vide — aucune distribution calculable.", ts)

        stats: dict[str, dict] = {}
        anomalies: list[str] = []

        for col in cols_meta:
            col_name = col["name"]
            col_type = col["type"].upper()
            is_numeric = any(t in col_type for t in ("INT", "REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"))

            null_df = connector.execute_query(
                f"SELECT SUM(CASE WHEN {col_name} IS NULL THEN 1 ELSE 0 END) AS nulls FROM {table}"
            )
            null_count = int(null_df.iloc[0]["nulls"]) if not null_df.empty else 0
            null_rate = null_count / total if total > 0 else 0.0

            col_stats: dict = {"null_rate": round(null_rate, 4), "total": total}

            if is_numeric:
                agg_df = connector.execute_query(
                    f"""SELECT
                        AVG(CAST({col_name} AS FLOAT)) AS mean,
                        MIN(CAST({col_name} AS FLOAT)) AS min,
                        MAX(CAST({col_name} AS FLOAT)) AS max,
                        SUM(CASE WHEN {col_name} = 0 THEN 1 ELSE 0 END) AS zeros
                    FROM {table}"""
                )
                if not agg_df.empty:
                    row = agg_df.iloc[0]
                    col_stats.update({
                        "mean": round(float(row["mean"]), 4) if row["mean"] is not None else None,
                        "min": row["min"],
                        "max": row["max"],
                        "zero_rate": round(int(row["zeros"]) / total, 4),
                    })

            # Détection anomalie null_rate via historique
            hist_key = f"dist_null:{table}:{col_name}"
            history = get_history(hist_key)
            append_history(hist_key, null_rate)

            if null_rate > null_rate_threshold:
                anomalies.append(f"{col_name}: taux nulls {null_rate:.0%} > seuil {null_rate_threshold:.0%}")
            elif len(history) >= 5:
                import statistics
                mean_h = statistics.mean(history)
                stdev_h = statistics.stdev(history) if len(history) > 1 else 0.0
                if stdev_h > 0 and null_rate > mean_h + _NULL_SIGMA_THRESHOLD * stdev_h:
                    anomalies.append(
                        f"{col_name}: taux nulls {null_rate:.0%} > moy {mean_h:.0%} + {_NULL_SIGMA_THRESHOLD}σ"
                    )

            stats[col_name] = col_stats

        if anomalies:
            has_critical = any(stats[c]["null_rate"] > null_rate_threshold for c in stats)
            status = "critical" if has_critical else "warning"
            msg = "Anomalies détectées : " + " | ".join(anomalies)
        else:
            status = "ok"
            msg = f"Distribution normale sur {len(cols_meta)} colonnes."

        return _result(table, status, stats, msg, ts)

    except Exception as exc:
        logger.error(f"[distribution:{table}] Erreur inattendue : {exc}")
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
