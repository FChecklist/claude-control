import json, sys

def summarize(path, label):
    data = json.load(open(path))
    superseded = []
    all_missing = []  # every changed file missing on main -> obsolete candidate
    mixed = []
    still_real = []
    for p in data:
        if p.get('full_diff_empty'):
            superseded.append(p)
            continue
        files = p['files']
        if not files:
            # no file diff vs merge-base but full_diff not empty? edge case
            mixed.append(p)
            continue
        n_identical = sum(1 for f in files if f['identical_to_main'])
        n_missing = sum(1 for f in files if not f['exists_on_main'] and f['pr_status'] != 'A')
        n_total = len(files)
        n_real_diff = n_total - n_identical  # files that still differ in some way
        # files that differ AND exist on main (real content diff, not just missing)
        n_real_content_diff = sum(1 for f in files if (not f['identical_to_main']) and f['exists_on_main'])
        n_missing_only = sum(1 for f in files if (not f['identical_to_main']) and (not f['exists_on_main']))
        entry = {
            'number': p['number'], 'title': p['title'], 'url': p['url'],
            'updated_at': p['updated_at'], 'head_ref': p['head_ref'],
            'n_total': n_total, 'n_identical': n_identical,
            'n_missing_only': n_missing_only, 'n_real_content_diff': n_real_content_diff,
        }
        if n_real_content_diff == 0 and n_missing_only > 0:
            # all remaining differing files are simply absent on main -> obsolete candidate
            entry['files'] = files
            all_missing.append(entry)
        elif n_real_content_diff > 0:
            entry['files'] = files
            still_real.append(entry)
        else:
            entry['files'] = files
            mixed.append(entry)

    print(f"=== {label} ===")
    print(f"SUPERSEDED (full diff vs main empty): {len(superseded)}")
    for p in superseded:
        print(f"  #{p['number']} {p['title'][:70]}")
    print(f"OBSOLETE-CANDIDATE (all remaining diffs are files missing on main): {len(all_missing)}")
    for p in all_missing:
        print(f"  #{p['number']} {p['title'][:70]}  missing_files={[f['path'] for f in p['files'] if not f['identical_to_main'] and not f['exists_on_main']]}")
    print(f"STILL-REAL (has real content diff in existing files): {len(still_real)}")
    for p in still_real:
        print(f"  #{p['number']} {p['title'][:70]}  n_real_content_diff={p['n_real_content_diff']}")
    print(f"MIXED/UNCLEAR: {len(mixed)}")
    for p in mixed:
        print(f"  #{p.get('number')} {p.get('title','')[:70]}")
    return superseded, all_missing, still_real, mixed

if __name__ == '__main__':
    summarize(sys.argv[1], sys.argv[2])
