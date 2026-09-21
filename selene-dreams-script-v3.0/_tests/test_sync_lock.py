"""One Drive sync at a time. Added 2026-09-11 after the 15-minute tick and a
manual --sync raced and produced 9 duplicate '_2' downloads (~500 MB)."""
import os, sys, tempfile, time
sys.path.insert(0, ".")
import reel_drive

# Point the lock at a scratch path. The real one lives inside a synced folder
# that some environments will not let a test delete from, and a test that
# depends on that is testing the filesystem, not the lock.
reel_drive.LOCK_PATH = os.path.join(tempfile.mkdtemp(), "drive-sync.lock")

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

calls = []
reel_drive._sync = lambda state, svc=None: (calls.append(1), (1, 0))[1]

for p in (reel_drive.LOCK_PATH,):
    if os.path.exists(p): os.remove(p)

# a plain run works and cleans up after itself
r = reel_drive.sync({})
check("an uncontended sync runs", r == (1, 0) and len(calls) == 1, str(r))
check("the lock is released afterwards", not os.path.exists(reel_drive.LOCK_PATH))

# a second sync while one is held must NOT run
calls.clear()
outer = reel_drive._Lock().__enter__()
check("the lock was taken", outer.held)
r = reel_drive.sync({})
check("a concurrent sync is refused", r == (0, 0), str(r))
check("and does no work", len(calls) == 0, str(len(calls)))
outer.__exit__()
check("released again", not os.path.exists(reel_drive.LOCK_PATH))

# after release, syncing resumes
calls.clear()
reel_drive.sync({})
check("sync resumes once the lock is free", len(calls) == 1)

# a stale lock from a crashed run must expire on its own
with open(reel_drive.LOCK_PATH, "w") as f:
    f.write("99999")
old = time.time() - reel_drive.LOCK_STALE_SECONDS - 60
os.utime(reel_drive.LOCK_PATH, (old, old))
calls.clear()
r = reel_drive.sync({})
check("a stale lock is cleared, not obeyed forever", len(calls) == 1, str(r))
check("cleaned up", not os.path.exists(reel_drive.LOCK_PATH))

# a FRESH lock is still obeyed
with open(reel_drive.LOCK_PATH, "w") as f:
    f.write("99999")
calls.clear()
reel_drive.sync({})
check("a fresh lock is obeyed", len(calls) == 0)
os.remove(reel_drive.LOCK_PATH)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
