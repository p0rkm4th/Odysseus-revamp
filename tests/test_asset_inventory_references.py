import src.asset_inventory as assets


def test_resolve_supports_owner_scoped_ordinal_asset_references(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "DB_PATH", tmp_path / "assets.db")
    connection = assets.db()
    columns = (
        "id, name, type, status, manufacturer, model, hostname, location, notes, "
        "source, confidence, attributes_json, created_at, updated_at, retired_at, owner"
    )
    rows = [
        ("atlas", "Atlas", "computer", "deployed", "Acceptance", "Fixture", None, None, None, "fixture", 1.0, "{}", "2026-01-01", "2026-01-02", None, "alice"),
        ("erebus", "Erebus", "computer", "deployed", "Acceptance", "Fixture", None, None, None, "fixture", 1.0, "{}", "2026-01-01", "2026-01-03", None, "alice"),
        ("other", "Other", "computer", "deployed", "Acceptance", "Fixture", None, None, None, "fixture", 1.0, "{}", "2026-01-01", "2026-01-04", None, "bob"),
    ]
    connection.executemany(f"INSERT INTO assets ({columns}) VALUES ({','.join('?' for _ in rows[0])})", rows)
    connection.commit()

    assert assets.resolve(connection, "first", "alice")["name"] == "Atlas"
    assert assets.resolve(connection, "second", "alice")["name"] == "Erebus"
    assert assets.resolve(connection, "third", "alice") is None
    assert assets.resolve(connection, "first", "bob")["name"] == "Other"
