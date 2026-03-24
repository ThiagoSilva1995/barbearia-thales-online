# cria_dono.py (Rode uma vez: python cria_dono.py)
import asyncio
from app.database import AsyncSessionLocal
from app.models.barbeiro import Barbeiro
from sqlalchemy import select


async def criar_dono():
    async with AsyncSessionLocal() as db:
        # Verifica se já existe
        stmt = select(Barbeiro).where(Barbeiro.nome == "Dono")
        res = await db.execute(stmt)
        dono = res.scalars().first()

        if not dono:
            dono = Barbeiro(nome="Dono", telefone="5511999999999")
            db.add(dono)
            await db.commit()
            print("✅ Dono criado com ID:", dono.id)
        else:
            print("ℹ️ Dono já existe com ID:", dono.id)


if __name__ == "__main__":
    asyncio.run(criar_dono())
