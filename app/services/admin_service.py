from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
import re

from app.models import Cliente, Barbeiro, Servico, Produto, Agendamento

# ==========================================
# CLIENTES
# ==========================================


async def get_clientes(db: AsyncSession, search: str = None, limit: int = 100):
    query = select(Cliente).order_by(Cliente.nome)
    if search:
        query = query.where(Cliente.nome.ilike(f"%{search}%"))
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def criar_cliente(
    db: AsyncSession, nome: str, telefone: str, data_nascimento: date
):
    nome_formatado = nome.title()
    tel_limpo = re.sub(r"\D", "", telefone)
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + (tel_limpo[1:] if tel_limpo.startswith("0") else tel_limpo)

    cliente = Cliente(
        nome=nome_formatado,
        telefone=tel_limpo,
        data_nascimento=data_nascimento,
        parabens_enviado=False,
    )
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


async def atualizar_cliente(
    db: AsyncSession, cliente_id: int, nome: str, telefone: str, data_nascimento: date
):
    stmt = select(Cliente).where(Cliente.id == cliente_id)
    result = await db.execute(stmt)
    cliente = result.scalars().first()
    if not cliente:
        raise ValueError("Cliente não encontrado")

    cliente.nome = nome.title()
    tel_limpo = re.sub(r"\D", "", telefone)
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + (tel_limpo[1:] if tel_limpo.startswith("0") else tel_limpo)
    cliente.telefone = tel_limpo
    cliente.data_nascimento = data_nascimento

    await db.commit()
    await db.refresh(cliente)
    return cliente


async def excluir_cliente(db: AsyncSession, cliente_id: int):
    stmt = select(Cliente).where(Cliente.id == cliente_id)
    result = await db.execute(stmt)
    cliente = result.scalars().first()
    if cliente:
        await db.delete(cliente)
        await db.commit()
        return True
    return False


# ==========================================
# BARBEIROS
# ==========================================


async def get_barbeiros(db: AsyncSession):
    result = await db.execute(select(Barbeiro).order_by(Barbeiro.nome))
    return result.scalars().all()


async def criar_barbeiro(db: AsyncSession, nome: str, telefone: str):
    barbeiro = Barbeiro(nome=nome.title(), telefone=telefone)
    db.add(barbeiro)
    await db.commit()
    await db.refresh(barbeiro)
    return barbeiro


async def atualizar_barbeiro(
    db: AsyncSession, barbeiro_id: int, nome: str, telefone: str
):
    stmt = select(Barbeiro).where(Barbeiro.id == barbeiro_id)
    result = await db.execute(stmt)
    barbeiro = result.scalars().first()
    if not barbeiro:
        raise ValueError("Barbeiro não encontrado")
    barbeiro.nome = nome.title()
    barbeiro.telefone = telefone
    await db.commit()
    await db.refresh(barbeiro)
    return barbeiro


async def excluir_barbeiro(db: AsyncSession, barbeiro_id: int):
    stmt = select(Barbeiro).where(Barbeiro.id == barbeiro_id)
    result = await db.execute(stmt)
    barbeiro = result.scalars().first()
    if barbeiro:
        await db.delete(barbeiro)
        await db.commit()
        return True
    return False


# ==========================================
# SERVIÇOS (CORTES)
# ==========================================


async def get_servicos(db: AsyncSession):
    result = await db.execute(select(Servico).order_by(Servico.nome))
    return result.scalars().all()


async def criar_servico(db: AsyncSession, nome: str, preco: Decimal):
    servico = Servico(nome=nome, preco=preco)
    db.add(servico)
    await db.commit()
    await db.refresh(servico)
    return servico


async def atualizar_servico(
    db: AsyncSession, servico_id: int, nome: str, preco: Decimal
):
    stmt = select(Servico).where(Servico.id == servico_id)
    result = await db.execute(stmt)
    servico = result.scalars().first()
    if not servico:
        raise ValueError("Serviço não encontrado")
    servico.nome = nome
    servico.preco = preco
    await db.commit()
    await db.refresh(servico)
    return servico


async def excluir_servico(db: AsyncSession, servico_id: int):
    stmt = select(Servico).where(Servico.id == servico_id)
    result = await db.execute(stmt)
    servico = result.scalars().first()
    if servico:
        await db.delete(servico)
        await db.commit()
        return True
    return False


# ==========================================
# PRODUTOS
# ==========================================


async def get_produtos(db: AsyncSession):
    result = await db.execute(select(Produto).order_by(Produto.nome))
    return result.scalars().all()


async def criar_produto(db: AsyncSession, nome: str, preco: Decimal, estoque: int):
    produto = Produto(nome=nome, preco=preco, estoque=estoque)
    db.add(produto)
    await db.commit()
    await db.refresh(produto)
    return produto


async def atualizar_produto(
    db: AsyncSession, produto_id: int, nome: str, preco: Decimal, estoque: int
):
    stmt = select(Produto).where(Produto.id == produto_id)
    result = await db.execute(stmt)
    produto = result.scalars().first()
    if not produto:
        raise ValueError("Produto não encontrado")
    produto.nome = nome
    produto.preco = preco
    produto.estoque = estoque
    await db.commit()
    await db.refresh(produto)
    return produto


async def excluir_produto(db: AsyncSession, produto_id: int):
    stmt = select(Produto).where(Produto.id == produto_id)
    result = await db.execute(stmt)
    produto = result.scalars().first()
    if produto:
        await db.delete(produto)
        await db.commit()
        return True
    return False


# ==========================================
# ESTATÍSTICAS GERAIS
# ==========================================


async def get_estatisticas_gerais(db: AsyncSession, data_inicio: date, data_fim: date):
    # Receita Total de Cortes no Período
    # Usamos func.sum() corretamente
    query_receita_cortes = (
        select(func.sum(Servico.preco))
        .select_from(Agendamento)
        .join(Agendamento.servicos)
        .where(
            Agendamento.pago == True,
            Agendamento.data >= data_inicio,
            Agendamento.data <= data_fim,
        )
    )
    res_rec = await db.execute(query_receita_cortes)
    receita_cortes = res_rec.scalar() or Decimal("0.00")

    # Receita de Produtos (Estimativa baseada no preço atual do produto vinculado)
    # Nota: Em um sistema real de histórico, deveríamos salvar o preço no momento da venda.
    # Aqui, somamos o preço atual dos produtos vinculados aos agendamentos pagos.
    query_receita_produtos = (
        select(func.sum(Produto.preco))
        .select_from(Agendamento)
        .join(Agendamento.produtos)
        .where(
            Agendamento.pago == True,
            Agendamento.data >= data_inicio,
            Agendamento.data <= data_fim,
        )
    )
    res_prod = await db.execute(query_receita_produtos)
    receita_produtos = res_prod.scalar() or Decimal("0.00")

    return {
        "receita_cortes": receita_cortes,
        "receita_produtos": receita_produtos,
        "receita_total": receita_cortes + receita_produtos,
    }
