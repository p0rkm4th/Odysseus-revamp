"""
agent_tools.py — Facade module.

Re-exports tool parsing, schemas, execution, and implementations
for backward compatibility. All importers continue to work unchanged.

Sub-modules:
  - tool_parsing.py: regex patterns, parse/strip functions
  - tool_schemas.py: FUNCTION_TOOL_SCHEMAS, function_call_to_tool_block
  - tool_execution.py: execute_tool_block, format_tool_result, MCP helpers
  - tool_implementations.py: all do_* tool functions
"""

import logging
from src.tool_security import BUILTIN_EMAIL_TOOLS
from src.tool_utils import _truncate, get_mcp_manager, set_mcp_manager
from src.tool_contracts import TOOL_TAGS, ToolBlock

logger = logging.getLogger(__name__)

from .subprocess_tools import BashTool, PythonTool
from .web_tools import WebSearchTool, WebFetchTool
from .filesystem_tools import ReadFileTool, WriteFileTool, EditFileTool, ApplyPatchTool, LsTool, GlobTool, GrepTool, GetWorkspaceTool
from .coding_tools import TodoWriteTool
from .document_tools import CreateDocumentTool, UpdateDocumentTool, EditDocumentTool, SuggestDocumentTool, ManageDocumentTool
from .interaction_tools import AskUserTool, UpdatePlanTool
from .model_interaction_tools import ChatWithModelTool, AskTeacherTool, ListModelsTool
from .bg_job_tools import ManageBgJobsTool
from .session_tools import CreateSessionTool, ListSessionsTool, SendToSessionTool, ManageSessionTool
from .admin_tools import (
    ADMIN_TOOL_HANDLERS,
    do_manage_endpoints, do_manage_mcp, do_manage_webhooks,
    do_manage_tokens, do_manage_settings,
)

TOOL_HANDLERS = {
    "bash": BashTool().execute,
    "python": PythonTool().execute,
    "web_search": WebSearchTool().execute,
    "web_fetch": WebFetchTool().execute,
    "read_file": ReadFileTool().execute,
    "write_file": WriteFileTool().execute,
    "edit_file": EditFileTool().execute,
    "apply_patch": ApplyPatchTool().execute,
    "todowrite": TodoWriteTool().execute,
    "ls": LsTool().execute,
    "glob": GlobTool().execute,
    "grep": GrepTool().execute,
    "create_document": CreateDocumentTool().execute,
    "update_document": UpdateDocumentTool().execute,
    "edit_document": EditDocumentTool().execute,
    "suggest_document": SuggestDocumentTool().execute,
    "manage_documents": ManageDocumentTool().execute,
    "get_workspace": GetWorkspaceTool().execute,
    "ask_user": AskUserTool().execute,
    "update_plan": UpdatePlanTool().execute,
    "chat_with_model": ChatWithModelTool().execute,
    "ask_teacher": AskTeacherTool().execute,
    "list_models": ListModelsTool().execute,
    "manage_bg_jobs": ManageBgJobsTool().execute,
    "create_session": CreateSessionTool().execute,
    "list_sessions": ListSessionsTool().execute,
    "send_to_session": SendToSessionTool().execute,
    "manage_session": ManageSessionTool().execute,
}
# Config/integration admin tools (manage_endpoints/mcp/webhooks/tokens/settings).
TOOL_HANDLERS.update(ADMIN_TOOL_HANDLERS)

# ---------------------------------------------------------------------------
# Constants (re-exported for backward compatibility — single source of truth
# is src.constants; always prefer importing from there for new code)
# ---------------------------------------------------------------------------
MAX_AGENT_ROUNDS = 50
SHELL_TIMEOUT = 60
PYTHON_TIMEOUT = 30

# Tool types that trigger execution
# ---------------------------------------------------------------------------
# Re-exports from sub-modules
# ---------------------------------------------------------------------------

# Parsing
from src.tool_parsing import (  # noqa: E402, F401
    parse_tool_blocks,
    strip_tool_blocks,
    _TOOL_NAME_MAP,
    _TOOL_BLOCK_RE,
    _TOOL_CALL_RE,
    _XML_TOOL_CALL_RE,
    _XML_INVOKE_RE,
    _XML_PARAM_RE,
)

# Schemas
from src.tool_schemas import (  # noqa: E402, F401
    FUNCTION_TOOL_SCHEMAS,
    function_call_to_tool_block,
)

# Execution
from src.tool_execution import (  # noqa: E402, F401
    execute_tool_block,
    stream_tool_execution,
    format_tool_result,
)

# Document functions
from .document_tools import (
    set_active_document, 
    set_active_model
)

# Implementations
from src.tool_implementations import (  # noqa: E402, F401
    do_search_chats,
    do_manage_skills,
    do_manage_tasks,
    do_api_call,
)

# Capability V1 transport projection.  This runs after the facade's schema and
# parser imports have completed, preserving the existing import boundary.
import src.tool_schemas as _ody_v34_tool_schemas
import src.tool_parsing as _ody_v34_tool_parsing
from src.tool_bindings import TOOL_BINDINGS as _capability_v1_bindings


def _ody_v34_add_tool_name(name):
    global TOOL_TAGS
    tags = TOOL_TAGS

    if isinstance(tags, dict):
        if name not in tags:
            sample_key = (
                "manage_memory"
                if "manage_memory" in tags
                else (next(iter(tags)) if tags else None)
            )
            sample = tags.get(sample_key) if sample_key is not None else name
            if isinstance(sample, str):
                value = (
                    sample.replace(str(sample_key), name)
                    if sample_key and str(sample_key) in sample
                    else name
                )
            elif isinstance(sample, tuple):
                value = tuple(
                    x.replace(str(sample_key), name)
                    if isinstance(x, str)
                    and sample_key
                    and str(sample_key) in x
                    else x
                    for x in sample
                )
            elif isinstance(sample, list):
                value = [
                    x.replace(str(sample_key), name)
                    if isinstance(x, str)
                    and sample_key
                    and str(sample_key) in x
                    else x
                    for x in sample
                ]
            else:
                value = sample
            tags[name] = value

    elif isinstance(tags, set):
        tags.add(name)

    elif isinstance(tags, frozenset):
        TOOL_TAGS = tags | frozenset({name})

    elif isinstance(tags, list):
        if name not in tags:
            tags.append(name)

    elif isinstance(tags, tuple):
        if name not in tags:
            TOOL_TAGS = tags + (name,)

    else:
        raise TypeError(
            "Unsupported TOOL_TAGS type: " + type(tags).__name__
        )

    # tool_schemas imported the original object/name during package init.
    _ody_v34_tool_schemas.TOOL_TAGS = TOOL_TAGS

    name_map = getattr(_ody_v34_tool_parsing, "_TOOL_NAME_MAP", None)
    if isinstance(name_map, dict):
        name_map.setdefault(name, name)


for _capability_v1_name in _capability_v1_bindings:
    _ody_v34_add_tool_name(_capability_v1_name)
