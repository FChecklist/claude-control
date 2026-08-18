import json, subprocess, sys, re

def run(args, cwd):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

DEF_RE = re.compile(r'^\s*(?:def|class)\s+(\w+)', re.MULTILINE)

def analyze(repo_dir, classified_path, main_ref, out_path, numbers):
    data = json.load(open(classified_path))
    by_num = {p['number']: p for p in data}
    report = []
    for n in numbers:
        p = by_num[n]
        head = f'refs/prs/{n}'
        file_results = []
        for f in p['files']:
            path = f['path']
            if not path.endswith('.py'):
                continue
            if f['identical_to_main']:
                continue
            rc, pr_content, _ = run(['git', 'show', f'{head}:{path}'], repo_dir)
            if rc != 0:
                continue
            pr_defs = set(DEF_RE.findall(pr_content))
            if not f['exists_on_main']:
                file_results.append({'path': path, 'exists_on_main': False, 'pr_defs': sorted(pr_defs), 'matched_defs': []})
                continue
            rc2, main_content, _ = run(['git', 'show', f'{main_ref}:{path}'], repo_dir)
            main_defs = set(DEF_RE.findall(main_content))
            matched = sorted(pr_defs & main_defs)
            unmatched = sorted(pr_defs - main_defs)
            file_results.append({
                'path': path, 'exists_on_main': True,
                'pr_defs': sorted(pr_defs), 'matched_defs': matched, 'unmatched_defs': unmatched,
            })
        report.append({'number': n, 'title': p['title'], 'file_results': file_results})
    json.dump(report, open(out_path, 'w'), indent=2)
    for r in report:
        print(f"#{r['number']} {r['title'][:50]}", file=sys.stderr)
        for fr in r['file_results']:
            print(f"   {fr['path']} exists_on_main={fr['exists_on_main']} matched={fr.get('matched_defs')} unmatched={fr.get('unmatched_defs', fr.get('pr_defs'))}", file=sys.stderr)

if __name__ == '__main__':
    repo_dir, classified_path, main_ref, out_path = sys.argv[1:5]
    numbers = [int(x) for x in sys.argv[5:]]
    analyze(repo_dir, classified_path, main_ref, out_path, numbers)
