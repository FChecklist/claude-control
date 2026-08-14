import json, re, glob

# load PR list
prs = json.load(open('tmp/open_prs.json'), strict=False)
pr_by_num = {p['number']: p for p in prs}

nums = [237,234,215,214,206,194,186,159,158,153,150,147,142,125,116,114,111,102,98,91,83,75,72]

results = []
for n in nums:
    p = pr_by_num[n]
    head = p['headRefOid']
    mergeable = p['mergeable']
    mergeState = p['mergeStateStatus']
    comments = []
    try:
        with open(f'tmp/comments_{n}.jsonl') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                comments.append(json.loads(line, strict=False))
    except FileNotFoundError:
        pass
    # sort by created time
    comments.sort(key=lambda c: c.get('created',''))
    audit_comments = [c for c in comments if re.search(r'\bAUDIT\s*:\s*(PASS|FAIL)\b', c.get('body') or '', re.I)]
    latest_audit = audit_comments[-1] if audit_comments else None
    verdict = None
    audited_sha = None
    if latest_audit:
        body = latest_audit['body']
        m = re.search(r'\bAUDIT\s*:\s*(PASS|FAIL)\b', body, re.I)
        verdict = m.group(1).upper() if m else None
        m2 = re.search(r'headRefOid[`\s]*[=:]\s*`?([0-9a-f]{7,40})', body)
        if m2:
            audited_sha = m2.group(1)
    sha_match = None
    if audited_sha:
        sha_match = head.startswith(audited_sha) or audited_sha.startswith(head[:len(audited_sha)])
        # more precise: compare up to min length
        L = min(len(audited_sha), len(head))
        sha_match = audited_sha[:L] == head[:L]
    results.append({
        'pr': n,
        'head': head,
        'mergeable': mergeable,
        'mergeState': mergeState,
        'num_comments': len(comments),
        'num_audit_comments': len(audit_comments),
        'latest_audit_author': latest_audit['author'] if latest_audit else None,
        'latest_audit_created': latest_audit['created'] if latest_audit else None,
        'verdict': verdict,
        'audited_sha': audited_sha,
        'sha_match': sha_match,
    })

for r in results:
    print(r)
