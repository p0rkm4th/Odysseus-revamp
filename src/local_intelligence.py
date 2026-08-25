"""Opt-in local inference and deterministic, inspectable routing."""
from __future__ import annotations
import json, os, time, urllib.request
from dataclasses import asdict, dataclass
@dataclass(frozen=True)
class LocalModelProfile:
    name: str; provider: str; endpoint: str; model: str; context: int
    tool_calling: bool; capabilities: tuple[str, ...]; weaknesses: tuple[str, ...]
PROFILES = {"hades-local-test": LocalModelProfile("hades-local-test", "ollama", os.getenv("HADES_OLLAMA_ENDPOINT", "http://host.docker.internal:11434"), "qwen3:8b", 8192, False, ("chat", "structured", "read_only"), ("cpu_only", "no_consequential_tools", "latency"))}
def profiles(): return [asdict(x) for x in PROFILES.values()]
def route_request(text: str, *, requested_profile: str | None = None, execution_profile: str = "host"):
    value = str(text or "").casefold()
    network_request = any(x in value for x in ("network", "device", "nmap", "homelab", "service", "lan", "subnet"))
    network_action = network_request and any(x in value for x in (
        "scan", "discover", "discovery", "execute", "begin", "start", "restart", "install",
    ))
    if network_action:
        domain, reason, local_ok = "network", "bounded_network_action_requires_canonical_homelab_route", False
    elif any(x in value for x in ("exploit", "credential attack", "scan public", "delete", "send", "execute")):
        domain, reason, local_ok = "security", "consequential_or_security_action_requires_strong_route", False
    elif network_request:
        domain, reason, local_ok = "network", "bounded_network_tools_remain_authority_gated", True
    elif any(x in value for x in ("rice", "food", "pantry", "recipe", "cook", "household")):
        domain, reason, local_ok = "household_inventory", "simple_household_read", True
    elif any(x in value for x in ("gpu", "computer", "it asset", "hardware", "serial")):
        domain, reason, local_ok = "it_assets", "simple_technical_read", True
    elif any(x in value for x in ("work", "goal", "project", "task", "where did we leave")):
        domain, reason, local_ok = "work", "durable_work_status_read", True
    else: domain, reason, local_ok = "general", "default_strong_route", False
    profile = requested_profile if requested_profile in PROFILES and local_ok else "strong-default"
    task_class = {"network": "network_action" if network_action else "network_read", "household_inventory": "household_read", "it_assets": "canonical_it_read", "work": "work_read", "general": "general_chat", "security": "security_action"}[domain]
    return {"domains":[domain], "task_class":task_class, "model_profile":profile, "capabilities":["read_only"] if local_ok else [], "context_projection":"work_compact" if domain == "work" else domain, "execution_profile":execution_profile, "confidence":0.86 if local_ok else 0.94, "reason_codes":[reason], "fallbacks":["strong-default"], "local_recommended":local_ok, "consequential_execution":not local_ok}
def infer(profile_name: str, messages: list[dict], *, timeout: int = 90):
    profile = PROFILES.get(profile_name)
    if not profile: raise ValueError("unknown local model profile")
    if not (profile.endpoint.startswith("http://127.0.0.1:") or profile.endpoint.startswith("http://host.docker.internal:")):
        raise ValueError("local endpoint must be loopback or the container's host-only bridge")
    body = json.dumps({"model": profile.model, "messages": messages, "stream": False, "think": False, "format": "json", "options": {"num_ctx": profile.context, "temperature": 0}}).encode()
    started = time.monotonic(); req = urllib.request.Request(profile.endpoint + "/api/chat", data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response: result = json.loads(response.read())
    result["_hades"] = {"profile": profile_name, "elapsed_ms": round((time.monotonic()-started)*1000), "local_only": True}
    return result
