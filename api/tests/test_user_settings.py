from sqlalchemy import select

from app import user_settings
from app.config import settings
from app.crypto import decrypt
from app.db import SessionLocal
from app.models import UserSetting

KEY = "sk-or-v1-supersecretkey1234"


def names(rows):
    return {r["name"]: r for r in rows}


def test_secret_is_encrypted_at_rest_and_never_returned(client, user_token):
    assert client.put("/settings/openrouter_api_key", json={"value": KEY}, headers=user_token).status_code == 200

    with SessionLocal() as db:
        row = db.scalars(select(UserSetting).where(UserSetting.name == "openrouter_api_key")).all()[-1]
    assert KEY not in row.value  # ciphertext, not the key
    assert decrypt(row.value) == KEY

    listed = names(client.get("/settings", headers=user_token).json())["openrouter_api_key"]
    assert listed["configured"] is True
    assert listed["source"] == "user"
    assert listed["value"] == "…1234"  # a hint, not the key
    assert KEY not in client.get("/settings", headers=user_token).text


def test_non_secret_values_are_shown_in_full(client, user_token):
    client.put("/settings/openrouter_model", json={"value": "anthropic/claude-sonnet-5"}, headers=user_token)
    row = names(client.get("/settings", headers=user_token).json())["openrouter_model"]
    assert row["value"] == "anthropic/claude-sonnet-5"
    assert row["secret"] is False


def test_falls_back_to_the_server_value_then_reports_unset(client, user_token):
    settings.openrouter_model = "anthropic/claude-opus-5"
    settings.openrouter_api_key = ""

    rows = names(client.get("/settings", headers=user_token).json())
    assert rows["openrouter_model"] == {**rows["openrouter_model"], "source": "server", "configured": True}
    assert rows["openrouter_api_key"]["source"] == "unset"
    assert rows["openrouter_api_key"]["configured"] is False


def test_user_setting_overrides_the_server_value(client, user_token):
    settings.openrouter_model = "anthropic/claude-opus-5"
    client.put("/settings/openrouter_model", json={"value": "mine/model"}, headers=user_token)

    with SessionLocal() as db:
        me = int(client.get("/auth/me", headers=user_token).json()["id"])
        assert user_settings.get(db, me, "openrouter_model") == "mine/model"


def test_clearing_falls_back_to_the_server_value(client, user_token):
    settings.openrouter_model = "anthropic/claude-opus-5"
    client.put("/settings/openrouter_model", json={"value": "mine/model"}, headers=user_token)
    assert client.delete("/settings/openrouter_model", headers=user_token).status_code == 204

    row = names(client.get("/settings", headers=user_token).json())["openrouter_model"]
    assert row["value"] == "anthropic/claude-opus-5" and row["source"] == "server"


def test_settings_are_per_user(client, user_token):
    client.put("/settings/openrouter_api_key", json={"value": KEY}, headers=user_token)

    client.post("/auth/register", json={"email": "settings-peer@example.com", "password": "long-enough-pw"})
    r = client.post("/auth/login", data={"username": "settings-peer@example.com", "password": "long-enough-pw"})
    peer = {"Authorization": f"Bearer {r.json()['access_token']}"}

    settings.openrouter_api_key = ""
    assert names(client.get("/settings", headers=peer).json())["openrouter_api_key"]["configured"] is False
    assert KEY not in client.get("/settings", headers=peer).text


def test_unknown_names_empty_values_and_auth(client, user_token):
    assert client.put("/settings/aws_secret", json={"value": "x"}, headers=user_token).status_code == 404
    assert client.delete("/settings/aws_secret", headers=user_token).status_code == 404
    assert client.put("/settings/openrouter_model", json={"value": "  "}, headers=user_token).status_code == 422
    assert client.get("/settings").status_code == 401
    assert client.put("/settings/openrouter_api_key", json={"value": KEY}).status_code == 401
