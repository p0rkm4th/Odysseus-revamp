"""Mission projection over the canonical Work Goal/Run system."""
from core.work_models import WorkGoal, WorkRun
from src.work_engine import WorkEngine, WorkError, serialize


class MissionService:
    def __init__(self, db): self.db = db

    @staticmethod
    def is_mission(row):
        return str((row.constraints or {}).get("operating_mode") or "").lower() == "mission"

    @staticmethod
    def lifecycle(row):
        return {"draft":"DRAFT", "active":"ACTIVE", "paused":"PAUSED", "blocked":"BLOCKED", "completed":"COMPLETED", "failed":"FAILED", "cancelled":"CANCELLED"}.get(row.status, row.status.upper())

    def _one(self, owner, mission_id):
        row = self.db.query(WorkGoal).filter_by(owner=owner, id=mission_id).one_or_none()
        if row is None or not self.is_mission(row): raise WorkError("mission not found")
        return row

    def project(self, owner, row):
        result = serialize(row)
        result["lifecycle"] = self.lifecycle(row); result["objective"] = row.desired_outcome or row.title
        result["runs"] = [serialize(run) for run in self.db.query(WorkRun).filter_by(owner=owner, goal_id=row.id).order_by(WorkRun.updated_at.desc()).limit(50).all()]
        result["canonical_ref"] = f"goal://{row.id}"
        return result

    def list(self, owner, *, lifecycle=None, limit=200):
        rows = self.db.query(WorkGoal).filter_by(owner=owner).order_by(WorkGoal.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()
        result = [self.project(owner, row) for row in rows if self.is_mission(row)]
        return [row for row in result if not lifecycle or row["lifecycle"] == str(lifecycle).upper()]

    def create(self, owner, data):
        payload = dict(data); constraints = dict(payload.get("constraints") or {}); constraints["operating_mode"] = "mission"; payload["constraints"] = constraints
        row = WorkEngine(self.db).create_goal(owner, payload)
        return self.get(owner, row["id"])

    def get(self, owner, mission_id): return self.project(owner, self._one(owner, mission_id))

    def update(self, owner, mission_id, data):
        row = self._one(owner, mission_id); payload = dict(data)
        if "constraints" in payload:
            constraints = dict(payload["constraints"] or {}); constraints["operating_mode"] = "mission"; payload["constraints"] = constraints
        WorkEngine(self.db).update_goal(owner, row.id, payload)
        return self.get(owner, row.id)
