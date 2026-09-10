from src.execution_profiles import bubblewrap_argv, resolve_execution_profile, use_execution_profile


def test_hardcore_yolo_is_networked_but_host_workspace_is_read_only(tmp_path):
    profile = resolve_execution_profile("hardcore_yolo")
    assert profile.subprocess_backend == "bubblewrap_network"
    assert profile.requires_workspace
    with use_execution_profile(profile):
        argv = bubblewrap_argv(str(tmp_path), ["/bin/bash", "-lc", "id"])
    assert "--share-net" in argv
    assert "--ro-bind" in argv
    assert str(tmp_path) in argv
    assert "/source" in argv
    assert "--bind" not in argv
    assert "/work" in argv
    assert "65534" in argv


def test_hardcore_yolo_allows_only_bounded_shell_tools():
    profile = resolve_execution_profile("hardcore_yolo")
    assert profile.allowed_tools == frozenset({
        "bash", "python", "get_workspace", "glob", "grep", "ls", "read_file",
    })
