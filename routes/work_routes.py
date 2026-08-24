"""Authenticated Work Engine API."""
from __future__ import annotations
import asyncio
from typing import Any
from fastapi import APIRouter, Body, HTTPException, Query, Request
from core.database import SessionLocal
from core.work_models import WorkAction, WorkCommitment, WorkEvent, WorkGoal, WorkProject, WorkRun, WorkTask
from src.auth_helpers import require_user
from src.owner_identity import effective_storage_owner
from src.work_engine import WorkEngine, WorkError, serialize
from src.run_planner import RunPlanner

def setup_work_routes(*, session_factory=SessionLocal):
    router = APIRouter(prefix="/api/work", tags=["work-engine"])
    def owner(request):
        user = require_user(request); value = effective_storage_owner(user)
        if not value: raise HTTPException(401, "authenticated work owner required")
        return value, user
    async def tx(request, fn):
        value, user = owner(request)
        def run():
            with session_factory() as db:
                try: return fn(WorkEngine(db), value, user)
                except Exception:
                    db.rollback(); raise
        try: return await asyncio.to_thread(run)
        except WorkError as exc: raise HTTPException(409, str(exc)) from exc

    @router.get("/overview")
    async def overview(request: Request):
        return await tx(request, lambda svc, o, u: {"goals": svc.list_records(o, WorkGoal, status="active"), "projects": svc.list_records(o, WorkProject, status="active"), "tasks": svc.list_records(o, WorkTask), "runs": svc.list_records(o, WorkRun), "commitments": svc.list_records(o, WorkCommitment, status="open")})
    @router.get("/review")
    async def review(request: Request, horizon_hours: int = Query(48, ge=1, le=336)):
        return await tx(request, lambda svc, o, u: svc.life_review(o, horizon_hours=horizon_hours))
    @router.get("/context")
    async def context(request: Request, goal_id: str | None = None, project_id: str | None = None, task_id: str | None = None, run_id: str | None = None):
        return await tx(request, lambda svc, o, u: svc.context(o, goal_id=goal_id, project_id=project_id, task_id=task_id, run_id=run_id))
    @router.get("/goals")
    async def goals(request: Request, status: str | None = None): return {"goals": await tx(request, lambda svc,o,u: svc.list_records(o, WorkGoal, status=status))}
    @router.post("/goals", status_code=201)
    async def create_goal(request: Request, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_goal(o,payload))
    @router.patch("/goals/{goal_id}")
    async def update_goal(request: Request, goal_id: str, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.update_goal(o,goal_id,payload))
    @router.get("/missions")
    async def missions(request: Request, lifecycle: str | None = None):
        return {"missions": await tx(request, lambda svc,o,u: __import__("src.mission_projection", fromlist=["MissionService"]).MissionService(svc.db).list(o, lifecycle=lifecycle))}
    @router.post("/missions", status_code=201)
    async def create_mission(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.mission_projection", fromlist=["MissionService"]).MissionService(svc.db).create(o, payload))
    @router.get("/missions/{mission_id}")
    async def get_mission(request: Request, mission_id: str):
        return await tx(request, lambda svc,o,u: __import__("src.mission_projection", fromlist=["MissionService"]).MissionService(svc.db).get(o, mission_id))
    @router.patch("/missions/{mission_id}")
    async def update_mission(request: Request, mission_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.mission_projection", fromlist=["MissionService"]).MissionService(svc.db).update(o, mission_id, payload))
    @router.get("/execution-nodes")
    async def execution_nodes(request: Request, health: str | None = None):
        return {"nodes": await tx(request, lambda svc,o,u: __import__("src.execution_nodes", fromlist=["ExecutionNodeService"]).ExecutionNodeService(svc.db).list(o, health=health))}
    @router.post("/execution-nodes", status_code=201)
    async def register_execution_node(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.execution_nodes", fromlist=["ExecutionNodeService"]).ExecutionNodeService(svc.db).register(o, payload))
    @router.post("/execution-nodes/{node_key}/heartbeat")
    async def execution_node_heartbeat(request: Request, node_key: str, payload: dict[str, Any] = Body(default={} )):
        return await tx(request, lambda svc,o,u: __import__("src.execution_nodes", fromlist=["ExecutionNodeService"]).ExecutionNodeService(svc.db).heartbeat(o, node_key, health=str(payload.get("health") or "healthy"), utilization=payload.get("utilization") or {}))
    @router.post("/execution-nodes/select")
    async def select_execution_node(request: Request, payload: dict[str, Any] = Body(default={} )):
        return await tx(request, lambda svc,o,u: __import__("src.execution_nodes", fromlist=["ExecutionNodeService"]).ExecutionNodeService(svc.db).select(o, payload.get("requirements") or {}, limit=payload.get("limit", 1)))
    @router.get("/sandboxes")
    async def sandboxes(request: Request, status: str | None = None):
        return {"sandboxes": await tx(request, lambda svc,o,u: __import__("src.sandbox", fromlist=["SandboxService"]).SandboxService(svc.db).list(o, status=status))}
    @router.post("/sandboxes", status_code=201)
    async def create_sandbox(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.sandbox", fromlist=["SandboxService"]).SandboxService(svc.db).create(o, payload))
    @router.get("/sandboxes/{sandbox_id}")
    async def get_sandbox(request: Request, sandbox_id: str):
        return await tx(request, lambda svc,o,u: __import__("src.sandbox", fromlist=["SandboxService"]).SandboxService(svc.db).get(o, sandbox_id))
    @router.post("/sandboxes/{sandbox_id}/transition")
    async def transition_sandbox(request: Request, sandbox_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.sandbox", fromlist=["SandboxService"]).SandboxService(svc.db).transition(o, sandbox_id, payload.get("status"), artifacts=payload.get("artifacts"), error=payload.get("error")))
    @router.get("/grants")
    async def delegated_grants(request: Request, active_only: bool = False):
        return {"grants": await tx(request, lambda svc,o,u: __import__("src.delegated_grants", fromlist=["DelegatedGrantService"]).DelegatedGrantService(svc.db).list(o, active_only=active_only))}
    @router.post("/actions/{action_id}/grant", status_code=201)
    async def issue_delegated_grant(request: Request, action_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.delegated_grants", fromlist=["DelegatedGrantService"]).DelegatedGrantService(svc.db).issue(o, action_id, payload))
    @router.post("/grants/{grant_id}/consume")
    async def consume_delegated_grant(request: Request, grant_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.delegated_grants", fromlist=["DelegatedGrantService"]).DelegatedGrantService(svc.db).consume(o, grant_id, payload))
    @router.post("/grants/{grant_id}/revoke")
    async def revoke_delegated_grant(request: Request, grant_id: str):
        return await tx(request, lambda svc,o,u: __import__("src.delegated_grants", fromlist=["DelegatedGrantService"]).DelegatedGrantService(svc.db).revoke(o, grant_id))
    @router.post("/projects", status_code=201)
    async def create_project(request: Request, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_project(o,payload))
    @router.get("/projects")
    async def projects(request: Request, status: str | None = None): return {"projects": await tx(request, lambda svc,o,u: svc.list_records(o, WorkProject, status=status))}
    @router.post("/tasks", status_code=201)
    async def create_task(request: Request, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_task(o,payload))
    @router.post("/tasks/{task_id}/dependencies", status_code=201)
    async def dependency(request: Request, task_id: str, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.add_dependency(o,task_id,str(payload.get("depends_on_task_id") or "")))
    @router.get("/tasks")
    async def tasks(request: Request, status: str | None = None): return {"tasks": await tx(request, lambda svc,o,u: svc.list_records(o, WorkTask, status=status))}
    @router.post("/runs", status_code=201)
    async def create_run(request: Request, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_run(o,payload | {"requested_by": payload.get("requested_by") or u}))
    @router.get("/runs")
    async def runs(request: Request, status: str | None = None, domain: str | None = None): return {"runs": await tx(request, lambda svc,o,u: svc.list_records(o, WorkRun, status=status, domain=domain))}
    @router.get("/runs/{run_id}")
    async def get_run(request: Request, run_id: str): return await tx(request, lambda svc,o,u: svc.get_run(o,run_id))
    @router.get("/runs/{run_id}/preview")
    async def run_preview(request: Request, run_id: str):
        return await tx(request, lambda svc,o,u: RunPlanner(svc.db).compile(o, run_id))
    @router.post("/runs/{run_id}/validate")
    async def validate_run(request: Request, run_id: str):
        return await tx(request, lambda svc,o,u: RunPlanner(svc.db).validate(o, run_id))
    @router.post("/runs/{run_id}/execution/{lifecycle_state}")
    async def execution_step(request: Request, run_id: str, lifecycle_state: str, payload: dict[str, Any] = Body(default={})): 
        return await tx(request, lambda svc,o,u: svc.verified_execution_step(o, run_id, lifecycle_state, reason=payload.get("reason"), failure_class=payload.get("failure_class")))
    @router.post("/runs/{run_id}/cancel")
    async def cancel_run(request: Request, run_id: str, payload: dict[str, Any] = Body(default={})): 
        return await tx(request, lambda svc,o,u: svc.request_cancel(o, run_id, reason=str(payload.get("reason") or "operator requested cancellation")))
    @router.post("/runs/{run_id}/precheck")
    async def precheck_run(request: Request, run_id: str, payload: dict[str, Any] = Body(...)): 
        return await tx(request, lambda svc,o,u: svc.record_precheck(o, run_id, payload))
    @router.post("/runs/{run_id}/invalidate")
    async def invalidate_run(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.invalidate_state(o, run_id, payload.get("invalidations") or [], reason=str(payload.get("reason") or "mutation completed")))
    @router.post("/runs/{run_id}/verification")
    async def complete_verification(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.complete_verification(o, run_id, success=bool(payload.get("success")), details=payload.get("details") or {}, compensation_reference=payload.get("compensation_reference")))
    @router.post("/runs/{run_id}/compensation")
    async def complete_compensation(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.complete_compensation(o, run_id, success=bool(payload.get("success")), details=payload.get("details") or {}))
    @router.post("/claims/{claim_id}/contradictions", status_code=201)
    async def contradiction(request: Request, claim_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.record_contradiction(o, claim_id, str(payload.get("contradicting_claim_id") or ""), resolution=payload.get("resolution")))
    @router.get("/claims")
    async def claims(request: Request, subject_ref: str | None = None, claim_class: str | None = None, include_inactive: bool = False, limit: int = Query(100, ge=1, le=500)):
        return {"claims": await tx(request, lambda svc,o,u: svc.list_claims(o, subject_ref=subject_ref, claim_class=claim_class, include_inactive=include_inactive, limit=limit))}
    @router.get("/claims/{claim_id}/lineage")
    async def claim_lineage(request: Request, claim_id: str):
        return await tx(request, lambda svc,o,u: svc.claim_lineage(o, claim_id))
    @router.get("/runs/{run_id}/replay")
    async def replay_run(request: Request, run_id: str):
        return await tx(request, lambda svc,o,u: svc.reconstruct_run(o, run_id))
    @router.get("/runs/{run_id}/traces")
    async def run_traces(request: Request, run_id: str):
        def operation(svc, o, u):
            svc._one(WorkRun, o, run_id, "run")
            from src.observability import ObservabilityService
            return {"spans": ObservabilityService(svc.db).list_spans(o, run_id=run_id)}
        return await tx(request, operation)
    @router.get("/evaluations/scenarios")
    async def evaluation_scenarios(request: Request, domain: str | None = None):
        return await tx(request, lambda svc,o,u: __import__("src.evaluation_service", fromlist=["EvaluationService"]).EvaluationService(svc.db).list_scenarios(o, domain=domain))
    @router.get("/evaluations/failures")
    async def evaluation_failures(request: Request, status: str | None = None, taxonomy: str | None = None):
        return await tx(request, lambda svc,o,u: __import__("src.evaluation_service", fromlist=["EvaluationService"]).EvaluationService(svc.db).list_failures(o, status=status, taxonomy=taxonomy))
    @router.post("/incidents", status_code=201)
    async def create_incident(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).create_incident(o, payload))
    @router.get("/incidents")
    async def incidents(request: Request, status: str | None = None):
        return {"incidents": await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).list_incidents(o, status=status))}
    @router.get("/incidents/{incident_id}")
    async def get_incident(request: Request, incident_id: str):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).get_incident(o, incident_id))
    @router.patch("/incidents/{incident_id}")
    async def update_incident(request: Request, incident_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).update_incident(o, incident_id, payload))
    @router.post("/incidents/{incident_id}/hypotheses", status_code=201)
    async def add_hypothesis(request: Request, incident_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).add_hypothesis(o, incident_id, payload))
    @router.get("/incidents/{incident_id}/hypotheses")
    async def hypotheses(request: Request, incident_id: str):
        return {"hypotheses": await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).list_hypotheses(o, incident_id))}
    @router.patch("/incidents/{incident_id}/hypotheses/{hypothesis_id}")
    async def update_hypothesis(request: Request, incident_id: str, hypothesis_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).update_hypothesis(o, incident_id, hypothesis_id, payload))
    @router.post("/incidents/{incident_id}/evidence", status_code=201)
    async def add_incident_evidence(request: Request, incident_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).add_evidence(o, incident_id, payload))
    @router.post("/changes", status_code=201)
    async def create_change(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).create_change(o, payload))
    @router.get("/changes")
    async def changes(request: Request, status: str | None = None, incident_id: str | None = None):
        return {"changes": await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).list_changes(o, status=status, incident_id=incident_id))}
    @router.get("/changes/{change_id}")
    async def get_change(request: Request, change_id: str):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).get_change(o, change_id))
    @router.post("/changes/{change_id}/transition")
    async def transition_change(request: Request, change_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.incident_change", fromlist=["IncidentChangeService"]).IncidentChangeService(svc.db).transition_change(o, change_id, payload.get("status"), outcome=payload.get("outcome")))
    @router.post("/competence/recompute")
    async def recompute_competence(request: Request, payload: dict[str, Any] = Body(default={})): 
        return {"competence": await tx(request, lambda svc,o,u: __import__("src.model_competence", fromlist=["ModelCompetenceService"]).ModelCompetenceService(svc.db).recompute(o, model_key=payload.get("model_key"), task_class=payload.get("task_class")))}
    @router.get("/competence")
    async def competence(request: Request, task_class: str | None = None, qualification: str | None = None):
        return {"competence": await tx(request, lambda svc,o,u: __import__("src.model_competence", fromlist=["ModelCompetenceService"]).ModelCompetenceService(svc.db).list(o, task_class=task_class, qualification=qualification))}
    @router.get("/competence/matrix")
    async def competence_matrix(request: Request):
        return await tx(request, lambda svc,o,u: __import__("src.model_competence", fromlist=["ModelCompetenceService"]).ModelCompetenceService(svc.db).matrix(o))
    @router.post("/competence/recommend")
    async def recommend_competence(request: Request, payload: dict[str, Any] = Body(default={})):
        def operation(svc, o, u):
            task_class = str(payload.get("task_class") or "general_chat")
            candidates = payload.get("candidates") or []
            if not isinstance(candidates, list): raise WorkError("candidates must be a list")
            return __import__("src.model_competence", fromlist=["ModelCompetenceService"]).ModelCompetenceService(svc.db).recommend(o, task_class=task_class, candidates=candidates, preferred=payload.get("preferred"), require_qualified=bool(payload.get("require_qualified", False)))
        return await tx(request, operation)
    @router.post("/world/relationships", status_code=201)
    async def create_world_relationship(request: Request, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.world_model", fromlist=["WorldModelService"]).WorldModelService(svc.db).create_relationship(o, payload))
    @router.patch("/world/relationships/{relationship_id}")
    async def update_world_relationship(request: Request, relationship_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: __import__("src.world_model", fromlist=["WorldModelService"]).WorldModelService(svc.db).update_relationship(o, relationship_id, payload))
    @router.get("/world/relationships")
    async def world_relationships(request: Request, entity_ref: str | None = None, relation: str | None = None, status: str | None = None):
        return {"relationships": await tx(request, lambda svc,o,u: __import__("src.world_model", fromlist=["WorldModelService"]).WorldModelService(svc.db).list_relationships(o, entity_ref=entity_ref, relation=relation, status=status))}
    @router.get("/world/entities/{entity_ref:path}/neighbors")
    async def world_neighbors(request: Request, entity_ref: str, depth: int = Query(1, ge=1, le=3)):
        return await tx(request, lambda svc,o,u: __import__("src.world_model", fromlist=["WorldModelService"]).WorldModelService(svc.db).neighbors(o, entity_ref, depth=depth))
    @router.get("/world/entities/{entity_ref:path}/blast-radius")
    async def world_blast_radius(request: Request, entity_ref: str):
        return await tx(request, lambda svc,o,u: __import__("src.world_model", fromlist=["WorldModelService"]).WorldModelService(svc.db).blast_radius(o, entity_ref))
    @router.patch("/runs/{run_id}")
    async def update_run(request: Request, run_id: str, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.set_run_status(o,run_id,str(payload.get("status") or ""),payload))
    @router.post("/runs/{run_id}/actions", status_code=201)
    async def create_action(request: Request, run_id: str, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_action(o,run_id,payload))
    @router.post("/runs/{run_id}/actions/{action_id}/retry")
    async def retry_action(request: Request, run_id: str, action_id: str, payload: dict[str, Any] = Body(default={} )):
        def operation(svc, o, u):
            action = svc.db.query(WorkAction).join(WorkRun).filter(WorkAction.id == action_id, WorkRun.owner == o).one_or_none()
            if action is None: raise WorkError("action not found")
            action = serialize(action)
            if action["run_id"] != run_id: raise WorkError("action not found")
            return svc.retry_action(o, action_id, reason=str((payload or {}).get("reason") or "operator requested retry"))
        return await tx(request, operation)
    @router.post("/actions/{action_id}/complete")
    async def complete_action(request: Request, action_id: str, payload: dict[str, Any] = Body(default={})): return await tx(request, lambda svc,o,u: svc.complete_action(o,action_id,payload))
    @router.post("/actions/{action_id}/approval")
    async def bind_approval(request: Request, action_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.bind_approval(o, action_id, str(payload.get("approval_reference") or payload.get("approval_id") or ""), digest=payload.get("sealed_input_digest")))
    @router.post("/actions/{action_id}/resume")
    async def resume_action(request: Request, action_id: str, payload: dict[str, Any] = Body(...)):
        return await tx(request, lambda svc,o,u: svc.resume_approved_action(o, action_id, str(payload.get("approval_reference") or payload.get("approval_id") or ""), digest=payload.get("sealed_input_digest")))
    @router.post("/runs/{run_id}/results", status_code=201)
    async def result(request: Request, run_id: str, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.add_result(o,run_id,payload))
    @router.get("/commitments")
    async def commitments(request: Request, status: str | None = None): return {"commitments": await tx(request, lambda svc,o,u: svc.list_records(o, WorkCommitment, status=status))}
    @router.post("/commitments", status_code=201)
    async def create_commitment(request: Request, payload: dict[str, Any] = Body(...)): return await tx(request, lambda svc,o,u: svc.create_commitment(o,payload))
    @router.get("/events")
    async def events(request: Request, limit: int = Query(100, ge=1, le=500)):
        return {"events": await tx(request, lambda svc,o,u: [serialize(x) for x in svc.db.query(WorkEvent).filter_by(owner=o).order_by(WorkEvent.created_at.desc()).limit(limit).all()])}

    @router.post("/runs/{run_id}/security-context", status_code=201)
    async def security_context(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        def operation(svc,o,u):
            run = svc._one(WorkRun,o,run_id,"run")
            from src.security_assessment import SecurityAssessmentService
            assessment = SecurityAssessmentService(svc.db); engagement = assessment.get_engagement(o,str(payload.get("engagement_id") or ""))
            target = next((x for x in engagement["targets"] if x["id"] == payload.get("target_id")), None)
            if target is None: raise WorkError("security target not found")
            action = svc.create_action(o,run.id,{"capability_id":"security.target.resolve","action_id":"resolve","tool_binding_name":"manage_security_assessment","effect_class":"read_private","normalized_input":{"target_id":target["id"]}})
            completed = svc.complete_action(o,action["id"],{"result_reference":f"security-target://{target['id']}"})
            return {"action": completed, "target": target, "engagement_id": engagement["id"]}
        return await tx(request, operation)

    @router.post("/runs/{run_id}/inventory-review", status_code=201)
    async def inventory_review(request: Request, run_id: str, payload: dict[str, Any] = Body(...)):
        def operation(svc,o,u):
            run = svc._one(WorkRun,o,run_id,"run"); item_id = str(payload.get("item_id") or "")
            from src.inventory_service import get_inventory_service
            item = get_inventory_service().get_item(o,item_id)
            action = svc.create_action(o,run.id,{"capability_id":"inventory.manage","action_id":"get","tool_binding_name":"manage_assets","effect_class":"read_private","normalized_input":{"item_id":item_id}})
            completed = svc.complete_action(o,action["id"],{"result_reference":f"inventory-item://{item_id}"})
            return {"action": completed, "item": item, "proposal": {"review_required": True, "item_id": item_id}}
        return await tx(request, operation)
    return router
