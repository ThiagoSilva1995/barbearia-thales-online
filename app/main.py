from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine, Base
from fastapi.staticfiles import StaticFiles

# Importe os routers
from app.routers import (
    auth,
    agenda,
    cadastros,
    relatorios,
    cliente_publico,
    admin_config,  # <--- Novo Router
)

# IMPORTANTE: Importe o modelo Configuracao para ele ser criado no banco
from app.models.configuracao import Configuracao


async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados pronto! (Tabelas verificadas)")
    yield


app = FastAPI(title="Gestão de Barbearia", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="sua_chave_secreta_forte_123")

# Registro dos Routers Modulares
app.include_router(auth.router)
app.include_router(agenda.router)
app.include_router(cadastros.router)
app.include_router(relatorios.router)
app.include_router(cliente_publico.router)
app.include_router(admin_config.router)  # <--- Registrando o novo router

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
