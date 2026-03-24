from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete
from sqlalchemy.orm import selectinload
from datetime import date, time
from typing import List, Optional, Dict
from decimal import Decimal
from app.models.agendamento import Agendamento
from app.models.servico import Servico
from app.models.produto import Produto, agendamento_produto
from app.models.cliente import Cliente
from app.models.barbeiro import Barbeiro
from app.schemas.agendamento import AgendamentoCreate


async def verificar_disponibilidade(
    db: AsyncSession,
    barbeiro_id: int,
    data: date,
    hora: time,
    exclude_id: Optional[int] = None,
) -> bool:
    query = select(Agendamento).where(
        Agendamento.barbeiro_id == barbeiro_id,
        Agendamento.data == data,
        Agendamento.hora == hora,
        Agendamento.is_confirmed == False,
    )
    if exclude_id:
        query = query.where(Agendamento.id != exclude_id)
    result = await db.execute(query)
    return result.scalars().first() is not None


async def criar_agendamento(db: AsyncSession, dados: AgendamentoCreate):
    ocupado = await verificar_disponibilidade(
        db, dados.barbeiro_id, dados.data, dados.hora
    )
    if ocupado:
        raise ValueError("Horário já agendado para este barbeiro.")

    novo_agd = Agendamento(
        cliente_id=dados.cliente_id,
        barbeiro_id=dados.barbeiro_id,
        data=dados.data,
        hora=dados.hora,
        pago=False,
        is_confirmed=False,
    )
    if dados.servico_ids and len(dados.servico_ids) > 0:
        stmt = select(Servico).where(Servico.id.in_(dados.servico_ids))
        result = await db.execute(stmt)
        novo_agd.servicos = result.scalars().all()

    db.add(novo_agd)
    await db.commit()
    await db.refresh(novo_agd)
    return novo_agd


async def remover_agendamento(db: AsyncSession, agendamento_id: int) -> bool:
    stmt = select(Agendamento).where(Agendamento.id == agendamento_id)
    result = await db.execute(stmt)
    agendamento = result.scalars().first()
    if agendamento:
        await db.delete(agendamento)
        await db.commit()
        return True
    return False


async def confirmar_pagamento_e_baixar_estoque(
    db: AsyncSession,
    agendamento_id: int,
    servico_ids: List[int],
    produtos_qtd: Dict[int, int],
):
    stmt = (
        select(Agendamento)
        .options(
            selectinload(Agendamento.cliente),
            selectinload(Agendamento.barbeiro),
            selectinload(Agendamento.servicos),
            selectinload(Agendamento.produtos),
        )
        .where(Agendamento.id == agendamento_id)
    )
    result = await db.execute(stmt)
    agd = result.scalars().first()

    if not agd:
        raise ValueError("Agendamento não encontrado.")
    if agd.pago:
        raise ValueError("Este agendamento já foi pago.")

    # Atualizar Serviços
    agd.servicos.clear()
    if servico_ids and len(servico_ids) > 0:
        stmt_serv = select(Servico).where(Servico.id.in_(servico_ids))
        res_serv = await db.execute(stmt_serv)
        for s in res_serv.scalars().all():
            agd.servicos.append(s)

    # Processar Produtos com INSERT MANUAL para garantir quantidade
    total_produtos_val = Decimal("0.00")

    # Limpar associações antigas se houver
    await db.execute(
        delete(agendamento_produto).where(
            agendamento_produto.c.agendamento_id == agd.id
        )
    )

    for prod_id, qtd in produtos_qtd.items():
        if qtd <= 0:
            continue
        stmt_prod = select(Produto).where(Produto.id == prod_id)
        res_prod = await db.execute(stmt_prod)
        produto = res_prod.scalars().first()

        if not produto:
            raise ValueError(f"Produto ID {prod_id} não encontrado.")
        if produto.estoque < qtd:
            raise ValueError(
                f"Estoque insuficiente para '{produto.nome}'. Disponível: {produto.estoque}."
            )

        produto.estoque -= qtd
        total_produtos_val += produto.preco * qtd

        # Insert explícito na tabela associativa com quantidade
        await db.execute(
            insert(agendamento_produto).values(
                agendamento_id=agd.id, produto_id=prod_id, quantidade=qtd
            )
        )

    total_servicos_val = sum(s.preco for s in agd.servicos)
    total_geral = total_servicos_val + total_produtos_val

    agd.pago = True
    agd.is_confirmed = True
    await db.commit()
    await db.refresh(agd)

    return {
        "agendamento": agd,
        "total_geral": total_geral,
        "total_servicos": total_servicos_val,
        "total_produtos": total_produtos_val,
    }
