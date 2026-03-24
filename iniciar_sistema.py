import asyncio
import sys
import os

# Adiciona a raiz ao path para importar o app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from decimal import Decimal
from datetime import date

# Imports dos Models
from app.database import Base
from app.models.barbeiro import Barbeiro
from app.models.cliente import Cliente
from app.models.servico import Servico
from app.models.produto import Produto

# URL do Banco
DATABASE_URL = "sqlite+aiosqlite:///./barbearia.db"


async def init_db():
    # 1. Criar Engine e Tabelas
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        print("🔨 Criando tabelas no banco de dados...")
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Tabelas criadas com sucesso!")

    # 2. Sessão para inserir dados
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # --- A. Criar o Barbeiro Dono (ID 1) ---
        dono = Barbeiro(nome="Dono", telefone="5511999999999")
        session.add(dono)
        await session.commit()
        await session.refresh(dono)
        print(f"👤 Barbeiro 'Dono' criado com ID: {dono.id}")

        # --- B. Criar Serviços Padrão ---
        servicos_padrao = [
            ("Corte Social", Decimal("30.00")),
            ("Barba Completa", Decimal("25.00")),
            ("Corte + Barba", Decimal("50.00")),
            ("Pezinho/Sobrancelha", Decimal("10.00")),
            ("Platinado", Decimal("80.00")),
        ]

        for nome, preco in servicos_padrao:
            s = Servico(nome=nome, preco=preco)
            session.add(s)

        await session.commit()
        print(f"✂️ {len(servicos_padrao)} serviços criados.")

        # --- C. Criar Produtos Padrão ---
        produtos_padrao = [
            ("Pomada Modeladora", Decimal("45.00"), 20),
            ("Óleo para Barba", Decimal("35.00"), 15),
            ("Shampoo Especial", Decimal("25.00"), 30),
            ("Minoxidil", Decimal("60.00"), 10),
        ]

        for nome, preco, estoque in produtos_padrao:
            p = Produto(nome=nome, preco=preco, estoque=estoque)
            session.add(p)

        await session.commit()
        print(f"🧴 {len(produtos_padrao)} produtos criados.")

        # --- D. Criar Cliente de Teste ---
        cliente_teste = Cliente(
            nome="Cliente Exemplo",
            telefone="5511988887777",
            data_nascimento=date(1990, 1, 1),
            parabens_enviado=False,
        )
        session.add(cliente_teste)
        await session.commit()
        print("🙍 Cliente de teste criado.")

    print("\n🎉 SISTEMA INICIALIZADO COM SUCESSO!")
    print("🚀 Agora você pode rodar: python -m uvicorn app.main:app --reload")
    print(
        f"💡 Dica: O ID do Barbeiro Dono é {dono.id}. Use este ID para configurar o sistema fixo."
    )


if __name__ == "__main__":
    asyncio.run(init_db())
