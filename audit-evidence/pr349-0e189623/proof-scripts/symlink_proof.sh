#!/bin/bash
set -e
TESTROOT=$(mktemp -d /tmp/audit_reaper_proof_XXXXXX)
mkdir -p "$TESTROOT/real_target_data"
echo "precious live data" > "$TESTROOT/real_target_data/register.sqlite"
ln -s "$TESTROOT/real_target_data" "$TESTROOT/pm_sentinel_tick_symlink_attack"
python3 /tmp/set_old_mtime.py "$TESTROOT/pm_sentinel_tick_symlink_attack"
echo "before:"
ls -la "$TESTROOT"
python3 /tmp/veridian-scripts-audit/reap_stale_test_scratch.py --tmp-dir "$TESTROOT"
echo "after:"
ls -la "$TESTROOT"
echo "target data still present?"
cat "$TESTROOT/real_target_data/register.sqlite" 2>&1
rm -rf "$TESTROOT"
