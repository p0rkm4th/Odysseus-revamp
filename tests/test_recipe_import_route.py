import asyncio

from routes import inventory_routes


class _Uploads:
    def resolve_upload(self, *args, **kwargs):
        raise AssertionError("pasted import must not resolve an upload")


class _PdfUploads:
    def resolve_upload(self, _upload_id, *, owner, auth_manager, allow_admin):
        assert owner == "alice"
        return {"id": _upload_id, "mime": "application/pdf", "path": "/managed/recipe.pdf"}


class _Service:
    def create_recipe(self, owner, **kwargs):
        assert owner == "alice"
        assert kwargs["ingredients"][0]["name"] in {"spaghetti", "pasta"}
        return {"id": "recipe-1", **kwargs}

    def missing_ingredients(self, owner, recipe_id):
        assert owner == "alice"
        return {"recipe_id": recipe_id, "can_make": False, "shortages": [
            {"name": "tomato sauce", "missing": "1.000000", "unit": "each", "optional": False},
        ]}


def test_recipe_import_route_returns_saved_recipe_and_deterministic_shortages(monkeypatch):
    router = inventory_routes.setup_inventory_routes(_Uploads(), service=_Service())
    endpoint = next(route.endpoint for route in router.routes if route.path == "/api/recipes/import")
    monkeypatch.setattr(inventory_routes, "_owner", lambda _request: "alice")

    result = asyncio.run(endpoint(object(), {
        "source_text": "Spaghetti\n\nIngredients:\n400 g spaghetti\n1 can tomato sauce\n\nDirections:\nBoil.",
    }))

    assert result["recipe"]["id"] == "recipe-1"
    assert result["missing"]["shortages"][0]["name"] == "tomato sauce"
    assert result["source"]["kind"] == "text"


def test_recipe_import_route_uses_existing_web_fetch_boundary(monkeypatch):
    class FakeWebFetch:
        async def execute(self, content, _ctx):
            assert "recipe.example" in content
            return {"output": "Pasta\n\nIngredients:\n400 g pasta", "exit_code": 0}

    monkeypatch.setattr("src.agent_tools.web_tools.WebFetchTool", FakeWebFetch)
    router = inventory_routes.setup_inventory_routes(_Uploads(), service=_Service())
    endpoint = next(route.endpoint for route in router.routes if route.path == "/api/recipes/import")
    monkeypatch.setattr(inventory_routes, "_owner", lambda _request: "alice")

    result = asyncio.run(endpoint(object(), {"url": "https://recipe.example/pasta"}))

    assert result["source"] == {"kind": "url", "url": "https://recipe.example/pasta"}


def test_recipe_import_route_extracts_owner_checked_pdf(monkeypatch):
    monkeypatch.setattr(inventory_routes, "extract_pdf_text", lambda path: "Pasta\n\nIngredients:\n400 g pasta")
    router = inventory_routes.setup_inventory_routes(_PdfUploads(), service=_Service())
    endpoint = next(route.endpoint for route in router.routes if route.path == "/api/recipes/import")
    monkeypatch.setattr(inventory_routes, "_owner", lambda _request: "alice")

    result = asyncio.run(endpoint(object(), {"attachment_ids": ["a" * 32]}))

    assert result["source"] == {"kind": "pdf", "url": None}
