import json, subprocess, sys, os

def run(args, cwd):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def classify_repo(repo_dir, pr_list_path, out_path, main_ref='origin/main'):
    prs = json.load(open(pr_list_path))
    results = []
    for p in prs:
        n = p['number']
        head = f'refs/prs/{n}'
        rc, mb, err = run(['git', 'merge-base', main_ref, head], repo_dir)
        if rc != 0:
            results.append({**p, 'error': f'merge-base failed: {err}'})
            continue
        mb = mb.strip()

        # full tree diff between current main tip and PR head
        rc, full_diff, err = run(['git', 'diff', '--stat', main_ref, head], repo_dir)
        full_diff_empty = (full_diff.strip() == '')

        # files changed by the PR relative to merge-base (the PR's own contribution)
        rc, changed_files_out, err = run(['git', 'diff', '--name-status', mb, head], repo_dir)
        changed = []
        for line in changed_files_out.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split('\t')
            status = parts[0]
            path = parts[-1]
            changed.append({'status': status, 'path': path})

        file_info = []
        for c in changed:
            path = c['path']
            # does file exist on main tip?
            rc_show, main_content, _ = run(['git', 'show', f'{main_ref}:{path}'], repo_dir)
            exists_on_main = (rc_show == 0)
            rc_show2, pr_content, _ = run(['git', 'show', f'{head}:{path}'], repo_dir)
            exists_on_pr_head = (rc_show2 == 0)
            identical = exists_on_main and exists_on_pr_head and (main_content == pr_content)
            last_commit = None
            if exists_on_main:
                rc3, lc, _ = run(['git', 'log', '-1', '--format=%H', main_ref, '--', path], repo_dir)
                last_commit = lc.strip() or None
            file_info.append({
                'path': path, 'pr_status': c['status'],
                'exists_on_main': exists_on_main,
                'exists_on_pr_head': exists_on_pr_head,
                'identical_to_main': identical,
                'main_last_commit': last_commit,
            })

        results.append({
            'number': n, 'title': p['title'], 'updated_at': p['updated_at'],
            'head_ref': p['head_ref'], 'url': p['url'], 'merge_base': mb,
            'full_diff_empty': full_diff_empty,
            'files': file_info,
        })
        print(f"processed {n}: full_diff_empty={full_diff_empty} files={len(file_info)}", file=sys.stderr)

    json.dump(results, open(out_path, 'w'), indent=2)

if __name__ == '__main__':
    repo_dir = sys.argv[1]
    pr_list = sys.argv[2]
    out = sys.argv[3]
    main_ref = sys.argv[4] if len(sys.argv) > 4 else 'origin/main'
    classify_repo(repo_dir, pr_list, out, main_ref)
