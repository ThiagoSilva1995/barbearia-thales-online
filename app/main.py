from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles  # <--- Confirme este import
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine, Base
from app.models.configuracao import Configuracao
from app.routers import (
    auth,
    agenda,
    cadastros,
    relatorios,
    cliente_publico,
    admin_config,
)
import os  # <--- Adicione este import


async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados pronto! (Tabelas verificadas)")
    yield


app = FastAPI(title="Gestão de Barbearia", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="sua_chave_secreta_forte_123")

# --- CORREÇÃO: Montar arquivos estáticos com verificação ---
static_path = "app/static"
if not os.path.exists(static_path):
    os.makedirs(static_path)  # Cria a pasta se não existir
    # Cria um manifest.json vazio padrão só para garantir que o arquivo exista
    with open(os.path.join(static_path, "manifest.json"), "w", encoding="utf-8") as f:
        f.write("{}")

app.mount("/static", StaticFiles(directory=static_path), name="static")
# -----------------------------------------------------------

app.include_router(auth.router)
app.include_router(agenda.router)
app.include_router(cadastros.router)
app.include_router(relatorios.router)
app.include_router(cliente_publico.router)
app.include_router(admin_config.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
