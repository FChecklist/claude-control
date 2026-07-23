#!/usr/bin/env python3
"""Real, exhaustive file inventory of the canonical VERIDIAN system-of-record (ai-os/ + scripts/),
using MASTER_INDEX.yaml's own exclusion_rules (prune, not -not-path, per its documented speed reason)
so it's fast enough to run on EVERY prompt, not just when something is suspected missing.

Root cause this fixes: files were being discovered reactively (one grep at a time, whenever a
question happened to surface one) instead of via one exhaustive, diffable inventory. This script
IS that inventory. It stores every file's path+size+mtime+hash in a register table and, on every
run, reports what's NEW, CHANGED, or MISSING since the last run -- so "finding a new file" becomes
a printed diff, not an accident three tasks later.

Scope, stated honestly: /opt/veridian/ai-os and /opt/veridian/scripts only (the canonical
system-of-record where every confusion this session happened -- SUPERBOSS_REGISTER.md,
preflight-guard.py, MASTER_INDEX.yaml gaps). Does NOT cover /opt/veridian/repos (application code --
already covered by FUNCTION_CATALOG.json/DATABASE_CATALOG.json/route catalogs, a different existing
mechanism) or /opt/veridian/workspace (ephemeral scratch, explicitly excluded, not system-of-record).
"""
import contextlib, fcntl, subprocess, sqlite3, hashlib, datetime, os, stat

DB = "/opt/veridian/ai-os/memory/superboss-register.sqlite"
_WRITE_LOCK_PATH = DB + ".writelock"
ROOTS = ["/opt/veridian/ai-os", "/opt/veridian/scripts"]


@contextlib.contextmanager
def _write_lock():
    """Same OS-level flock convention as scripts/superboss-register.py's own
    _write_lock() (root-caused 2026-07-23: this script used to open the DB
    directly, unserialized against every other writer -- confirmed by watchdog
    build task-20260723-142643's DB repair as the cause of the file_inventory
    table's recurring freelist/page corruption). Acquiring this BEFORE any
    sqlite connection means a killed/slow writer can never hold sqlite's own
    write lock mid-transaction."""
    os.makedirs(os.path.dirname(_WRITE_LOCK_PATH), exist_ok=True)
    with open(_WRITE_LOCK_PATH, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockfile, fcntl.LOCK_UN)


def ensure_table():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS file_inventory (
        path TEXT PRIMARY KEY, size INTEGER, mtime TEXT, hash16 TEXT,
        first_seen TEXT, last_seen TEXT
    )""")
    # item 22 (file_permission_change_tracking): permission bits, added
    # 2026-07-23. try/except keeps this idempotent on re-run against a DB
    # that already has the column, no separate migration script needed.
    try:
        conn.execute("ALTER TABLE file_inventory ADD COLUMN mode TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def list_files():
    # MASTER_INDEX.yaml's own documented pattern: -prune, not -not-path (real speed fix, proven this session)
    cmd = (
        "find " + " ".join(ROOTS) + " "
        r"\( -path '*/node_modules' -o -path '*/.git' -o -path '*/ai-os/tasks/*/workspace' \) -prune "
        r"-o -type f -print"
    )
    out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)
    return [f for f in out.stdout.strip().split("\n") if f]

def hash16(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return None

def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    files = list_files()

    with _write_lock():
        ensure_table()
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT path, hash16 FROM file_inventory")
        previous = {r["path"]: r["hash16"] for r in c.fetchall()}

        current_paths = set()
        new_files, changed_files = [], []

        for path in files:
            current_paths.add(path)
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            h = hash16(path)
            mode_str = format(stat.S_IMODE(st.st_mode), "04o")
            if path not in previous:
                new_files.append(path)
            elif previous[path] != h:
                changed_files.append(path)

            c.execute("SELECT 1 FROM file_inventory WHERE path=?", (path,))
            if c.fetchone():
                c.execute("UPDATE file_inventory SET size=?, mtime=?, hash16=?, last_seen=?, mode=? WHERE path=?",
                           (st.st_size, datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc).isoformat(), h, now, mode_str, path))
            else:
                c.execute("INSERT INTO file_inventory (path, size, mtime, hash16, first_seen, last_seen, mode) VALUES (?,?,?,?,?,?,?)",
                           (path, st.st_size, datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc).isoformat(), h, now, now, mode_str))

        missing_files = [p for p in previous if p not in current_paths]

        conn.commit()
        conn.close()

    print(f"INVENTORY RUN {now} -- {len(files)} files scanned under {ROOTS}")
    print(f"NEW this run: {len(new_files)}")
    for f in new_files[:30]:
        print("  + NEW:", f)
    print(f"CHANGED this run: {len(changed_files)}")
    for f in changed_files[:30]:
        print("  ~ CHANGED:", f)
    print(f"MISSING since last run: {len(missing_files)}")
    for f in missing_files[:30]:
        print("  - MISSING:", f)
    if not new_files and not changed_files and not missing_files:
        print("(no drift since last run)")

if __name__ == "__main__":
    main()
