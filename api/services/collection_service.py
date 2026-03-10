import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.collection import Collection, CollectionJogo, CollectionMembro
from api.models.user import User
from api.repositories.collection_repository import CollectionRepository
from api.repositories.game_repository import GameRepository
from api.repositories.library_repository import LibraryRepository
from api.repositories.user_repository import UserRepository
from api.schemas.collection import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionJogoResponse,
    CollectionResponse,
    CollectionUpdate,
    MembroResponse,
)


class CollectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CollectionRepository(session)
        self.game_repo = GameRepository(session)
        self.user_repo = UserRepository(session)
        self.library_repo = LibraryRepository(session)
        self._session = session

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _assert_membro(self, collection_id: UUID, user_id: UUID) -> CollectionMembro:
        membro = await self.repo.get_membro(collection_id, user_id)
        if not membro:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não é membro deste collection",
            )
        return membro

    async def _assert_owner(self, collection: Collection, user_id: UUID) -> None:
        if collection.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas o dono pode realizar esta ação",
            )

    async def _build_response(self, collection: Collection) -> CollectionResponse:
        mc = await self.repo.count_membros(collection.id)
        gc = await self.repo.count_jogos(collection.id)
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            owner_id=collection.owner_id,
            created_at=collection.created_at,
            member_count=mc,
            game_count=gc,
        )

    async def _build_detail(self, collection: Collection) -> CollectionDetailResponse:
        membros_db = await self.repo.get_membros(collection.id)
        jogos_db = await self.repo.get_jogos(collection.id)

        membros = []
        for m in membros_db:
            user = await self.user_repo.get_by_id(m.user_id)
            if user:
                membros.append(MembroResponse(
                    user_id=m.user_id,
                    username=user.username,
                    full_name=user.full_name,
                    role=m.role,
                    joined_at=m.joined_at,
                ))

        jogos = []
        for j in jogos_db:
            game = await self.game_repo.get_by_id(j.game_id)
            adder = await self.user_repo.get_by_id(j.added_by)
            if game:
                jogos.append(CollectionJogoResponse(
                    game_id=game.id,
                    name=game.name,
                    bgg_id=game.bgg_id,
                    image_url=getattr(game, "image_url", None),
                    bayes_rating=getattr(game, "bayes_rating", None),
                    year=getattr(game, "year", None),
                    added_by=j.added_by,
                    added_by_username=adder.username if adder else None,
                    added_at=j.added_at,
                ))

        return CollectionDetailResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            owner_id=collection.owner_id,
            created_at=collection.created_at,
            member_count=len(membros),
            game_count=len(jogos),
            members=membros,
            games=jogos,
        )

    # ------------------------------------------------------------------
    # Collection CRUD
    # ------------------------------------------------------------------

    async def criar(self, current_user: User, data: CollectionCreate) -> CollectionDetailResponse:
        collection = Collection(
            name=data.name,
            description=data.description,
            owner_id=current_user.id,
        )
        collection = await self.repo.create(collection)

        # Dono já entra como membro owner
        membro = CollectionMembro(
            collection_id=collection.id,
            user_id=current_user.id,
            role="owner",
        )
        await self.repo.add_membro(membro)
        await self._session.commit()
        await self._session.refresh(collection)

        return await self._build_detail(collection)

    async def listar_meus(self, current_user: User) -> list[CollectionResponse]:
        collections = await self.repo.get_collections_do_usuario(current_user.id)
        return [await self._build_response(a) for a in collections]

    async def detalhe(self, collection_id: UUID, current_user: User) -> CollectionDetailResponse:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_membro(collection_id, current_user.id)
        return await self._build_detail(collection)

    async def atualizar(
        self, collection_id: UUID, data: CollectionUpdate, current_user: User
    ) -> CollectionDetailResponse:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_owner(collection, current_user.id)

        if data.name is not None:
            collection.name = data.name
        if data.description is not None:
            collection.description = data.description

        collection = await self.repo.update(collection)
        await self._session.commit()
        return await self._build_detail(collection)

    async def excluir(self, collection_id: UUID, current_user: User) -> None:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_owner(collection, current_user.id)

        # Remove membros e jogos primeiro (sem FK cascade)
        for m in await self.repo.get_membros(collection_id):
            await self.repo.remove_membro(m)
        for j in await self.repo.get_jogos(collection_id):
            await self.repo.remove_jogo(j)

        await self.repo.delete(collection)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Membros
    # ------------------------------------------------------------------

    async def convidar_membro(
        self, collection_id: UUID, user_id: UUID, current_user: User
    ) -> MembroResponse:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_owner(collection, current_user.id)

        convidado = await self.user_repo.get_by_id(user_id)
        if not convidado:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        existente = await self.repo.get_membro(collection_id, user_id)
        if existente:
            raise HTTPException(status_code=400, detail="Usuário já é membro")

        membro = CollectionMembro(collection_id=collection_id, user_id=user_id, role="member")
        membro = await self.repo.add_membro(membro)
        await self._session.commit()

        return MembroResponse(
            user_id=convidado.id,
            username=convidado.username,
            full_name=convidado.full_name,
            role=membro.role,
            joined_at=membro.joined_at,
        )

    async def remover_membro(
        self, collection_id: UUID, user_id: UUID, current_user: User
    ) -> None:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")

        # Dono remove qualquer um; membro pode sair por conta própria
        if current_user.id != collection.owner_id and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para remover este membro",
            )

        # Dono não pode sair do próprio collection
        if user_id == collection.owner_id:
            raise HTTPException(
                status_code=400,
                detail="O dono não pode sair do collection. Exclua o collection se quiser.",
            )

        membro = await self.repo.get_membro(collection_id, user_id)
        if not membro:
            raise HTTPException(status_code=404, detail="Membro não encontrado")

        await self.repo.remove_membro(membro)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Jogos
    # ------------------------------------------------------------------

    async def adicionar_jogo(
        self, collection_id: UUID, game_id: UUID, current_user: User
    ) -> CollectionJogoResponse:
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_membro(collection_id, current_user.id)

        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Jogo não encontrado")

        existente = await self.repo.get_jogo(collection_id, game_id)
        if existente:
            raise HTTPException(status_code=400, detail="Jogo já está no collection")

        jogo = CollectionJogo(
            collection_id=collection_id,
            game_id=game_id,
            added_by=current_user.id,
        )
        jogo = await self.repo.add_jogo(jogo)
        await self._session.commit()

        return CollectionJogoResponse(
            game_id=game.id,
            name=game.name,
            bgg_id=game.bgg_id,
            image_url=getattr(game, "image_url", None),
            bayes_rating=getattr(game, "bayes_rating", None),
            year=getattr(game, "year", None),
            added_by=current_user.id,
            added_by_username=current_user.username,
            added_at=jogo.added_at,
        )

    async def jogos_disponiveis(
        self, collection_id: UUID, current_user: User
    ) -> list[CollectionJogoResponse]:
        """Jogos nas biblitoecas dos membros que ainda não estão na collection."""
        collection = await self.repo.get_by_id(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_membro(collection_id, current_user.id)

        # jogos já na collection
        ja_na_collection = {
            j.game_id for j in await self.repo.get_jogos(collection_id)
        }

        # percorre biblioteca de cada membro
        membros = await self.repo.get_membros(collection_id)
        seen: set[UUID] = set()
        result: list[CollectionJogoResponse] = []
        for membro in membros:
            entries = await self.library_repo.get_by_user(membro.user_id)
            user = await self.user_repo.get_by_id(membro.user_id)
            for entry in entries:
                if entry.game_id in ja_na_collection or entry.game_id in seen:
                    continue
                seen.add(entry.game_id)
                game = await self.game_repo.get_by_id(entry.game_id)
                if game:
                    result.append(CollectionJogoResponse(
                        game_id=game.id,
                        name=game.name,
                        bgg_id=game.bgg_id,
                        image_url=getattr(game, "image_url", None),
                        bayes_rating=getattr(game, "bayes_rating", None),
                        year=getattr(game, "year", None),
                        added_by=membro.user_id,
                        added_by_username=user.username if user else None,
                        added_at=entry.created_at,
                    ))

        result.sort(key=lambda g: g.name)
        return result

    async def remover_jogo(
        self, collection_id: UUID, game_id: UUID, current_user: User
    ) -> None:
        if not collection:
            raise HTTPException(status_code=404, detail="Collection não encontrado")
        await self._assert_membro(collection_id, current_user.id)

        jogo = await self.repo.get_jogo(collection_id, game_id)
        if not jogo:
            raise HTTPException(status_code=404, detail="Jogo não está no collection")

        # Apenas quem adicionou ou o dono pode remover
        if jogo.added_by != current_user.id and collection.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas quem adicionou o jogo ou o dono pode removê-lo",
            )

        await self.repo.remove_jogo(jogo)
        await self._session.commit()
