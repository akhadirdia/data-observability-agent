from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


class SQLConnector:
    """Connecteur universel SQLAlchemy — Postgres, MySQL, SQLite, BigQuery."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Engine | None = None

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------

    def connect(self) -> Engine | None:
        """Crée et retourne le moteur SQLAlchemy. Retourne None si échec."""
        try:
            engine = create_engine(self._database_url)
            with engine.connect():
                pass  # validation de la connexion
            self._engine = engine
            logger.info(f"Connexion établie : {self._safe_url()}")
            return engine
        except Exception as exc:
            logger.error(f"Échec de connexion ({self._safe_url()}) : {exc}")
            return None

    def is_connected(self) -> bool:
        return self._engine is not None

    def ensure_connected(self) -> bool:
        if not self.is_connected():
            self.connect()
        return self.is_connected()

    # ------------------------------------------------------------------
    # Requêtes
    # ------------------------------------------------------------------

    def execute_query(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """Exécute une requête SQL et retourne un DataFrame. Retourne un DataFrame vide si échec."""
        if not self.ensure_connected():
            return pd.DataFrame()
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return pd.DataFrame(result.fetchall(), columns=list(result.keys()))
        except Exception as exc:
            logger.error(f"Erreur lors de l'exécution de la requête : {exc}\nQuery: {query[:200]}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Métadonnées
    # ------------------------------------------------------------------

    def get_table_list(self) -> list[str]:
        """Retourne la liste de toutes les tables disponibles."""
        if not self.ensure_connected():
            return []
        try:
            inspector = inspect(self._engine)
            return inspector.get_table_names()
        except Exception as exc:
            logger.error(f"Impossible de récupérer la liste des tables : {exc}")
            return []

    def get_column_metadata(self, table: str) -> list[dict]:
        """Retourne les métadonnées des colonnes : nom, type, nullable."""
        if not self.ensure_connected():
            return []
        try:
            inspector = inspect(self._engine)
            columns = inspector.get_columns(table)
            return [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                }
                for col in columns
            ]
        except Exception as exc:
            logger.error(f"Impossible de récupérer les colonnes de '{table}' : {exc}")
            return []

    def get_row_count(self, table: str) -> int | None:
        """Retourne le nombre de lignes d'une table. Retourne None si échec."""
        df = self.execute_query(f"SELECT COUNT(*) AS cnt FROM {table}")
        if df.empty:
            return None
        return int(df.iloc[0]["cnt"])

    # ------------------------------------------------------------------
    # Utilitaire
    # ------------------------------------------------------------------

    def _safe_url(self) -> str:
        """Masque le mot de passe dans l'URL pour les logs."""
        try:
            from sqlalchemy.engine import make_url
            url = make_url(self._database_url)
            return url.render_as_string(hide_password=True)
        except Exception:
            return self._database_url[:30] + "..."
