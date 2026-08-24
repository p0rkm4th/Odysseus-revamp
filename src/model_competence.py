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

    def recommend(self, owner, *, task_class, candidates, preferred=None, require_qualified=False):
        """Return an empirical, owner-scoped recommendation projection.

        This is deliberately advisory: it selects among caller-supplied model
        candidates and never changes capability, approval, or execution policy.
        A model with no evidence is never presented as qualified.
        """
        task = str(task_class or "general")[:160]
        rows = self.db.query(ModelCompetence).filter_by(owner=owner, task_class=task).all()
        by_key = {row.model_key: row for row in rows}
        normalized = []
        for candidate in candidates or []:
            if isinstance(candidate, str):
                candidate = {"model_key": candidate, "profile": candidate}
            item = dict(candidate)
            keys = [str(item.get(key) or "") for key in ("model_key", "model", "profile", "name")]
            evidence = next((by_key[key] for key in keys if key in by_key), None)
            item["model_key"] = str(item.get("model_key") or item.get("profile") or item.get("model") or item.get("name") or "unknown")[:300]
            item["competence"] = serialize(evidence) if evidence is not None else {
                "model_key": item["model_key"], "task_class": task, "sample_count": 0,
                "success_rate": 0, "recent_success_rate": 0, "qualification": "unknown",
                "failure_classes": [], "evidence_refs": []
            }
            normalized.append(item)
        if not normalized:
            return {"task_class": task, "selected": None, "alternatives": [], "reason_codes": ["no_candidates"], "evidence_backed": False}

        def rank(item):
            comp = item["competence"]
            qualification = comp.get("qualification")
            qrank = {"qualified": 4, "experimental": 2, "unknown": 1, "degraded": 0, "disqualified": -1}.get(qualification, -1)
            preferred_rank = 1 if preferred and item["model_key"] == preferred else 0
            latency = item.get("latency_ms") or comp.get("latency_ms") or 10**9
            return (qrank, int(comp.get("success_rate") or 0), int(comp.get("sample_count") or 0), preferred_rank, -int(latency))

        eligible = [item for item in normalized if item["competence"].get("qualification") not in {"disqualified", "degraded"}]
        qualified = [item for item in eligible if item["competence"].get("qualification") == "qualified"]
        pool = qualified if qualified else ([] if require_qualified else eligible)
        if not pool:
            selected = None
            reason_codes = ["no_qualified_candidate"]
        else:
            selected = sorted(pool, key=rank, reverse=True)[0]
            comp = selected["competence"]
            reason_codes = ["empirical_competence_selected" if comp.get("qualification") == "qualified" else "no_qualified_evidence_fallback"]
            if preferred and selected["model_key"] != preferred:
                reason_codes.append("preferred_model_not_sufficiently_qualified")
        alternatives = [{"model_key": item["model_key"], "profile": item.get("profile"), "qualification": item["competence"].get("qualification"), "sample_count": item["competence"].get("sample_count", 0), "success_rate": item["competence"].get("success_rate", 0)} for item in sorted(normalized, key=rank, reverse=True)]
        selected_competence = selected["competence"] if selected else None
        return {
            "task_class": task,
            "selected": {"model_key": selected["model_key"], "profile": selected.get("profile"), "competence": selected["competence"]} if selected else None,
            "alternatives": alternatives,
            "reason_codes": reason_codes,
            "evidence_summary": {
                "selected_sample_count": int((selected_competence or {}).get("sample_count") or 0),
                "selected_success_rate": int((selected_competence or {}).get("success_rate") or 0),
                "selected_recent_success_rate": int((selected_competence or {}).get("recent_success_rate") or 0),
                "selected_failure_classes": list((selected_competence or {}).get("failure_classes") or []),
                "selected_evidence_refs": list((selected_competence or {}).get("evidence_refs") or []),
            },
            "evidence_backed": bool(selected and selected["competence"].get("qualification") == "qualified"),
            "authority_unchanged": True,
        }
