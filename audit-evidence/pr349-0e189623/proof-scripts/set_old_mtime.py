import os, sys, time
p = sys.argv[1]
old = time.time() - 3 * 3600
os.utime(p, (old, old), follow_symlinks=False)
