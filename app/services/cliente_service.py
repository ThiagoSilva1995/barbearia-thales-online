from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import re
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate


def formatar_telefone(telefone: str) -> str:
    tel_limpo = re.sub(r"\D", "", telefone)
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + (tel_limpo[1:] if tel_limpo.startswith("0") else tel_limpo)
    return tel_limpo


async def criar_cliente(db: AsyncSession, dados: ClienteCreate) -> Cliente:
    nome_formatado = dados.nome.title()
    telefone_formatado = formatar_telefone(dados.telefone)

    novo_cliente = Cliente(
        nome=nome_formatado,
        telefone=telefone_formatado,
        data_nascimento=dados.data_nascimento,
        parabens_enviado=False,
    )

    db.add(novo_cliente)
    await db.commit()
    await db.refresh(novo_cliente)
    return novo_cliente
