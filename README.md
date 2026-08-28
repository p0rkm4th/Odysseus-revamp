# Odysseus Revamp

<p align="center"><img src="docs/odysseus-wordmark.png" alt="Odysseus" width="420"></p>

**A local-first AI control plane built to make smaller models behave like capable, persistent agents.**

Odysseus Revamp is an experimental rework of the Odysseus project focused on agent architecture, durable state, local-model reliability, infrastructure awareness, and supervised execution.

![Odysseus browser preview](docs/odysseus-browser.jpg)

The long-term goal is simple to describe and annoyingly difficult to build:

> A model should not need to understand the internals of the application in order to operate the application.

Instead of asking an LLM to memorize dozens of tools, reconstruct workflow state from chat history, guess what it is allowed to do, and hope its tool-call syntax survives parsing, this project is moving those responsibilities into the application itself.

The model reasons.

Odysseus handles the machinery.

Keep `AUTH_ENABLED=true` for any network-accessible deployment. Keep `LOCALHOST_BYPASS=false` outside local development.

---

## What this project is

This repository began as a heavily modified Odysseus installation and has since evolved into an architectural revamp centered around **Hades**, the persistent local-agent control plane.

The project is currently exploring a system where interchangeable language models operate over durable:

* objectives
* Runs
* Actions
* Results
* approvals
* memory
* infrastructure state
* evidence
* world relationships
* verification
* procedures
* execution policy

The selected model is treated as **replaceable cognition**, not as the database, workflow engine, security boundary, or source of truth.

That distinction is the heart of the revamp.

---

## Why this exists

Modern agent frameworks often place an absurd amount of responsibility on the language model.

A typical model may be expected to:

1. understand an ambiguous request,
2. identify the correct domain,
3. remember previous work,
4. search a large tool registry,
5. choose the correct tool,
6. construct valid arguments,
7. respect security policy,
8. recover from failures,
9. determine whether execution succeeded,
10. remember what remains to be done,
11. and explain everything coherently.

Frontier models can brute-force their way through a surprising amount of that.

Small local models usually cannot.

Odysseus Revamp takes the opposite approach:

```text
Human
  ↓
Context + state resolution
  ↓
Intent
  ↓
Canonical domain state
  ↓
Small set of valid operations
  ↓
Language model reasoning
  ↓
Validated Action
  ↓
Policy / approval
  ↓
Execution
  ↓
Verification
  ↓
Result
  ↓
Completion or continuation
```

The framework should make the reasoning problem easy.

The model should not have to reverse-engineer the framework.

---

# Design principles

## Odysseus owns state

Objectives, task progress, pending work, Results, references, and execution history should survive:

* model changes
* provider failures
* page refreshes
* context compaction
* long-running work

Chat history is useful context.

It is not the workflow database.

---

## Odysseus owns authority

A model choosing an Action does not make that Action authorized.

Execution remains subject to:

* owner identity
* capability policy
* execution scope
* exact approvals
* resource constraints
* runtime security boundaries

The model proposes.

The control plane decides whether the proposal may become reality.

A reassuring arrangement, considering language models occasionally hallucinate with the confidence of a middle manager.

---

## Odysseus owns canonical truth

Domain systems remain authoritative for their own data.

Examples include:

* Work
* Memory
* technical assets
* network observations
* security findings
* research evidence
* integrations
* infrastructure state

Model-generated prose is not promoted to truth merely because it sounds convincing.

---

## Odysseus owns verification

A successful command is not necessarily a successful outcome.

Actions can define postconditions so that Odysseus can distinguish:

```text
COMMAND_SUCCEEDED
```

from:

```text
REQUESTED_OUTCOME_VERIFIED
```

This is especially important for:

* service operations
* configuration changes
* infrastructure work
* code edits
* deployment
* network operations

---

## Models reason where reasoning matters

The model should spend its limited intelligence on things like:

* interpreting ambiguous language
* diagnosing from evidence
* comparing alternatives
* choosing useful observations
* synthesizing research
* planning unfamiliar work
* explaining results

