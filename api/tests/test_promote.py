"""The only route to an admin account — without it the /admin endpoints are unreachable."""

from app.promote import main


def test_promoting_grants_access_to_the_admin_endpoints(client, user_token, capsys):
    email = client.get("/auth/me", headers=user_token).json()["email"]
    assert client.get("/admin/jobs", headers=user_token).status_code == 403

    assert main([email, "admin"]) == 0
    assert f"user -> admin" in capsys.readouterr().out

    # The role rides in the JWT claims but is read from the row, so the existing
    # token starts working immediately.
    assert client.get("/admin/jobs", headers=user_token).status_code == 200


def test_demoting_takes_it_away(client, user_token):
    email = client.get("/auth/me", headers=user_token).json()["email"]
    main([email, "admin"])
    assert main([email, "user"]) == 0
    assert client.get("/admin/jobs", headers=user_token).status_code == 403


def test_repeating_it_is_a_no_op(client, user_token, capsys):
    email = client.get("/auth/me", headers=user_token).json()["email"]
    main([email, "admin"])
    capsys.readouterr()

    assert main([email, "admin"]) == 0
    assert "already admin" in capsys.readouterr().out


def test_bad_input_fails_loudly(client, user_token, capsys):
    assert main(["nobody@example.com", "admin"]) == 1
    assert "No user" in capsys.readouterr().err

    email = client.get("/auth/me", headers=user_token).json()["email"]
    assert main([email, "superuser"]) == 2
    assert "Unknown role" in capsys.readouterr().err


def test_list_shows_every_account_and_role(client, user_token, capsys):
    email = client.get("/auth/me", headers=user_token).json()["email"]
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    assert email in out and "user" in out


def test_help_is_the_default_for_no_arguments(capsys):
    assert main([]) == 0
    assert "python -m app.promote" in capsys.readouterr().out
