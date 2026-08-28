"""Idempotent Cloud Run Job entry point for artifact expiry enforcement."""

import logging
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.artifacts import PrivateArtifactStore

logger = logging.getLogger("li.retention")


class RetentionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LI_OS_", extra="ignore")
    artifact_bucket: str
    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: str
    db_sslmode: str = "require"

    def connect_kwargs(self) -> dict[str, object]:
        return {"host": self.db_host, "port": self.db_port, "dbname": self.db_name,
                "user": self.db_user, "password": self.db_password,
                "sslmode": self.db_sslmode, "row_factory": dict_row}


def run() -> int:
    settings = RetentionSettings()
    store = PrivateArtifactStore(settings.artifact_bucket)
    deleted = 0
    with psycopg.connect(**settings.connect_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM li_api.list_expired_artifacts(%s);", (100,))
            for record in cursor.fetchall():
                object_name = record.get("storage_object")
                if object_name:
                    store.delete(str(object_name))
                cursor.execute("SELECT li_api.mark_artifact_expired(%s) AS marked;",
                               (UUID(str(record["artifact_id"])),))
                if cursor.fetchone()["marked"]:
                    deleted += 1
                    logger.info("artifact_expired",
                                extra={"artifact_id": str(record["artifact_id"])})
    logger.info("retention_complete", extra={"deleted_count": deleted})
    return deleted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