It should not waste inference figuring out internal implementation details that deterministic software already knows.

---

# Current architecture

The canonical execution direction is:

```text
Domain
  ↓
Capability
  ↓
ActionSpec
  ↓
ToolBinding / trusted executor
```

The model-facing layer is being redesigned around semantic projections such as:

```text
IntentFrame
Objective
WorkingSet
ActionCard
AgentTaskPacket
Decision
ResultProjection
CompletionContract
```

These projections are not intended to become new truth stores.

They are compact interfaces between a potentially complicated control plane and a comparatively small language model.

---

# Hades

**Hades** is the name used in this repository for the persistent agent/control-plane architecture surrounding Odysseus.

The intended experience is less:

```text
chatbot with a pile of tools
```

and more:

```text
persistent local operator
with replaceable cognition
```

Hades is being designed around several properties.

### Continuity

Work persists independently of a particular model response.

### Attention

The system can represent active work, blockers, approvals, incidents, failed verification, and things requiring attention.

### Working memory

Current objectives and evidence can be projected into compact task-specific state.

### Long-term memory

Durable owner memory remains separate from conversation history and canonical domain truth.

### World awareness

Infrastructure, assets, services, networks, and other entities can be represented as durable objects and relationships.

### Epistemic discipline

The system should distinguish between:

* observed
* retrieved
* user-asserted
* inferred
* historical
* stale
* contradicted

information.

### Competence awareness

Hades should know which capabilities are:

* available
* degraded
* unavailable
* restricted

rather than asking the language model to guess what the application can currently do.

---

# Local-model focus

A major goal of the revamp is making models in roughly the **7B–14B class** genuinely useful as agents.

The current architecture work uses smaller models as a stress test.

A weak model is useful because it exposes poor interface design immediately.

If an 8B model receives:

```text
one objective
current verified state
three applicable operations
clear constraints
explicit completion criteria
```

and still makes the wrong decision, the model may genuinely be the limiting factor.

If it receives:

```text
forty tools
several competing tool descriptions
thousands of tokens of generic instructions
Memory
Skills
documents
conversation history
provider-specific syntax
and ambiguous workflow state
```

the harness has no right to act surprised when things go sideways.

---

# Agent-Computer Interface

The current development phase focuses heavily on the **Agent-Computer Interface**, or ACI.

The intended flow is approximately:

```text
USER
 │
 ▼
Context Resolution
 │
 ▼
IntentFrame
 │
 ▼
Objective
 │
 ▼
Canonical Domain Resolution
 │
 ▼
WorkingSet
 │
 ▼
Is the next operation deterministic?
 ├── yes ──► execute/read directly
 │
 └── no
      │
      ▼
 AgentTaskPacket
      │
      ▼
 Local Model
      │
      ▼
 Structured Decision
      │
      ▼
 Validate
      │
      ▼
 Policy / Approval
      │
      ▼
 Execute
      │
      ▼
 Verify
      │
      ▼
 Canonical Result
      │
      ▼
 Result Projection
      │
      ▼
 Completion Check
      │
      ├── incomplete ──► continue
      │
      └── complete ────► answer
```

The objective is to make the model-visible problem dramatically smaller than the underlying system.

---

# Durable work

The revamp includes a durable Work/Run architecture intended to represent execution independently of transient chat messages.

A Run can contain concepts such as:

* objective
* status
* Actions
* Results
* journal entries
* checkpoints
* blockers
* approvals
* verification
* dependencies
* completion state

This allows another model to continue existing work without reconstructing the entire workflow from a transcript.

---

# Actions and Results

Execution is increasingly represented as explicit Actions rather than arbitrary implied tool activity.

An Action can carry information such as:

* semantic operation
* target
* parameters
* policy classification
* resource requirements
* approval requirements
* expected Result
* verification requirements

Results preserve execution evidence separately from whatever the model later says about that evidence.

The intended invariant is:

