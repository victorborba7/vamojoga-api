import pytest


async def _register(client, username: str, email: str, password: str = "12345678") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201
    return response.json()


async def _login_headers(client, identifier: str, password: str = "12345678") -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_friendship_request_accept_list_and_remove_flow(client):
    alice = await _register(client, "friend_alice", "friend_alice@example.com")
    bob = await _register(client, "friend_bob", "friend_bob@example.com")

    alice_headers = await _login_headers(client, "friend_alice@example.com")
    bob_headers = await _login_headers(client, "friend_bob")

    send_response = await client.post(
        f"/api/v1/friends/request/{bob['id']}",
        headers=alice_headers,
    )
    assert send_response.status_code == 200
    friendship = send_response.json()
    assert friendship["status"] == "pending"

    pending_received = await client.get(
        "/api/v1/friends/pending/received",
        headers=bob_headers,
    )
    assert pending_received.status_code == 200
    assert len(pending_received.json()) == 1

    pending_sent = await client.get(
        "/api/v1/friends/pending/sent",
        headers=alice_headers,
    )
    assert pending_sent.status_code == 200
    assert len(pending_sent.json()) == 1

    accept_response = await client.post(
        f"/api/v1/friends/{friendship['id']}/accept",
        headers=bob_headers,
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    alice_friends = await client.get("/api/v1/friends/", headers=alice_headers)
    assert alice_friends.status_code == 200
    assert len(alice_friends.json()) == 1
    assert alice_friends.json()[0]["username"] == "friend_bob"

    bob_friends = await client.get("/api/v1/friends/", headers=bob_headers)
    assert bob_friends.status_code == 200
    assert len(bob_friends.json()) == 1
    assert bob_friends.json()[0]["username"] == "friend_alice"

    remove_response = await client.delete(
        f"/api/v1/friends/{friendship['id']}",
        headers=alice_headers,
    )
    assert remove_response.status_code == 204

    alice_friends_after = await client.get("/api/v1/friends/", headers=alice_headers)
    assert alice_friends_after.status_code == 200
    assert alice_friends_after.json() == []


@pytest.mark.asyncio
async def test_friendship_reject_and_resend_flow(client):
    carol = await _register(client, "friend_carol", "friend_carol@example.com")
    dave = await _register(client, "friend_dave", "friend_dave@example.com")

    carol_headers = await _login_headers(client, "friend_carol")
    dave_headers = await _login_headers(client, "friend_dave@example.com")

    first_request = await client.post(
        f"/api/v1/friends/request/{dave['id']}",
        headers=carol_headers,
    )
    assert first_request.status_code == 200

    reject_response = await client.post(
        f"/api/v1/friends/{first_request.json()['id']}/reject",
        headers=dave_headers,
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    resend_response = await client.post(
        f"/api/v1/friends/request/{dave['id']}",
        headers=carol_headers,
    )
    assert resend_response.status_code == 200
    assert resend_response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_friendship_reverse_pending_auto_accept_and_validation_errors(client):
    eve = await _register(client, "friend_eve", "friend_eve@example.com")
    frank = await _register(client, "friend_frank", "friend_frank@example.com")

    eve_headers = await _login_headers(client, "friend_eve")
    frank_headers = await _login_headers(client, "friend_frank")

    self_request = await client.post(
        f"/api/v1/friends/request/{eve['id']}",
        headers=eve_headers,
    )
    assert self_request.status_code == 400

    send_response = await client.post(
        f"/api/v1/friends/request/{frank['id']}",
        headers=eve_headers,
    )
    assert send_response.status_code == 200
    assert send_response.json()["status"] == "pending"

    reverse_send = await client.post(
        f"/api/v1/friends/request/{eve['id']}",
        headers=frank_headers,
    )
    assert reverse_send.status_code == 200
    assert reverse_send.json()["status"] == "accepted"

    duplicate_after_accept = await client.post(
        f"/api/v1/friends/request/{frank['id']}",
        headers=eve_headers,
    )
    assert duplicate_after_accept.status_code == 400
