from uuid import uuid4

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
        json={"name": name, "min_players": 1, "max_players": 10},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_scoring_template_crud_validations_and_permissions(client):
    owner = await _register(client, "st_owner", "st_owner@example.com")
    other = await _register(client, "st_other", "st_other@example.com")

    owner_headers = await _auth_headers(client, "st_owner")
    other_headers = await _auth_headers(client, "st_other")

    game = await _create_game(client, owner_headers, "Scoring Test Game")

    missing_game_payload = {
        "game_id": str(uuid4()),
        "name": "Template X",
        "match_mode": "individual",
        "fields": [{"name": "Pontos", "field_type": "numeric", "display_order": 1}],
    }
    missing_game = await client.post(
        "/api/v1/scoring-templates/",
        headers=owner_headers,
        json=missing_game_payload,
    )
    assert missing_game.status_code == 404

    invalid_field_type_payload = {
        "game_id": game["id"],
        "name": "Template Invalid Field",
        "match_mode": "individual",
        "fields": [{"name": "Pontos", "field_type": "text", "display_order": 1}],
    }
    invalid_field_type = await client.post(
        "/api/v1/scoring-templates/",
        headers=owner_headers,
        json=invalid_field_type_payload,
    )
    assert invalid_field_type.status_code == 400

    invalid_range_payload = {
        "game_id": game["id"],
        "name": "Template Invalid Range",
        "match_mode": "individual",
        "fields": [
            {
                "name": "Pontos",
                "field_type": "numeric",
                "min_value": 10,
                "max_value": 1,
                "display_order": 1,
            }
        ],
    }
    invalid_range = await client.post(
        "/api/v1/scoring-templates/",
        headers=owner_headers,
        json=invalid_range_payload,
    )
    assert invalid_range.status_code == 400

    valid_payload = {
        "game_id": game["id"],
        "name": "Template Valido",
        "description": "Template para testes",
        "match_mode": "individual",
        "fields": [
            {
                "name": "Pontos",
                "field_type": "numeric",
                "min_value": 0,
                "max_value": 200,
                "display_order": 1,
                "is_required": True,
            },
            {
                "name": "Vencedor",
                "field_type": "boolean",
                "display_order": 2,
                "is_required": False,
            },
        ],
    }
    create_template = await client.post(
        "/api/v1/scoring-templates/",
        headers=owner_headers,
        json=valid_payload,
    )
    assert create_template.status_code == 201
    template = create_template.json()
    template_id = template["id"]
    assert len(template["fields"]) == 2

    get_template = await client.get(
        f"/api/v1/scoring-templates/{template_id}",
        headers=owner_headers,
    )
    assert get_template.status_code == 200
    assert get_template.json()["name"] == "Template Valido"

    search_templates = await client.get(
        "/api/v1/scoring-templates/search/",
        headers=owner_headers,
        params={"q": "Valido", "limit": 10},
    )
    assert search_templates.status_code == 200
    assert len(search_templates.json()) >= 1

    list_by_game = await client.get(
        f"/api/v1/scoring-templates/game/{game['id']}",
        headers=owner_headers,
    )
    assert list_by_game.status_code == 200
    assert len(list_by_game.json()) >= 1

    forbidden_update = await client.patch(
        f"/api/v1/scoring-templates/{template_id}",
        headers=other_headers,
        json={"name": "Nao Pode"},
    )
    assert forbidden_update.status_code == 403

    invalid_mode_update = await client.patch(
        f"/api/v1/scoring-templates/{template_id}",
        headers=owner_headers,
        json={"match_mode": "duo"},
    )
    assert invalid_mode_update.status_code == 400

    invalid_fields_update = await client.patch(
        f"/api/v1/scoring-templates/{template_id}",
        headers=owner_headers,
        json={"fields": []},
    )
    assert invalid_fields_update.status_code == 400

    valid_update = await client.patch(
        f"/api/v1/scoring-templates/{template_id}",
        headers=owner_headers,
        json={
            "name": "Template Atualizado",
            "is_active": True,
            "fields": [
                {
                    "name": "Ranking",
                    "field_type": "ranking",
                    "display_order": 1,
                    "is_required": True,
                }
            ],
        },
    )
    assert valid_update.status_code == 200
    assert valid_update.json()["name"] == "Template Atualizado"
    assert len(valid_update.json()["fields"]) == 1
    assert valid_update.json()["fields"][0]["field_type"] == "ranking"

    forbidden_delete = await client.delete(
        f"/api/v1/scoring-templates/{template_id}",
        headers=other_headers,
    )
    assert forbidden_delete.status_code == 403

    owner_delete = await client.delete(
        f"/api/v1/scoring-templates/{template_id}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == 204

    list_after_delete = await client.get(
        f"/api/v1/scoring-templates/game/{game['id']}",
        headers=owner_headers,
    )
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []
