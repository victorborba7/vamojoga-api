from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from api.schemas.game import GameResponse


# ----------------------------------------------------------------
# Library Schemas
# ----------------------------------------------------------------

class LibraryEntryResponse(BaseModel):
    """Um jogo da coleção do usuário com estatísticas de partidas."""
    id: UUID
    game: GameResponse
    match_count: int
    added_at: datetime


class LibraryGameAdd(BaseModel):
    game_id: UUID


# ----------------------------------------------------------------
# Wishlist Schemas
# ----------------------------------------------------------------

class WishlistEntryResponse(BaseModel):
    """Um jogo na wishlist do usuário."""
    id: UUID
    game: GameResponse
    is_public: bool
    added_at: datetime
    friends_who_own: list[str]  # Lista de usernames de amigos que possuem o jogo


class WishlistGameAdd(BaseModel):
    game_id: UUID
    is_public: bool = True


class WishlistVisibilityUpdate(BaseModel):
    is_public: bool