> If Hades claims an operation happened, a corresponding Result or canonical observation should exist.

---

# Infrastructure and world state

Infrastructure work is one of the major test environments for the control plane.

The project includes or is developing architecture around:

* technical asset inventory
* CMDB-style entities
* host observations
* network observations
* Homelab operations
* service state
* incidents
* changes
* security findings
* relationships between systems

Network context is deliberately separated into concepts such as:

* physical network
* VPN
* container/runtime networks
* host-local state
* application runtime

A private IP address is **not** treated as automatic authorization to scan a network.

The system is expected to fail closed when ownership or scope is uncertain.

---

# Memory

Memory is treated as a first-class system, but not as a dumping ground for every fact Hades encounters.

The architecture distinguishes between:

### Conversation context

Recent dialogue.

### Working state

The current objective, Run, Results, and unresolved questions.

### Durable Memory

Useful persistent information about the owner and prior interactions.

### Canonical domain state

Things that belong elsewhere, such as:

* assets
* tasks
* projects
* research evidence
* infrastructure observations

Memory may reference canonical systems.

It should not silently replace them.

---

# Procedural knowledge

Another direction of the project is turning reusable skills into supervised procedural knowledge.

Examples include procedures for:

* diagnosing a managed host
* performing bounded network discovery
* recovering services
* conducting technical research
* debugging code
* verifying deployment
* protecting data before repair

The long-term goal is not to inject giant procedure libraries into every model prompt.

Instead:

```text
objective
  ↓
retrieve applicable procedure
  ↓
load only relevant procedure/state
  ↓
execute through canonical Actions
```

Procedures remain constrained by the same policy and approval system as every other Action.

---

# Developer mode

A future major milestone is making Hades capable of developing Odysseus from inside Odysseus.

Rather than expecting a smaller coding model to navigate an entire repository through unrestricted shell access, the intended developer ACI emphasizes operations such as:

```text
SEARCH_CODE
VIEW_FILE_REGION
VIEW_SYMBOL
VIEW_REFERENCES
SHOW_REPO_MAP
APPLY_PATCH
SHOW_DIFF
RUN_TARGETED_TEST
RUN_LINT
SHOW_DIAGNOSTICS
```

The framework can then automate mechanical responsibilities such as:

```text
edit
→ syntax validation
→ targeted test
→ verification
```

while the model focuses on understanding and solving the engineering problem.

---

# Current development status

This repository is an **active architectural revamp**, not a polished downstream release of upstream Odysseus.

The current work has focused heavily on foundations including:

* durable Runs
* Action lifecycle
* canonical Results
* approval semantics
* execution policy
* resource locking
* verification
* state invalidation
* provider-failure continuation
* canonical Memory reads
* Work reads
* technical asset reads
* network-context correctness
* infrastructure observations
* execution provenance
* model-independent workflow state

The next major phase is improving the model-facing ACI:

* compact WorkingSets
* deterministic read fast paths
* semantic ActionCards
* small Action candidate sets
* structured model Decisions
* objective-aware Result projection
* explicit completion contracts
* automatic safe continuation
* provider-native local-model optimization
* weak-model evaluation

Expect substantial architectural change.

---

# Weak-model evaluation

Local-model performance is being treated as an engineering problem rather than a collection of anecdotes.

The planned evaluation model compares things like:

* intent resolution
* reference resolution
* correct Action exposure
* Action shortlist recall
* correct Action selection
* structured-output validity
* approval correctness
* Result grounding
* continuation
* full task completion
* context size
* model calls
* latency

The primary question is not:

> Did the model produce pretty prose?

It is:

> Did Odysseus give the model a sufficiently good decision problem that the requested outcome could be completed correctly?

---

# Repository history

Several milestone tags are preserved to make architectural changes measurable.

Notable checkpoints include:

```text
hades-baseline-20260823
hades-security-assessment-v1.1-20260823
hades-work-engine-v1-20260823
hades-local-intelligence-v1-20260824
hades-pre-aci-v1
```

