"""
app.database.migrations
========================
Schema creation and forward-only migrations.

Every schema change is expressed as a numbered migration.  The current
schema version is stored in the ``schema_migrations`` table and compared
on every startup to apply any pending migrations automatically.
"""

from __future__ import annotations

import logging
from app.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Migration registry
# Each entry: (version: int, description: str, sql: str)
# ---------------------------------------------------------------------------
MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "Initial schema",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            event_name      TEXT NOT NULL DEFAULT '',
            description     TEXT DEFAULT '',
            project_dir     TEXT NOT NULL,
            database_path   TEXT NOT NULL,
            stage           TEXT NOT NULL DEFAULT 'created',
            status          TEXT NOT NULL DEFAULT 'draft',
            total_participants  INTEGER DEFAULT 0,
            total_certificates  INTEGER DEFAULT 0,
            matched_count       INTEGER DEFAULT 0,
            emails_sent         INTEGER DEFAULT 0,
            emails_failed       INTEGER DEFAULT 0,
            emails_pending      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_opened_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS participants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_id     TEXT NOT NULL UNIQUE,
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            full_name       TEXT NOT NULL,
            email           TEXT NOT NULL,
            phone           TEXT DEFAULT '',
            college         TEXT DEFAULT '',
            department      TEXT DEFAULT '',
            designation     TEXT DEFAULT '',
            certificate_type TEXT DEFAULT '',
            remarks         TEXT DEFAULT '',
            certificate_id  INTEGER DEFAULT 0,
            match_status    TEXT NOT NULL DEFAULT 'not_assigned',
            match_confidence REAL DEFAULT 0.0,
            email_status    TEXT NOT NULL DEFAULT 'pending',
            email_sent_at   TIMESTAMP,
            email_attempts  INTEGER DEFAULT 0,
            email_error     TEXT DEFAULT '',
            is_deleted      INTEGER DEFAULT 0,
            import_source   TEXT DEFAULT 'manual',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id              INTEGER NOT NULL REFERENCES projects(id),
            original_filename       TEXT NOT NULL,
            original_file_path      TEXT NOT NULL,
            renamed_filename        TEXT DEFAULT '',
            renamed_file_path       TEXT DEFAULT '',
            detected_name           TEXT DEFAULT '',
            extraction_method       TEXT DEFAULT 'failed',
            confidence              REAL DEFAULT 0.0,
            raw_extracted_text      TEXT DEFAULT '',
            status                  TEXT DEFAULT 'pending',
            original_detected_name  TEXT DEFAULT '',
            manually_corrected      INTEGER DEFAULT 0,
            corrected_at            TIMESTAMP,
            is_ignored              INTEGER DEFAULT 0,
            is_duplicate            INTEGER DEFAULT 0,
            duplicate_of_id         INTEGER DEFAULT 0,
            failure_reason          TEXT DEFAULT '',
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS certificate_mappings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            participant_id  INTEGER NOT NULL REFERENCES participants(id),
            certificate_id  INTEGER NOT NULL REFERENCES certificates(id),
            match_method    TEXT NOT NULL DEFAULT 'auto',
            confidence      REAL DEFAULT 0.0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(participant_id),
            UNIQUE(certificate_id)
        );

        CREATE TABLE IF NOT EXISTS email_templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id),
            name        TEXT NOT NULL,
            is_active   INTEGER DEFAULT 0,
            subject     TEXT DEFAULT '',
            body_html   TEXT DEFAULT '',
            version     INTEGER DEFAULT 1,
            description TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS template_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id     INTEGER NOT NULL REFERENCES email_templates(id),
            version_number  INTEGER NOT NULL,
            subject         TEXT DEFAULT '',
            body_html       TEXT DEFAULT '',
            saved_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note            TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS email_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER NOT NULL REFERENCES projects(id),
            queue_position  INTEGER NOT NULL,
            participant_id  INTEGER NOT NULL REFERENCES participants(id),
            certificate_id  INTEGER NOT NULL REFERENCES certificates(id),
            template_id     INTEGER NOT NULL REFERENCES email_templates(id),
            to_email        TEXT NOT NULL,
            to_name         TEXT NOT NULL DEFAULT '',
            subject         TEXT NOT NULL,
            body_html       TEXT NOT NULL,
            attachment_path TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            attempts        INTEGER DEFAULT 0,
            last_attempt_at TIMESTAMP,
            sent_at         TIMESTAMP,
            error_message   TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id),
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            module      TEXT NOT NULL,
            action      TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            metadata    TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS app_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER DEFAULT 0,
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level       TEXT NOT NULL,
            module      TEXT NOT NULL,
            message     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS backups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id),
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            path        TEXT NOT NULL,
            trigger     TEXT NOT NULL DEFAULT 'auto',
            size_bytes  INTEGER DEFAULT 0
        );
        """,
    ),
]


class MigrationManager:
    """Applies pending schema migrations in version order."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def migrate(self) -> None:
        """Run all pending migrations."""
        self._ensure_migrations_table()
        applied = self._applied_versions()
        for version, description, sql in MIGRATIONS:
            if version not in applied:
                logger.info("Applying migration v%d: %s", version, description)
                with self._db.transaction() as cur:
                    cur.executescript(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                        (version, description),
                    )
                logger.info("Migration v%d applied successfully.", version)

    def _ensure_migrations_table(self) -> None:
        with self._db.transaction() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _applied_versions(self) -> set[int]:
        with self._db.read() as cur:
            rows = cur.execute("SELECT version FROM schema_migrations").fetchall()
        return {row["version"] for row in rows}


# Alias for backward compatibility with app controllers
SchemaMigrator = MigrationManager
