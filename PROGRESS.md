# PROGRESS -- task-20260723-145839-build-task-gateway-software

## Completed
- [x] scripts/task-gateway.py built: submit, start, log, close, register-automation, status
- [x] TEST_1 (submit): real instruction_id INS-20260723-150851-e127 returned
- [x] TEST_2 (status): real output matches task-20260723-142643-build-veridian-task-watchdog-service's actual task.yaml/systemctl state
- [x] TEST_3 (close): mismatched --audit-cmd rejected (verification_command_predefinition_rule enforced), exit code 1, real rejection message citing the predefined SUCCESS_CRITERIA
- [x] start's literal_template validation tested (rejects missing sections) without self-dispatching a real task
- [x] log subcommand tested against real task-20260723-145839 work_item -- ACT-20260723-150925-1d55
- [x] task-gateway.py registered via its own register-automation subcommand -- IDX-20260723-150929-2687
- [x] ai-os/STANDING_DIRECTIVE.yaml (live, /opt/veridian/ai-os/) bumped to v2.5, v2_task_gateway_software key added with real_test_evidence, backup at .bak-2026-07-23-v2.5-preupdate
- [x] ai-os/OWNER_DECISIONS_NEEDED_2026-07-23.yaml synced from task-20260723-120458's workspace branch into live /opt/veridian/ai-os/ (real sync gap, now fixed)

## Remaining
- [ ] None for this task's scope. No self-dispatch (standalone infrastructure task per spec).
