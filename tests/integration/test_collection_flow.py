import pytest


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


async def _create_game(client, headers: dict, name: str) -> dict:
    response = await client.post(
        "/api/v1/games/",
        headers=headers,
        json={"name": name, "min_players": 1, "max_players": 6},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_collection_full_flow_with_members_and_games(client):
    owner = await _register(client, "col_owner", "col_owner@example.com")
    member = await _register(client, "col_member", "col_member@example.com")
    outsider = await _register(client, "col_out", "col_out@example.com")

    owner_headers = await _auth_headers(client, "col_owner")
    member_headers = await _auth_headers(client, "col_member")
    outsider_headers = await _auth_headers(client, "col_out")

    game_owner = await _create_game(client, owner_headers, "Collection Game A")
    game_member = await _create_game(client, owner_headers, "Collection Game B")

    add_owner_library = await client.post(
        "/api/v1/library/",
        headers=owner_headers,
        json={"game_id": game_owner["id"]},
    )
    assert add_owner_library.status_code == 201

    add_member_library = await client.post(
        "/api/v1/library/",
        headers=member_headers,
        json={"game_id": game_member["id"]},
    )
    assert add_member_library.status_code == 201

    create_collection = await client.post(
        "/api/v1/collections/",
        headers=owner_headers,
        json={"name": "Colecao Teste", "description": "desc"},
    )
    assert create_collection.status_code == 201
    collection = create_collection.json()
    collection_id = collection["id"]
    assert collection["member_count"] == 1

    owner_collections = await client.get("/api/v1/collections/", headers=owner_headers)
    assert owner_collections.status_code == 200
    assert len(owner_collections.json()) == 1

    invite_member = await client.post(
        f"/api/v1/collections/{collection_id}/members",
        headers=owner_headers,
        json={"user_id": member["id"]},
    )
    assert invite_member.status_code == 201
    assert invite_member.json()["username"] == "col_member"

    duplicate_member = await client.post(
        f"/api/v1/collections/{collection_id}/members",
        headers=owner_headers,
        json={"user_id": member["id"]},
    )
    assert duplicate_member.status_code == 400

    available_games = await client.get(
        f"/api/v1/collections/{collection_id}/available-games",
        headers=member_headers,
    )
    assert available_games.status_code == 200
    names = [g["name"] for g in available_games.json()]
    assert names == sorted(names)
    assert "Collection Game A" in names
    assert "Collection Game B" in names

    add_game_to_collection = await client.post(
        f"/api/v1/collections/{collection_id}/games",
        headers=member_headers,
        json={"game_id": game_member["id"]},
    )
    assert add_game_to_collection.status_code == 201
    assert add_game_to_collection.json()["name"] == "Collection Game B"

    add_duplicate_game = await client.post(
        f"/api/v1/collections/{collection_id}/games",
        headers=owner_headers,
        json={"game_id": game_member["id"]},
    )
    assert add_duplicate_game.status_code == 400

    outsider_remove_game = await client.delete(
        f"/api/v1/collections/{collection_id}/games/{game_member['id']}",
        headers=outsider_headers,
    )
    assert outsider_remove_game.status_code == 403

    remove_by_owner = await client.delete(
        f"/api/v1/collections/{collection_id}/games/{game_member['id']}",
        headers=owner_headers,
    )
    assert remove_by_owner.status_code == 204

    non_owner_update = await client.patch(
        f"/api/v1/collections/{collection_id}",
        headers=member_headers,
        json={"name": "Novo Nome"},
    )
    assert non_owner_update.status_code == 403

    owner_update = await client.patch(
        f"/api/v1/collections/{collection_id}",
        headers=owner_headers,
        json={"name": "Novo Nome"},
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["name"] == "Novo Nome"

    owner_cannot_leave = await client.delete(
        f"/api/v1/collections/{collection_id}/members/{owner['id']}",
        headers=owner_headers,
    )
    assert owner_cannot_leave.status_code == 400

    member_leave = await client.delete(
        f"/api/v1/collections/{collection_id}/members/{member['id']}",
        headers=member_headers,
    )
    assert member_leave.status_code == 204

    outsider_delete = await client.delete(
        f"/api/v1/collections/{collection_id}",
        headers=outsider_headers,
    )
    assert outsider_delete.status_code == 403

    owner_delete = await client.delete(
        f"/api/v1/collections/{collection_id}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == 204
