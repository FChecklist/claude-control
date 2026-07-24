#!/usr/bin/env python3
"""
close_phase4_document_notification_data.py -- closes out
20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml's
phase_4_document_notification_data entry in place, same targeted-text-surgery
discipline ai-os-scripts/close_phase3_testing_engine.py already uses for its
own (different) plan file -- regex-scoped to this one phase's block so every
other phase's existing formatting/comments are left untouched.

Inserts `status:` + `status_detail:` right after phase_4's own `depends_on: []`
line (phase_4 currently has neither field -- Phase 1/2/3 above it in this same
plan file are the precedent for the richer status_detail mapping shape:
produced_by_task/completed_on/what_shipped/real_evidence/what_remains_for_later_phases,
not a single string, since this plan file's own phases already use that
richer shape and this script should match it, not close_phase3_testing_engine.py's
simpler single-string shape from a different plan file).

Run: python3 ai-os-scripts/close_phase4_document_notification_data.py
"""
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN_PATH = f"{REPO_ROOT}/ai-os/20_ENGINES_10_GATEWAYS_PHASE_PLAN_2026-07-24.yaml"

TASK_ID = "task-20260724-133622-phase4-unify-document-pipeline-pdf-gener"

STATUS_BLOCK = """    status: done
    status_detail:
      produced_by_task: {task_id}
      completed_on: '2026-07-24'
      repo_boundary_honestly_stated: "pdf-generator.ts, document-processing-engine.ts,
        document-extraction-service.ts, ocr-client.ts, services/doc-processing/main.py, and
        data-quality-engine.ts all live in the separate FChecklist/compliance-tracker repo -- per
        Phase 1/2/3's own established boundary (EXPECTED_OUTPUT requires a claude-control PR only),
        this task reads those files' real shapes to ground the shared facade/envelope schemas below but
        does not edit or commit to that repo. See ai-os/DOCUMENT_ENGINE_CONTRACT_2026-07-24.yaml's own
        repo_boundary_honestly_stated for the full reasoning."
      what_shipped:
        - "scripts/notify-owner.py added to claude-control git for the first time (real, live file
          copied from /opt/veridian/scripts/notify-owner.py) -- was already depended on by path from
          this repo's own scripts/automation_rule_engine.py (Phase 3) notify_owner action but never
          committed, same 'live but untracked' gap Phase 2 fixed for preflight-guard.py/risk-tier.py."
        - "ai-os/DOCUMENT_ENGINE_CONTRACT_2026-07-24.yaml: the Document Engine facade schema, grounded in
          the real, read shapes of pdf-generator.ts, services/doc-processing/main.py (PaddleOCR FastAPI,
          confirmed reachable only via ocr-client.ts's GitHub Actions repository_dispatch, never direct
          HTTP), document-extraction-service.ts, document-processing-engine.ts, and ocr-client.ts.
          Documents document_engine_operation_schema (5 operations) plus data_engine_finding -- the
          honest, evidence-backed record that no real multi-step data-movement need exists today (7 pure
          per-record data-quality-engine.ts call sites, zero ETL/pipeline references anywhere in either
          repo), so Engine 13 is closed by finding, not by building speculative ETL infrastructure, per
          this phase's own CONSTRAINTS."
        - "ai-os/NOTIFICATION_ENGINE_CONTRACT_2026-07-24.yaml: the shared notification_envelope_schema
          unifying notify-owner.py's real CLI (subject/body/dedupe_key/force, Resend email to the Owner)
          with app/api/notifications' real in-app shape (userId/title/message/type/isRead/metadata,
          confirmed 13 real but uncoordinated `db.insert(notifications).values()` call sites, no single
          createNotification() facade). Delivers the objective's own 'at minimum a shared schema +
          cross-call' floor for the in_app channel (documented, not fabricated cross-repo) while fully
          implementing the owner_email channel."
        - "scripts/document_engine.py (new): register-capabilities registers the 5 document operations
          into Phase 1's live capability_registry table; detect-duplicates is a direct, portable port of
          document-processing-engine.ts's detectDuplicateDocumentsByHash(); report-failure is the real,
          live cross-call realizing dependency_table's 'Document Engine (11) -> Notification Engine (12)'
          edge (previously status: planned) by firing scripts/automation_rule_engine.py evaluate-rules
          against a new document.pipeline_failed trigger type."
        - "scripts/notification_engine.py (new): send-owner implements notification_envelope_schema for
          the owner_email channel, mapping onto notify-owner.py's real CLI; validate-envelope checks an
          envelope's shape without side effects."
        - "A real automation_rule row (document-pipeline-failure-notify-owner, tied to the
          document_ocr_paddleocr capability_registry row) registered live via
          scripts/automation_rule_engine.py register-rule -- the first real notify_owner action-type
          dispatch this whole plan has live-tested end to end (Phase 3's own real_evidence only exercised
          log_action)."
      real_evidence:
        - "python3 scripts/document_engine.py register-capabilities: {{\\"schema_rows_found\\": 5,
          \\"registered_count\\": 5, \\"failed_count\\": 0}}. python3 scripts/superboss-register.py
          list-capabilities: count=10 (5 pre-existing Phase 1 rows + these 5)."
        - "python3 scripts/document_engine.py detect-duplicates --documents
          '[{{\\"id\\":\\"d1\\",\\"contentHash\\":\\"abc\\"}},{{\\"id\\":\\"d2\\",\\"contentHash\\":\\"abc\\"}},
          {{\\"id\\":\\"d3\\",\\"contentHash\\":\\"xyz\\"}}]': duplicate_groups=[[\\"d1\\",\\"d2\\"]] --
          exact port of detectDuplicateDocumentsByHash() confirmed correct."
        - "python3 scripts/automation_rule_engine.py register-rule --rule-name
          document-pipeline-failure-notify-owner --capability-name document_ocr_paddleocr --trigger-type
          document.pipeline_failed --action-type notify_owner ...: {{\\"registered\\": true}}."
        - "python3 scripts/document_engine.py report-failure --operation document_ocr_paddleocr --reason
          '...' --job-id phase4-verification-test: rules_fired=1, action_type=notify_owner, status=success,
          result.stdout='SENT: Resend message id=1c7ef7fd-df0f-4e2c-9d2e-7a36e53c0a55' -- the full
          Document-Engine-failure-to-real-email chain proven live, not simulated."
        - "python3 scripts/notification_engine.py send-owner ... --dedupe-key
          phase4-notification-engine-send-owner-test: first call SENT (Resend message id
          22749731-48a0-4e3f-8f72-b6354e631862), second call with the same --dedupe-key correctly
          SKIPPED (rate-limited, signature already notified within 1h) -- proves send-owner really
          delegates to notify-owner.py's own dedupe/rate-limit state rather than reimplementing it."
        - "python3 scripts/superboss-register.py query-knowledge
          \\"phase_4_document_notification_data\\" --tag domain:veridian-20-engine-10-gateway: found=2
          (this phase's own SUCCESS_CRITERIA check)."
      what_remains_for_later_phases:
        - "compliance-tracker's own PR: a createNotification() facade consolidating the 13 inline
          notifications-insert call sites, and ocr-client.ts actually calling something on job
          status=failed/timeout -- both out of this task's repo boundary, same deferral posture Phase
          1/2/3 used for their own TS-side gaps."
        - "phase_5_metadata_knowledge_consolidation (depends_on: []) remains open in this plan -- not
          attempted in this task."
"""


def close_phase(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    existing_block_re = re.compile(
        r"  - id: phase_4_document_notification_data\n(?:.*\n)*?(?=  - id: phase_5_metadata_knowledge_consolidation)"
    )
    existing_block = existing_block_re.search(text)
    if existing_block and "\n    status: done\n" in existing_block.group(0):
        print(f"{path}: phase_4 already shows status: done, no change")
        return False

    anchor_re = re.compile(
        r"(  - id: phase_4_document_notification_data\n"
        r"(?:.*\n)*?"
        r"    depends_on: \[\]\n)"
        r"(?=\n  - id: phase_5_metadata_knowledge_consolidation)",
        re.M,
    )
    status_block = STATUS_BLOCK.format(task_id=TASK_ID)
    new_text, n = anchor_re.subn(lambda m: m.group(1) + status_block, text, count=1)
    if n != 1:
        raise RuntimeError(f"could not locate phase_4 block anchor in {path} (matched {n} times)")

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"{path}: set phase_4_document_notification_data status: done")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] or [PLAN_PATH]
    for t in targets:
        close_phase(t)
