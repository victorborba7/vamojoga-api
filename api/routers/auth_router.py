from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.user import (
    ForgotPasswordRequest,
    GuestInviteValidationResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from api.services.auth_service import AuthService
from api.services.guest_service import GuestService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    service = AuthService(session)
    return await service.register(data)


@router.get("/guest-invite/{token}", response_model=GuestInviteValidationResponse)
async def validate_guest_invite(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> GuestInviteValidationResponse:
    return await GuestService(session).validate_invite(token)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    service = AuthService(session)
    return await service.login(data)


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuthService(session)
    await service.forgot_password(data.email)
    return {"message": "Se o e-mail existir, um link de recuperação foi enviado."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuthService(session)
    await service.reset_password(data.token, data.new_password)
    return {"message": "Senha redefinida com sucesso."}


@router.post("/verify-email", status_code=200)
async def verify_email(
    data: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuthService(session)
    await service.verify_email(data.token)
    return {"message": "E-mail verificado com sucesso."}


@router.post("/resend-verification", status_code=200)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = AuthService(session)
    await service.resend_verification(current_user.id)
    return {"message": "E-mail de verificação reenviado."}
