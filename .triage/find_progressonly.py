import json
data = json.load(open('vs_classified.json'))
progress_only = []
mixed_with_progress = []
for p in data:
    files = [f['path'] for f in p['files']]
    if files == ['PROGRESS.md']:
        progress_only.append(p['number'])
    elif 'PROGRESS.md' in files and len(files) > 1:
        mixed_with_progress.append((p['number'], files))
print('progress_only:', progress_only)
print('count', len(progress_only))
print('mixed_with_progress:')
for n, f in mixed_with_progress:
    print(' ', n, f)
