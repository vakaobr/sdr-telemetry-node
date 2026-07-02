"""Enrichment chain (FR-2): local DB → cache → optional online — always fail-soft.

Offline answers (registration, type, operator-by-prefix, country) come from
the local DB + bundled static data. Online (adsbdb) adds route + operator
refinement, cached with a TTL. A lookup NEVER blocks the delta path — the
engine schedules it and applies the result on a later tick.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import Config
from app.enrich import localdb, staticdata
from app.persist.db import Database

log = logging.getLogger("gateway.enrich")

ADSBDB_URL = "https://api.adsbdb.com/v0/callsign/{callsign}"
NEGATIVE_TTL_S = 6 * 3600  # remember online misses for a while


class Enricher:
    def __init__(self, config: Config, db: Database, client: httpx.AsyncClient | None = None):
        self._cfg = config
        self._db = db
        self._client = client or httpx.AsyncClient(timeout=5)
        self.military_flag_of: dict[str, bool] = {}  # icao → db_flags bit0 (rules input)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def enrich(self, icao: str, callsign: str | None) -> dict:
        """Full chain. Returns an Enrichment-shaped dict (nulls where unknown)."""
        result: dict = {
            "registration": None,
            "typeCode": None,
            "typeName": None,
            "operator": None,
            "country": staticdata.country_for_hex(icao),
            "route": None,
            "photoUrl": None,
        }

        # 1) offline aircraft DB
        local = await localdb.lookup(self._db, icao)
        if local:
            reg, type_code, flags = local
            result["registration"] = reg
            result["typeCode"] = type_code
            result["typeName"] = staticdata.type_name_for(type_code)
            self.military_flag_of[icao] = bool(flags & 1)

        # 2) offline operator by callsign prefix
        result["operator"] = staticdata.operator_for_callsign(callsign)

        # 3) cached online fields
        cached = await self._cache_get(icao)
        if cached:
            for k in ("route", "operator", "photoUrl"):
                result[k] = cached.get(k) or result[k]
            # cache may also fill gaps the local DB lacked
            for k in ("registration", "typeCode", "typeName"):
                result[k] = result[k] or cached.get(k)
            return result

        # 4) online (route + operator), fail-soft, negative-cached
        if self._cfg.enrichment.online.enabled and callsign:
            online = await self._fetch_online(callsign)
            await self._cache_put(icao, {**result, **(online or {})}, miss=online is None)
            if online:
                result["route"] = online.get("route") or result["route"]
                result["operator"] = online.get("operator") or result["operator"]
        return result

    # -- online ----------------------------------------------------------------

    async def _fetch_online(self, callsign: str) -> dict | None:
        try:
            r = await self._client.get(ADSBDB_URL.format(callsign=callsign.strip()))
            if r.status_code != 200:
                return None
            fr = (r.json().get("response") or {}).get("flightroute") or {}
            origin = (fr.get("origin") or {}).get("icao_code")
            dest = (fr.get("destination") or {}).get("icao_code")
            airline = (fr.get("airline") or {}).get("name")
            return {
                "route": f"{origin} → {dest}" if origin and dest else None,
                "operator": airline,
            }
        except (httpx.HTTPError, ValueError) as e:
            log.debug("online enrichment failed for %s: %s", callsign, e)
            return None  # offline / API gone — the chain already has local values

    # -- cache -------------------------------------------------------------------

    async def _cache_get(self, icao: str) -> dict | None:
        cur = await self._db.conn.execute(
            "SELECT registration, type_code, type_name, operator, country, route, "
            "photo_url, fetched_at, ttl_s FROM enrichment_cache WHERE icao=?",
            (icao,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        if row[7] + row[8] < int(time.time()):
            return None  # expired
        return {
            "registration": row[0],
            "typeCode": row[1],
            "typeName": row[2],
            "operator": row[3],
            "country": row[4],
            "route": row[5],
            "photoUrl": row[6],
        }

    async def _cache_put(self, icao: str, e: dict, miss: bool) -> None:
        ttl = NEGATIVE_TTL_S if miss else self._cfg.enrichment.online.cache_ttl_days * 86400
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO enrichment_cache VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                icao,
                e.get("registration"),
                e.get("typeCode"),
                e.get("typeName"),
                e.get("operator"),
                e.get("country"),
                e.get("route"),
                e.get("photoUrl"),
                "adsbdb" if not miss else "miss",
                int(time.time()),
                ttl,
            ),
        )
        await self._db.conn.commit()
