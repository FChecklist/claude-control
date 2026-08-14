#!/bin/bash
set -e
TESTROOT=$(mktemp -d /tmp/audit_reaper_lsofgap_XXXXXX)
mkdir -p "$TESTROOT/pm_sentinel_tick_live_process_dir"
python3 /tmp/held_writer2.py "$TESTROOT/pm_sentinel_tick_live_process_dir/superboss-register-copy.sqlite" &
BGPID=$!
sleep 1
python3 /tmp/set_old_mtime.py "$TESTROOT/pm_sentinel_tick_live_process_dir"
echo "before (process $BGPID still holding a file open inside this dir, cwd is NOT this dir):"
ls -la "$TESTROOT/pm_sentinel_tick_live_process_dir"
python3 /tmp/veridian-scripts-audit/reap_stale_test_scratch.py --tmp-dir "$TESTROOT"
echo "after:"
ls -la "$TESTROOT" || echo "(dir gone)"
wait $BGPID 2>/dev/null || true
rm -rf "$TESTROOT"
