import json, subprocess, sys, re

def run(args, cwd):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def added_lines(repo_dir, mb, head, path):
    rc, out, err = run(['git', 'diff', mb, head, '--', path], repo_dir)
    lines = []
    for l in out.splitlines():
        if l.startswith('+++') or l.startswith('---'):
            continue
        if l.startswith('+'):
            content = l[1:].strip()
            if content and len(content) > 8:  # skip trivial/blank
                lines.append(content)
    return lines

def analyze(repo_dir, classified_path, main_ref, out_path):
    data = json.load(open(classified_path))
    report = []
    for p in data:
        n = p['number']
        mb = p['merge_base']
        head = f"refs/prs/{n}"
        file_reports = []
        total_added = 0
        total_matched = 0
        for f in p['files']:
            path = f['path']
            if f['identical_to_main']:
                continue
            if not f['exists_on_main']:
                file_reports.append({'path': path, 'status': 'missing_on_main'})
                continue
            al = added_lines(repo_dir, mb, head, path)
            rc, main_content, _ = run(['git', 'show', f'{main_ref}:{path}'], repo_dir)
            matched = sum(1 for l in al if l in main_content)
            total_added += len(al)
            total_matched += matched
            unmatched_sample = [l for l in al if l not in main_content][:5]
            file_reports.append({
                'path': path, 'status': 'differs',
                'added_lines': len(al), 'matched_in_main': matched,
                'unmatched_sample': unmatched_sample,
            })
        overlap_ratio = (total_matched / total_added) if total_added else None
        report.append({
            'number': n, 'title': p['title'], 'url': p['url'],
            'updated_at': p['updated_at'], 'head_ref': p['head_ref'],
            'total_added': total_added, 'total_matched': total_matched,
            'overlap_ratio': overlap_ratio,
            'files': file_reports,
        })
        print(f"#{n} added={total_added} matched={total_matched} ratio={overlap_ratio}", file=sys.stderr)
    json.dump(report, open(out_path, 'w'), indent=2)

if __name__ == '__main__':
    analyze(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
