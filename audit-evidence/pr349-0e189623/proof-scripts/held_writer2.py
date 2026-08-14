import sys, time
f = open(sys.argv[1], 'w')
f.write('live in-progress register copy data, actively being written')
f.flush()
time.sleep(15)
