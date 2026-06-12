"""SQLite access (WAL, single writer = this process — ADR-005) + migrations.

Forward-only migrations: ordered NNN_*.sql files applied at boot inside a
transaction each; a pre-migration backup copy is taken (rollback artifact,
03_PROJECT_SPEC §5). Gateway refuses to start on a schema newer than it knows.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

import aiosqlite

log = logging.getLogger("gateway.persist")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIG_RE = re.compile(r"^(\d{3})_.+\.sql$")


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database.open() not awaited"
        return self._conn

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._migrate()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # -- migrations -----------------------------------------------------------

    async def _migrate(self) -> None:
        conn = self.conn
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        cur = await conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cur.fetchone()
        current = row[0] or 0

        migrations = sorted(
            (int(m.group(1)), p)
            for p in MIGRATIONS_DIR.glob("*.sql")
            if (m := _MIG_RE.match(p.name))
        )
        known_max = migrations[-1][0] if migrations else 0
        if current > known_max:
            raise RuntimeError(
                f"database schema v{current} is newer than this build knows (v{known_max}) "
                f"— refusing to start; restore the matching version or the .pre-* backup"
            )

        for version, path in migrations:
            if version <= current:
                continue
            if self.path.exists() and current > 0:
                backup = self.path.with_name(f"{self.path.name}.pre-{version:03d}")
                if not backup.exists():
                    shutil.copy2(self.path, backup)  # rollback artifact
            log.info("applying migration %03d (%s)", version, path.name)
            await conn.executescript(path.read_text())
            await conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            await conn.commit()
            current = version
