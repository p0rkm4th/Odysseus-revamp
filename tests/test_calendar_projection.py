import json

from src.aci import communications_calendar_summary_from_tool_output, project_final_answer


def test_communications_degraded_status_does_not_hide_calendar_empty_state():
    output = json.dumps({
        "calendar": {"calendars": 1, "events": [], "upcoming_14_days": 0},
        "email": {"accounts": [], "configured": 0},
        "status": "DEGRADED",
        "degraded_reason": "NOT_PROJECTED",
    })
    summary = communications_calendar_summary_from_tool_output(output)
    assert summary == "You have no calendar events scheduled in the next 14 days."
    assert "blocked" not in summary.lower()


def test_communications_calendar_summary_explains_missing_connection():
    output = json.dumps({"calendar": {"calendars": 0, "events": []}, "status": "SUCCESS_EMPTY"})
    assert "not connected" in communications_calendar_summary_from_tool_output(output).lower()


def test_calendar_projection_is_authoritative_final_answer():
    answer, provenance = project_final_answer(
        "The current objective is blocked or needs clarification.",
        [{"tool": "read_communications", "command": '{"action":"overview"}',
          "output": "The current objective is blocked or needs clarification.",
          "result_projection": {"calendar": {"calendars": 1, "events": []}},
          "exit_code": 0, "success": True}],
    )
    assert answer == "You have no calendar events scheduled in the next 14 days."
    assert provenance is not None
    assert provenance.source.value == "DETERMINISTIC_RESULT"
