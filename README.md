# VamoJoga — API

Backend da plataforma VamoJoga, construído com FastAPI e SQLModel.

## Stack

| | |
|---|---|
| Framework | FastAPI |
| ORM | SQLModel (SQLAlchemy async) |
| Banco | PostgreSQL (asyncpg) |
| Auth | JWT (python-jose · bcrypt) |
| Linguagem | Python 3.12+ |

## Estrutura

```
api/
├── api/
│   ├── core/
│   │   ├── config.py       # Settings via pydantic-settings (.env)
│   │   ├── database.py     # Engine e sessão async
│   │   └── security.py     # JWT e hashing de senha
│   ├── models/             # SQLModel (tabelas)
│   │   ├── user.py
│   │   ├── game.py
│   │   ├── match.py
│   │   ├── match_player.py
│   │   └── friendship.py
│   ├── schemas/            # Pydantic request/response
│   ├── repositories/       # Acesso ao banco (queries)
│   ├── services/           # Regras de negócio
│   └── routers/            # Endpoints FastAPI
├── .env                    # Variáveis de ambiente (não versionado)
├── .env.example
├── requirements.txt
├── Dockerfile
└── entrypoint.sh
```

## Desenvolvimento local

```bash
cd api
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

Crie o `.env` (ou copie de `.env.example`):

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/vamojoga
SECRET_KEY=sua-chave-secreta
DEBUG=True
```

Inicie o servidor:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse a documentação interativa em [http://localhost:8000/docs](http://localhost:8000/docs).

## Endpoints

Todos os endpoints ficam sob o prefixo `/api/v1`.

### Auth
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | Cadastro de usuário |
| POST | `/auth/login` | Login — retorna JWT |

### Users
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/users/me` | Perfil do usuário autenticado |
| GET | `/users/search/` | Busca usuários por nome |
| GET | `/users/{user_id}` | Dados de um usuário |
| GET | `/users/` | Lista todos os usuários |

### Games
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/games/` | Cadastrar jogo |
| GET | `/games/` | Listar jogos |
| GET | `/games/search/` | Buscar jogo por nome |
| GET | `/games/{game_id}` | Detalhes de um jogo |
| PATCH | `/games/{game_id}` | Atualizar jogo |

### Matches
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/matches/` | Registrar partida |
| GET | `/matches/{match_id}` | Detalhes de uma partida |
| GET | `/matches/user/{user_id}` | Partidas de um usuário |

### Ranking
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/ranking/global` | Ranking geral |
| GET | `/ranking/game/{game_id}` | Ranking por jogo |
| GET | `/ranking/user/{user_id}` | Estatísticas de um usuário |

### Friendships
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/friendships/request/{addressee_id}` | Enviar solicitação de amizade |
| POST | `/friendships/{friendship_id}/accept` | Aceitar solicitação |
| POST | `/friendships/{friendship_id}/reject` | Rejeitar solicitação |
| DELETE | `/friendships/{friendship_id}` | Remover amigo |
| GET | `/friendships/` | Listar amigos |
| GET | `/friendships/pending/received` | Solicitações recebidas |
| GET | `/friendships/pending/sent` | Solicitações enviadas |

## Docker

```bash
# A partir da raiz do projeto
docker compose up --build
```