`hades-pre-aci-v1` marks the control-plane baseline immediately before the major weak-model/ACI revamp.

This makes it possible to compare the pre-ACI architecture against later iterations without relying on heroic recollection of what happened several million tokens ago.

---

# Quick start

> **Important:** this repository is currently a development project. It may contain incomplete migrations, experimental architecture, or behavior that changes rapidly.

Docker is the primary development path.

```bash
git clone https://github.com/p0rkm4th/Odysseus-revamp.git
cd Odysseus-revamp

cp .env.example .env

docker compose up -d --build
```

Then inspect container health:

```bash
docker compose ps
docker compose logs --tail=150 odysseus
```

The application normally listens on:

```text
http://localhost:7000
```

Exact configuration and deployment behavior may change as the revamp progresses.

Do not assume the current development branch has the same setup expectations as upstream Odysseus.

---

# Local models

The project is intended to work with local and remote model providers.

Current development is especially interested in:

* Ollama
* llama.cpp-style servers
* OpenAI-compatible endpoints
* provider-native structured output
* constrained tool/Action decisions

One of the core experiments is determining how much model capability can be replaced by better orchestration.

The desired outcome is not merely to support smaller models.

It is to make the framework **measurably easier for a smaller model to operate than a generic tool-calling harness**.

---

# Security

Hades is being designed around the assumption that local-agent software can become extremely dangerous if model output is confused with authority.

Important architectural principles include:

* authenticated owner boundaries
* explicit capability policy
* exact approvals for consequential Actions
* replay protection
* resource scoping
* fail-closed network authorization
* untrusted external-content tracking
* constrained privileged brokers
* no general model-controlled host root shell
* no automatic privilege escalation
* no model-controlled policy changes

Running a model locally does not magically make arbitrary execution safe.

Keep externally reachable installations authenticated and isolated appropriately.

---

# Project direction

The broad direction is:

```text
Reliable control plane
        ↓
Weak-model ACI
        ↓
Developer ACI
        ↓
Research + broader domain convergence
        ↓
Self-hosted Odysseus development
        ↓
Optional multi-model cognition
```

A dedicated router or micro-model may eventually be useful, but it is intentionally deferred until measurement shows that semantic routing remains a meaningful bottleneck.

Complexity must earn its existence.

A revolutionary policy for software development, apparently.

---

# Philosophy

A few rules guide the revamp:

> **ODYSSEUS OWNS STATE.**

> **ODYSSEUS OWNS AUTHORITY.**

> **ODYSSEUS OWNS EXECUTION.**

> **ODYSSEUS OWNS VERIFICATION.**

> **ODYSSEUS OWNS CONTINUITY.**

> **ODYSSEUS OWNS CANONICAL TRUTH.**

> **THE MODEL INTERPRETS, REASONS, PRIORITIZES, AND EXPLAINS.**

> **THE MODEL SHOULD NEVER NEED TO REVERSE-ENGINEER ODYSSEUS IN ORDER TO OPERATE ODYSSEUS.**

---

# Upstream and attribution

Odysseus Revamp is derived from **Odysseus**, originally developed by the Odysseus project and its contributors.

Upstream project:

https://github.com/odysseus-dev/odysseus

This repository is an independent experimental revamp and should not be interpreted as an official upstream release or upstream development branch.

The purpose of this repository is to explore substantial changes to:

* agent orchestration
* durable execution
* model interfaces
* local-model performance
* infrastructure control
* memory
* verification
* supervised autonomy

Credit for the original Odysseus project and its existing components remains with the upstream project and contributors.

---

# License

This project retains the upstream **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)** licensing requirements.

See:

* `LICENSE`
* `ACKNOWLEDGMENTS.md`
* upstream project history

Any redistribution or hosted modification should comply with the applicable AGPL requirements.

---

# Current warning label

This is currently a personal research/development branch.

It contains powerful agent capabilities and is undergoing aggressive architectural change.

Do not deploy it somewhere important simply because the test suite is green.

We have already conducted that experiment.
