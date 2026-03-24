import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Lê a URL do banco de dados das variáveis de ambiente
# Se não existir (no seu PC), usa SQLite local como fallback
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./barbearia.db")

# Configuração do Engine
if DATABASE_URL.startswith("sqlite"):
    # Configurações específicas para SQLite
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,  # Mude para True se quiser ver as queries SQL no console
    )
else:
    # Configurações para PostgreSQL (Produção/Render)
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Garante que a conexão está viva antes de usar
        pool_size=5,
        max_overflow=10,
    )

# Sessão Assíncrona
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


# Dependência para injetar a sessão nas rotas
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Função de inicialização (cria as tabelas se não existirem)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados conectado e tabelas verificadas!")
