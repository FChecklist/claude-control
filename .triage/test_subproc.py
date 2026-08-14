import subprocess
r = subprocess.run(['git', 'diff', '5bc908cb7f28e62fb11a4849916c7fc850dccf0f', 'refs/prs/72', '--', 'ai-os/VERIDIAN_ARCHITECTURE_V2_PHASE_PLAN_2026-07-25.yaml'],
                    cwd='/opt/veridian/ai-os/tasks/task-20260814-060159-triage-and-dispose-the-pre-2026-08-08-st/workspace',
                    capture_output=True, text=True)
print('returncode', r.returncode)
print('stdout len', len(r.stdout))
print(repr(r.stdout[:500]))
print('stderr', r.stderr[:500])
