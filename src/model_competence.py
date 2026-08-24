"""Empirical competence projection derived from the canonical evaluation corpus."""
from core.evaluation_models import EvaluationRun, EvaluationScenario
from core.model_competence_models import ModelCompetence
from src.work_engine import ident, now, serialize


class ModelCompetenceService:
    def __init__(self, db): self.db=db

    @staticmethod
    def _model_key(model):
        if isinstance(model, dict): return str(model.get("name") or model.get("model") or model.get("profile") or "unknown")[:300]
        return str(model or "unknown")[:300]

    @staticmethod
    def _qualification(samples, rate):
        if samples <= 0: return "unknown"
        if samples < 3: return "experimental"
        if rate >= 80: return "qualified"
        if rate < 50: return "degraded"
        return "experimental"

    def recompute(self, owner, *, model_key=None, task_class=None):
        query=self.db.query(EvaluationRun, EvaluationScenario).join(EvaluationScenario, EvaluationScenario.id==EvaluationRun.scenario_id).filter(EvaluationRun.owner==owner, EvaluationScenario.owner==owner)
        aggregates={}
        for run, scenario in query.all():
            key=(self._model_key(run.model), scenario.task_class)
            if model_key and key[0] != model_key: continue
            if task_class and key[1] != task_class: continue
            bucket=aggregates.setdefault(key, {"runs":[],"failures":[]}); bucket["runs"].append(run); bucket["failures"].append(run.failure_category)
        result=[]
        for (key, task), bucket in aggregates.items():
            samples=len(bucket["runs"]); successes=sum(1 for run in bucket["runs"] if run.passed == 1); rate=round(successes*100/samples) if samples else 0
            recent=bucket["runs"][-5:]; recent_success=sum(1 for run in recent if run.passed==1); recent_rate=round(recent_success*100/len(recent)) if recent else 0
            row=self.db.query(ModelCompetence).filter_by(owner=owner, model_key=key, task_class=task).one_or_none()
            if row is None: row=ModelCompetence(id=ident("competence"), owner=owner, model_key=key, task_class=task); self.db.add(row)
            row.sample_count=samples; row.success_count=successes; row.success_rate=rate; row.recent_success_rate=recent_rate; row.failure_classes=sorted({x for x in bucket["failures"] if x and x!="none"}); row.qualification=self._qualification(samples,rate); row.evidence_refs=[run.id for run in bucket["runs"]][-100:]; row.last_evaluated_at=now(); self.db.flush(); result.append(serialize(row))
        self.db.commit(); return result

    def list(self, owner, *, task_class=None, qualification=None, limit=200):
        query=self.db.query(ModelCompetence).filter_by(owner=owner)
        if task_class: query=query.filter_by(task_class=task_class)
        if qualification: query=query.filter_by(qualification=qualification)
        return [serialize(row) for row in query.order_by(ModelCompetence.task_class, ModelCompetence.model_key).limit(max(1,min(int(limit),500))).all()]
