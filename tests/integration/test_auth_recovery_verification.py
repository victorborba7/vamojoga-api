import pytest
from sqlalchemy import select

from api.models.email_verification import EmailVerificationToken
from api.models.password_reset import PasswordResetToken
from api.models.user import User


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


async def _login(client, identifier: str, password: str) -> int:
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    return response.status_code


async def _auth_headers(client, identifier: str, password: str = "12345678") -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email_is_silent_success(client):
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 200
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow(client, db_session, monkeypatch):
    await _register(client, "recover_user", "recover_user@example.com")
    monkeypatch.setattr("api.services.auth_service.send_password_reset_email", lambda *_args, **_kwargs: None)

    forgot_response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "recover_user@example.com"},
    )
    assert forgot_response.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.email == "recover_user@example.com"))
    ).scalar_one()
    reset_token = (
        await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
    ).scalar_one()
    reset_token_id = reset_token.id

    invalid_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid-token", "new_password": "newsecret123"},
    )
    assert invalid_reset.status_code == 400

    valid_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token.token, "new_password": "newsecret123"},
    )
    assert valid_reset.status_code == 200

    db_session.expire_all()
    reset_token_after = (
        await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.id == reset_token_id)
        )
    ).scalar_one()
    assert reset_token_after.used is True

    old_login_status = await _login(client, "recover_user@example.com", "12345678")
    assert old_login_status == 401

    new_login_status = await _login(client, "recover_user", "newsecret123")
    assert new_login_status == 200


@pytest.mark.asyncio
async def test_verify_email_and_resend_verification_flow(client, db_session):
    created = await _register(client, "verify_user", "verify_user@example.com")
    assert created["email_verified"] is False

    user = (
        await db_session.execute(select(User).where(User.email == "verify_user@example.com"))
    ).scalar_one()

    verification_token = (
        await db_session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
        )
    ).scalar_one()
    user_id = user.id
    verification_token_id = verification_token.id

    invalid_verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": "invalid-token"},
    )
    assert invalid_verify.status_code == 400

    verify_response = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token.token},
    )
    assert verify_response.status_code == 200

    db_session.expire_all()
    refreshed_user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    used_verification_token = (
        await db_session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.id == verification_token_id)
        )
    ).scalar_one()
    assert refreshed_user.email_verified is True
    assert used_verification_token.used is True

    headers = await _auth_headers(client, "verify_user")
    resend_after_verified = await client.post(
        "/api/v1/auth/resend-verification",
        headers=headers,
    )
    assert resend_after_verified.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_creates_new_token_for_unverified_user(client, db_session):
    await _register(client, "resend_user", "resend_user@example.com")
    headers = await _auth_headers(client, "resend_user@example.com")

    user = (
        await db_session.execute(select(User).where(User.email == "resend_user@example.com"))
    ).scalar_one()
    before_count = len(
        (
            await db_session.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalars().all()
    )

    resend_response = await client.post(
        "/api/v1/auth/resend-verification",
        headers=headers,
    )
    assert resend_response.status_code == 200

    after_count = len(
        (
            await db_session.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalars().all()
    )
    assert after_count == before_count + 1
