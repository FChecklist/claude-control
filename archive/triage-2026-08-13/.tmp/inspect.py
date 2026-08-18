data = open('.tmp/open_prs.json','rb').read()
print(len(data))
print(repr(data[-300:]))
