"""Regression coverage for caller-controlled MLX image model selection."""

import argparse
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mlx_image_server.py"


def _load():
    spec = importlib.util.spec_from_file_location("mlx_image_server_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def server():
    module = _load()
    module._args = argparse.Namespace(
        model="mlx-community/pinned-model", host="127.0.0.1", port=8100,
        steps=0, width=512, height=512, base_model="", lora_style="",
        lora_paths=[], lora_scales=[], vlm_model="",
    )
    return module


def test_generation_ignores_caller_model_path(server, tmp_path, monkeypatch):
    planted = tmp_path / "hidream-planted"
    script = planted / "scripts" / "hidream_o1" / "generate_hidream_o1_mlx.py"
    script.parent.mkdir(parents=True)
    marker = planted / "executed"
    script.write_text(f"open({str(marker)!r}, 'w').write('ran')\n", encoding="utf-8")
    monkeypatch.setattr(server, "_generate_hidream", lambda *args: None)
    monkeypatch.setattr(server, "_resolve_cli", lambda name: "/bin/false")
    from fastapi.testclient import TestClient

    TestClient(server.app).post(
        "/v1/images/generations",
        json={"model": str(planted), "prompt": "x"},
    )
    assert not marker.exists()


@pytest.mark.asyncio
async def test_edits_ignore_caller_model_path(server, monkeypatch):
    called = []
    monkeypatch.setattr(server, "_run_inpaint_bridge", lambda *args: called.append(args))
    from fastapi import UploadFile
    from fastapi import HTTPException
    from io import BytesIO

    with pytest.raises(HTTPException) as raised:
        await server.edit_image(
            image=UploadFile(filename="i.png", file=BytesIO(b"not-an-image")),
            prompt="x", model="attacker/lama-model",
        )
    assert raised.value.status_code == 422
    assert not called


def test_pinned_model_still_drives_generation(server, monkeypatch, tmp_path):
    marker = tmp_path / "ran"
    monkeypatch.setattr(server, "_is_hidream", lambda model: True)
    monkeypatch.setattr(server, "_generate_hidream", lambda model, prompt, out, *args: (out.write_bytes(b"x"), marker.write_text(model)))
    from fastapi.testclient import TestClient

    response = TestClient(server.app).post(
        "/v1/images/generations", json={"model": "attacker/model", "prompt": "x"}
    )
    assert response.status_code == 200
    assert marker.read_text() == server._args.model
