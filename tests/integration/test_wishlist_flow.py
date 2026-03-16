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
        json={"name": name, "min_players": 1, "max_players": 8},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_wishlist_visibility_and_friend_owners_flow(client):
    owner = await _register(client, "wish_owner", "wish_owner@example.com")
    friend = await _register(client, "wish_friend", "wish_friend@example.com")
    viewer = await _register(client, "wish_viewer", "wish_viewer@example.com")

    owner_headers = await _auth_headers(client, "wish_owner")
    friend_headers = await _auth_headers(client, "wish_friend")
    viewer_headers = await _auth_headers(client, "wish_viewer")

    game_public = await _create_game(client, owner_headers, "Wishlist Public")
    game_private = await _create_game(client, owner_headers, "Wishlist Private")

    # Create friendship owner <-> friend
    send_request = await client.post(
        f"/api/v1/friends/request/{friend['id']}",
        headers=owner_headers,
    )
    assert send_request.status_code == 200

    accept_request = await client.post(
        f"/api/v1/friends/{send_request.json()['id']}/accept",
        headers=friend_headers,
    )
    assert accept_request.status_code == 200

    # Friend owns one game that should appear in friends_who_own
    add_to_friend_library = await client.post(
        "/api/v1/library/",
        headers=friend_headers,
        json={"game_id": game_public["id"]},
    )
    assert add_to_friend_library.status_code == 201

    add_public_wishlist = await client.post(
        "/api/v1/wishlist/",
        headers=owner_headers,
        json={"game_id": game_public["id"], "is_public": True},
    )
    assert add_public_wishlist.status_code == 201
    assert "wish_friend" in add_public_wishlist.json()["friends_who_own"]

    add_private_wishlist = await client.post(
        "/api/v1/wishlist/",
        headers=owner_headers,
        json={"game_id": game_private["id"], "is_public": False},
    )
    assert add_private_wishlist.status_code == 201

    duplicate_add = await client.post(
        "/api/v1/wishlist/",
        headers=owner_headers,
        json={"game_id": game_public["id"], "is_public": True},
    )
    assert duplicate_add.status_code == 400

    my_wishlist = await client.get("/api/v1/wishlist/", headers=owner_headers)
    assert my_wishlist.status_code == 200
    assert len(my_wishlist.json()) == 2

    owner_view = await client.get(f"/api/v1/wishlist/{owner['id']}", headers=owner_headers)
    assert owner_view.status_code == 200
    assert len(owner_view.json()) == 2

    viewer_view = await client.get(f"/api/v1/wishlist/{owner['id']}", headers=viewer_headers)
    assert viewer_view.status_code == 200
    assert len(viewer_view.json()) == 1
    assert viewer_view.json()[0]["game"]["name"] == "Wishlist Public"

    update_visibility = await client.patch(
        f"/api/v1/wishlist/{game_private['id']}/visibility",
        headers=owner_headers,
        json={"is_public": True},
    )
    assert update_visibility.status_code == 200
    assert update_visibility.json()["is_public"] is True

    remove_game = await client.delete(
        f"/api/v1/wishlist/{game_public['id']}",
        headers=owner_headers,
    )
    assert remove_game.status_code == 204

    remove_not_found = await client.delete(
        f"/api/v1/wishlist/{game_public['id']}",
        headers=owner_headers,
    )
    assert remove_not_found.status_code == 404
