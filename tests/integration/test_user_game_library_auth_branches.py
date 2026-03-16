from uuid import uuid4

import pytest
from sqlalchemy import select

from api.models.user import User


async def _register(client, username: str, email: str, password: str = "12345678") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


async def _auth_headers(client, identifier: str, password: str = "12345678") -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_auth_and_user_endpoints_branches(client, db_session):
    user_a = await _register(client, "ugl_user_a", "ugl_user_a@example.com")
    await _register(client, "ugl_user_b", "ugl_user_b@example.com")

    duplicate_email = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "ugl_user_c",
            "email": "ugl_user_a@example.com",
            "password": "12345678",
        },
    )
    assert duplicate_email.status_code == 400

    duplicate_username = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "ugl_user_a",
            "email": "ugl_user_c@example.com",
            "password": "12345678",
        },
    )
    assert duplicate_username.status_code == 400

    invalid_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "ugl_user_a", "password": "wrong-password"},
    )
    assert invalid_login.status_code == 401

    to_deactivate = (
        await db_session.execute(select(User).where(User.email == "ugl_user_b@example.com"))
    ).scalar_one()
    to_deactivate.is_active = False
    db_session.add(to_deactivate)
    await db_session.commit()

    inactive_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "ugl_user_b@example.com", "password": "12345678"},
    )
    assert inactive_login.status_code == 403

    unauthorized_me = await client.get("/api/v1/users/me")
    assert unauthorized_me.status_code == 401

    headers = await _auth_headers(client, "ugl_user_a@example.com")

    me_response = await client.get("/api/v1/users/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["id"] == user_a["id"]

    search_response = await client.get(
        "/api/v1/users/search/",
        headers=headers,
        params={"q": "ugl_user_", "limit": 10},
    )
    assert search_response.status_code == 200
    assert len(search_response.json()) >= 2

    list_response = await client.get(
        "/api/v1/users/",
        headers=headers,
        params={"skip": 0, "limit": 1},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_user = await client.get(f"/api/v1/users/{user_a['id']}", headers=headers)
    assert get_user.status_code == 200

    missing_user = await client.get(f"/api/v1/users/{uuid4()}", headers=headers)
    assert missing_user.status_code == 404


@pytest.mark.asyncio
async def test_game_and_library_endpoints_branches(client):
    await _register(client, "ugl_game_user", "ugl_game_user@example.com")
    headers = await _auth_headers(client, "ugl_game_user")

    invalid_create_game = await client.post(
        "/api/v1/games/",
        headers=headers,
        json={"name": "UGL Invalid", "min_players": 5, "max_players": 2},
    )
    assert invalid_create_game.status_code == 400

    create_game = await client.post(
        "/api/v1/games/",
        headers=headers,
        json={"name": "UGL Game", "min_players": 1, "max_players": 6},
    )
    assert create_game.status_code == 201
    game_id = create_game.json()["id"]

    duplicate_game = await client.post(
        "/api/v1/games/",
        headers=headers,
        json={"name": "UGL Game", "min_players": 1, "max_players": 6},
    )
    assert duplicate_game.status_code == 400

    list_games = await client.get("/api/v1/games/", headers=headers)
    assert list_games.status_code == 200
    assert any(g["name"] == "UGL Game" for g in list_games.json())

    search_empty_query = await client.get(
        "/api/v1/games/search/",
        headers=headers,
        params={"q": "   "},
    )
    assert search_empty_query.status_code == 200
    assert search_empty_query.json() == []

    get_missing_game = await client.get(f"/api/v1/games/{uuid4()}", headers=headers)
    assert get_missing_game.status_code == 404

    get_game = await client.get(f"/api/v1/games/{game_id}", headers=headers)
    assert get_game.status_code == 200
    assert get_game.json()["name"] == "UGL Game"

    update_missing_game = await client.patch(
        f"/api/v1/games/{uuid4()}",
        headers=headers,
        json={"name": "Does Not Exist"},
    )
    assert update_missing_game.status_code == 404

    update_invalid_players = await client.patch(
        f"/api/v1/games/{game_id}",
        headers=headers,
        json={"min_players": 10, "max_players": 2},
    )
    assert update_invalid_players.status_code == 400

    update_game = await client.patch(
        f"/api/v1/games/{game_id}",
        headers=headers,
        json={"name": "UGL Game Updated", "max_players": 7},
    )
    assert update_game.status_code == 200
    assert update_game.json()["name"] == "UGL Game Updated"

    add_unknown_library_game = await client.post(
        "/api/v1/library/",
        headers=headers,
        json={"game_id": str(uuid4())},
    )
    assert add_unknown_library_game.status_code == 404

    add_library = await client.post(
        "/api/v1/library/",
        headers=headers,
        json={"game_id": game_id},
    )
    assert add_library.status_code == 201

    add_library_duplicate = await client.post(
        "/api/v1/library/",
        headers=headers,
        json={"game_id": game_id},
    )
    assert add_library_duplicate.status_code == 400

    my_library = await client.get("/api/v1/library/", headers=headers)
    assert my_library.status_code == 200
    assert len(my_library.json()) == 1

    user_id = (await client.get("/api/v1/users/me", headers=headers)).json()["id"]
    user_library = await client.get(f"/api/v1/library/{user_id}", headers=headers)
    assert user_library.status_code == 200
    assert len(user_library.json()) == 1

    remove_missing_library_game = await client.delete(
        f"/api/v1/library/{uuid4()}",
        headers=headers,
    )
    assert remove_missing_library_game.status_code == 404

    remove_library_game = await client.delete(
        f"/api/v1/library/{game_id}",
        headers=headers,
    )
    assert remove_library_game.status_code == 204
