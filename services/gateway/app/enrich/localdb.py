"""Offline aircraft database (tar1090-db aircraft.csv.gz → SQLite table).

The CSV is downloaded at install time by scripts/fetch-aircraft-db.sh (so we
redistribute nothing — open Q6 resolved by not bundling). At gateway boot,
if the table is empty (or the file is newer), it's imported in one
transaction: ~500k rows, one-time ~30–60 s on a Pi 3B, then pure indexed
lookups with zero RAM cost.

CSV format (semicolon-separated): icao;registration;type_code;db_flags
db_flags bit0 = military (tar1090 semantics) — feeds the interesting rules.
"""

from __future__ import annotations

import csv
import gzip
import logging
from pathlib import Path

from app.persist.db import Database

log = logging.getLogger("gateway.enrich.localdb")

DEFAULT_CSV = Path("/data/aircraft.csv.gz")


async def ensure_imported(db: Database, csv_path: Path = DEFAULT_CSV) -> int:
    """Import the CSV if present and newer than the last import. Returns row count."""
    cur = await db.conn.execute("SELECT COUNT(*) FROM aircraft_db")
    existing = (await cur.fetchone())[0]

    if not csv_path.exists():
        if existing == 0:
            log.warning(
                "no aircraft DB at %s — registration/type will rely on cache/online only; "
                "run scripts/fetch-aircraft-db.sh",
                csv_path,
            )
        return existing

    cur = await db.conn.execute("SELECT value FROM meta WHERE key='aircraft_db_mtime'")
    row = await cur.fetchone()
    mtime = str(int(csv_path.stat().st_mtime))
    if row and row[0] == mtime and existing > 0:
        return existing  # already imported this file

    log.info("importing aircraft DB from %s (one-time)…", csv_path)
    rows = 0
    with gzip.open(csv_path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        batch: list[tuple[str, str | None, str | None, int]] = []
        await db.conn.execute("DELETE FROM aircraft_db")
        for line in reader:
            if not line or len(line[0]) != 6:
                continue
            icao = line[0].lower()
            reg = line[1].strip() or None if len(line) > 1 else None
            type_code = line[2].strip() or None if len(line) > 2 else None
            try:
                flags = int(line[3]) if len(line) > 3 and line[3].strip() else 0
            except ValueError:
                flags = 0
            batch.append((icao, reg, type_code, flags))
            rows += 1
            if len(batch) >= 5000:
                await db.conn.executemany(
                    "INSERT OR REPLACE INTO aircraft_db VALUES (?,?,?,?)", batch
                )
                batch.clear()
        if batch:
            await db.conn.executemany("INSERT OR REPLACE INTO aircraft_db VALUES (?,?,?,?)", batch)
    await db.conn.execute("INSERT OR REPLACE INTO meta VALUES ('aircraft_db_mtime', ?)", (mtime,))
    await db.conn.commit()
    log.info("aircraft DB imported: %d rows", rows)
    return rows


async def lookup(db: Database, icao: str) -> tuple[str | None, str | None, int] | None:
    """→ (registration, type_code, db_flags) or None when unknown."""
    cur = await db.conn.execute(
        "SELECT registration, type_code, db_flags FROM aircraft_db WHERE icao=?",
        (icao.lower(),),
    )
    row = await cur.fetchone()
    return (row[0], row[1], row[2]) if row else None
