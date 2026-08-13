import sys
sys.path.insert(0, "/opt/veridian/ai-os/tasks/task-20260813-132419-restore-the-stalled-dispatch-pipeline--p/workspace/veridian-scripts-work")
import dispatch_core as dc

print("running_worker_count:", dc.running_worker_count())
print("has_free_slot_detail:", dc.has_free_slot_detail())
print("has_resource_headroom_detail:", dc.has_resource_headroom_detail())
