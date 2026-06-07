"""SQLite revolution store — a generic time-series of wheel revolutions.

One row per revolution, tagged with the source detector ('camera' today; 'hall'
when the GPIO sensor lands) and the instantaneous rpm at that edge. Everything
the history views need — counts, avg speed, activity sessions — derives from this
one table. Distance is `revs * wheel_circumference_m`, applied by the caller:
circumference is a config value, not stored here, so the table stays dimensionless
and source-agnostic.

Two counts, deliberately separate:
  * lifetime — every revolution ever, including the pre-SQLite total carried over
    from the old state.json (`lifetime_offset`). Never decreases.
  * displayed — the big resettable number in the UI. `reset_counter` rebaselines
    it (stamps `counter_reset_ts`, zeroes `counter_offset`) WITHOUT deleting
    history, so a reset never touches the stored events or the lifetime total.

A single connection (WAL, check_same_thread=False) guarded by a re-usable lock —
the pipeline thread writes a few rows per second at most and the web threadpool
reads; at cat-wheel volumes (a few thousand rows/day) contention is a non-issue.
The lock matters because one sqlite3 connection is NOT safe under concurrent use.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class RevolutionStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS rev (ts REAL NOT NULL, source TEXT NOT NULL, rpm REAL);
            CREATE INDEX IF NOT EXISTS rev_ts ON rev(ts);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            """
        )
        self._db.commit()

    # --- meta helpers (caller holds the lock) ---

    def _meta_get(self, key: str) -> str | None:
        row = self._db.execute("SELECT v FROM meta WHERE k = ?", (key,)).fetchone()
        return row[0] if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (key, value),
        )

    def _count(self, since: float | None = None, source: str | None = None) -> int:
        q, args = "SELECT COUNT(*) FROM rev WHERE 1=1", []
        if since is not None:
            q += " AND ts >= ?"
            args.append(since)
        if source is not None:
            q += " AND source = ?"
            args.append(source)
        return int(self._db.execute(q, args).fetchone()[0])

    # --- writes ---

    def record_many(self, source: str, rows: list[tuple[float, float | None]]) -> None:
        """Append revolutions for one source. rows = [(wall_clock_ts, rpm)]."""
        if not rows:
            return
        with self._lock:
            self._db.executemany(
                "INSERT INTO rev(ts, source, rpm) VALUES(?, ?, ?)",
                [(ts, source, rpm) for ts, rpm in rows],
            )
            self._db.commit()

    def reset_counter(self, now: float) -> None:
        """Rebaseline the displayed counter to zero — history is left intact."""
        with self._lock:
            self._meta_set("counter_offset", "0")
            self._meta_set("counter_reset_ts", repr(now))
            self._db.commit()

    # --- reads ---

    def count(self, since: float | None = None, source: str | None = None) -> int:
        with self._lock:
            return self._count(since, source)

    def displayed_count(self, source: str | None = None) -> int:
        """The resettable UI counter: events since the last reset, plus whatever
        carryover (pre-SQLite total) the reset baseline still includes."""
        with self._lock:
            offset = int(self._meta_get("counter_offset") or 0)
            reset = self._meta_get("counter_reset_ts")
            since = float(reset) if reset else None
            return offset + self._count(since=since, source=source)

    def history(self, frm: float, to: float, bucket_s: int) -> list[dict]:
        """Revolutions bucketed into fixed time windows. avg/peak rpm skip the
        NULL-rpm rows (the first edge of a run) automatically."""
        with self._lock:
            cur = self._db.execute(
                """
                SELECT CAST(ts / ? AS INT) * ? AS bucket, COUNT(*), AVG(rpm), MAX(rpm)
                FROM rev WHERE ts >= ? AND ts < ?
                GROUP BY bucket ORDER BY bucket
                """,
                (bucket_s, bucket_s, frm, to),
            )
            return [
                {
                    "t": int(bucket),
                    "revs": int(n),
                    "avg_rpm": round(avg or 0.0, 1),
                    "peak_rpm": round(peak or 0.0, 1),
                }
                for bucket, n, avg, peak in cur.fetchall()
            ]

    def sessions(self, frm: float, to: float, gap_s: float) -> list[dict]:
        """Group events into activity sessions — maximal runs where consecutive
        revolutions are no more than gap_s apart (a still wheel logs nothing, so a
        gap means the cat stopped)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, rpm FROM rev WHERE ts >= ? AND ts < ? ORDER BY ts",
                (frm, to),
            ).fetchall()
        out: list[dict] = []
        cur: dict | None = None
        for ts, rpm in rows:
            if cur is None or ts - cur["end"] > gap_s:
                cur = {"start": ts, "end": ts, "revs": 0, "rpms": []}
                out.append(cur)
            cur["end"] = ts
            cur["revs"] += 1
            if rpm is not None:
                cur["rpms"].append(rpm)
        for s in out:
            rpms = s.pop("rpms")
            s["duration_s"] = round(s["end"] - s["start"], 1)
            s["avg_rpm"] = round(sum(rpms) / len(rpms), 1) if rpms else 0.0
            s["peak_rpm"] = round(max(rpms), 1) if rpms else 0.0
        return out

    def stats(self, today_start: float) -> dict:
        with self._lock:
            lifetime_offset = int(self._meta_get("lifetime_offset") or 0)
            offset = int(self._meta_get("counter_offset") or 0)
            reset = self._meta_get("counter_reset_ts")
            since = float(reset) if reset else None
            lifetime = lifetime_offset + self._count()
            displayed = offset + self._count(since=since)
            today = self._count(since=today_start)
            today_avg = self._db.execute(
                "SELECT AVG(rpm) FROM rev WHERE ts >= ?", (today_start,)
            ).fetchone()[0]
            first_ts, last_ts = self._db.execute("SELECT MIN(ts), MAX(ts) FROM rev").fetchone()
        return {
            "lifetime_revolutions": lifetime,
            "displayed": displayed,
            "today_revolutions": today,
            "today_avg_rpm": round(today_avg or 0.0, 1),
            "first_ts": first_ts,
            "last_ts": last_ts,
        }

    def migrate_from_json(self, json_path: Path) -> None:
        """One-time import of the old state.json total. The pre-SQLite count has
        no per-event timestamps, so it becomes a flat offset (both lifetime and
        the displayed counter) rather than fabricated events. No-op once events
        exist or the import has already run."""
        with self._lock:
            if self._meta_get("lifetime_offset") is not None or self._count() > 0:
                return
        try:
            data = json.loads(json_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        revolutions = data.get("revolutions")
        if not isinstance(revolutions, int):
            return
        with self._lock:
            self._meta_set("lifetime_offset", str(revolutions))
            self._meta_set("counter_offset", str(revolutions))
            self._db.commit()
        try:
            json_path.replace(json_path.with_name(json_path.name + ".migrated"))
        except OSError:
            pass

    def close(self) -> None:
        with self._lock:
            self._db.close()
