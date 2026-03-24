import traceback

from fastapi import APIRouter, Request, Depends, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
from decimal import Decimal
import pytz
import os

from app.database import get_db
from app.schemas.agendamento import AgendamentoCreate
from app.models import Cliente, Barbeiro, Servico, Produto, Agendamento
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.servico import agendamento_servico
from app.models.produto import agendamento_produto
from sqlalchemy import func

# Services
from app.services.agendamento_service import (
    criar_agendamento,
    remover_agendamento,
    confirmar_pagamento_e_baixar_estoque,
)
from app.services import admin_service

# ==========================================================
# CONFIGURAÇÕES GLOBAIS
# ==========================================================
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
tz_br = pytz.timezone("America/Sao_Paulo")

# Senha do Administrador (Mude aqui se quiser)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# ==========================================================
# ROTAS DE AUTENTICAÇÃO E HOME (NOVAS)
# ==========================================================


@router.get("/home", response_class=HTMLResponse)
async def home_simplificada(request: Request):
    """Tela inicial pública com apenas Agenda, Novo Agendamento e Clientes."""
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "is_admin": request.session.get("is_admin", False)},
    )


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, erro: str = None):
    """Tela de login para administradores."""
    return templates.TemplateResponse("login.html", {"request": request, "erro": erro})


@router.post("/login")
async def login_action(request: Request, db: AsyncSession = Depends(get_db)):
    """Processa o login."""
    form_data = await request.form()
    senha_digitada = form_data.get("senha")

    if senha_digitada == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse(
            url="/agendamentos", status_code=status.HTTP_303_SEE_OTHER
        )
    else:
        return RedirectResponse(
            url="/login?erro=Senha+incorreta", status_code=status.HTTP_303_SEE_OTHER
        )


@router.get("/logout")
async def logout(request: Request):
    """Realiza o logout."""
    request.session.clear()
    return RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)


# ==========================================================
# AGENDAMENTOS (LISTAR)
# ==========================================================
@router.get("/agendamentos", response_class=HTMLResponse)
async def listar_agendamentos(request: Request, db: AsyncSession = Depends(get_db)):
    hoje = datetime.now(tz_br).date()
    data_filter_param = request.query_params.get("data")
    barbeiro_filter = request.query_params.get("barbeiro")

    if not data_filter_param:
        data_obj = hoje
        data_filter_str = str(hoje)
    else:
        try:
            data_obj = datetime.strptime(data_filter_param, "%Y-%m-%d").date()
            data_filter_str = data_filter_param
        except ValueError:
            data_obj = hoje
            data_filter_str = str(hoje)

    query = (
        select(Agendamento)
        .options(
            selectinload(Agendamento.cliente),
            selectinload(Agendamento.barbeiro),
            selectinload(Agendamento.servicos),
        )
        .where(Agendamento.data == data_obj)
        .order_by(Agendamento.data, Agendamento.hora)
    )

    if barbeiro_filter:
        try:
            query = query.where(Agendamento.barbeiro_id == int(barbeiro_filter))
        except ValueError:
            pass

    result = await db.execute(query)
    agendamentos = result.scalars().all()

    for agd in agendamentos:
        agd.hora_str = agd.hora.strftime("%H:%M")
        agd.data_str = agd.data.strftime("%d/%m")

    barbeiros_res = await db.execute(select(Barbeiro).order_by(Barbeiro.nome))

    aniversariantes = []
    if data_obj == hoje:
        clientes_res = await db.execute(select(Cliente))
        for c in clientes_res.scalars().all():
            if (
                c.data_nascimento.month == hoje.month
                and c.data_nascimento.day == hoje.day
                and not c.parabens_enviado
            ):
                aniversariantes.append(c)

    return templates.TemplateResponse(
        "agendamentos/agendamentos.html",
        {
            "request": request,
            "agendamentos": agendamentos,
            "barbeiros": barbeiros_res.scalars().all(),
            "aniversariantes_do_dia": aniversariantes,
            "data_filter": data_filter_str,
            "barbeiro_selecionado": int(barbeiro_filter) if barbeiro_filter else None,
            "eh_hoje": data_obj == hoje,
        },
    )


# ==========================================================
# MARCAR HORÁRIO (GET)
# ==========================================================
@router.get("/marcar-horario", response_class=HTMLResponse)
async def marcar_horario_form(request: Request, db: AsyncSession = Depends(get_db)):
    horarios = []
    inicio = datetime.strptime("08:00", "%H:%M")
    fim = datetime.strptime("19:00", "%H:%M")
    while inicio <= fim:
        horarios.append(inicio.strftime("%H:%M"))
        inicio += timedelta(minutes=30)

    clientes_res = await db.execute(select(Cliente).order_by(Cliente.nome))
    # Nota: Se quiser esconder a seleção de barbeiro, não precisa buscar essa lista aqui
    barbeiros_res = await db.execute(select(Barbeiro).order_by(Barbeiro.nome))
    servicos_res = await db.execute(select(Servico).order_by(Servico.nome))
    hoje = datetime.now(tz_br).date()

    return templates.TemplateResponse(
        "marcar_horario.html",
        {
            "request": request,
            "horarios_disponiveis": horarios,
            "clientes": clientes_res.scalars().all(),
            "barbeiros": barbeiros_res.scalars().all(),
            "servicos": servicos_res.scalars().all(),
            "data_inicial": hoje.strftime("%Y-%m-%d"),
            "erro": None,
        },
    )


# ==========================================================
# MARCAR HORÁRIO (POST)
# ==========================================================
@router.post("/marcar-horario")
async def marcar_horario_action(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        servico_ids = [int(x) for x in form_data.getlist("servico")]
        if not servico_ids:
            raise ValueError("Selecione pelo menos um serviço.")

        dados = AgendamentoCreate(
            cliente_id=int(form_data["cliente"]),
            barbeiro_id=int(form_data["barbeiro"]),
            data=datetime.strptime(form_data["data"], "%Y-%m-%d").date(),
            hora=datetime.strptime(form_data["hora"], "%H:%M").time(),
            servico_ids=servico_ids,
        )
        await criar_agendamento(db, dados)
        return RedirectResponse(
            url="/agendamentos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/marcar-horario?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url="/marcar-horario?erro=Erro+interno",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# ==========================================================
# REMOVER AGENDAMENTO
# ==========================================================
@router.get("/remover-agendamento/{agendamento_id}")
async def remover_agendamento_route(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    if await remover_agendamento(db, agendamento_id):
        return RedirectResponse(
            url="/agendamentos?msg=removido", status_code=status.HTTP_303_SEE_OTHER
        )
    return RedirectResponse(
        url="/agendamentos?erro=Não+encontrado", status_code=status.HTTP_303_SEE_OTHER
    )


# ==========================================================
# CONFIRMAR PAGAMENTO (GET)
# ==========================================================
@router.get("/confirmar-pagamento/{agendamento_id}", response_class=HTMLResponse)
async def confirmar_pagamento_form(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
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

    res = await db.execute(stmt)
    agd = res.scalars().first()

    if not agd:
        return RedirectResponse(
            url="/agendamentos?erro=Agendamento+não+encontrado",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if agd.pago:
        return RedirectResponse(
            url="/agendamentos?erro=Este+agendamento+já+foi+pago",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    servicos_res = await db.execute(select(Servico).order_by(Servico.nome))
    produtos_res = await db.execute(
        select(Produto).where(Produto.estoque > 0).order_by(Produto.nome)
    )

    servicos = servicos_res.scalars().all()
    produtos = produtos_res.scalars().all()

    valor_inicial_cortes = sum(float(s.preco) for s in agd.servicos)

    return templates.TemplateResponse(
        "agendamentos/confirmar_pagamento.html",
        {
            "request": request,
            "agendamento": agd,
            "servicos": servicos,
            "produtos": produtos,
            "valor_inicial_cortes": f"{valor_inicial_cortes:.2f}",
        },
    )


# ==========================================================
# CONFIRMAR PAGAMENTO (POST)
# ==========================================================
@router.post("/confirmar-pagamento/{agendamento_id}")
async def confirmar_pagamento_action(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    form_data = await request.form()
    try:
        servico_ids = [int(x) for x in form_data.getlist("servico")]
        produtos_qtd = {}
        p_ids = form_data.getlist("produto_id")
        p_qtds = form_data.getlist("quantidade")
        for pid, qtd in zip(p_ids, p_qtds):
            if int(qtd) > 0:
                produtos_qtd[int(pid)] = int(qtd)

        resultado = await confirmar_pagamento_e_baixar_estoque(
            db, agendamento_id, servico_ids, produtos_qtd
        )
        msg = f"Pagamento confirmado! Total: R$ {resultado['total_geral']:.2f}"
        return RedirectResponse(
            url=f"/agendamentos?msg={msg}", status_code=status.HTTP_303_SEE_OTHER
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/confirmar-pagamento/{agendamento_id}?erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        print(f"Erro crítico: {e}")
        return RedirectResponse(
            url=f"/confirmar-pagamento/{agendamento_id}?erro=Erro+interno",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# ==========================================================
# CADASTROS (CLIENTES)
# ==========================================================
@router.get("/cadastrar-cliente", response_class=HTMLResponse)
async def cadastrar_cliente_form(request: Request, erro: str = None):
    return templates.TemplateResponse(
        "clientes/cadastrar_cliente.html", {"request": request, "erro": erro}
    )


@router.post("/cadastrar-cliente")
async def cadastrar_cliente_action(
    request: Request, db: AsyncSession = Depends(get_db)
):
    form_data = await request.form()
    try:
        await admin_service.criar_cliente(
            db,
            form_data["nome"],
            form_data["telefone"],
            datetime.strptime(form_data["data_nascimento"], "%Y-%m-%d").date(),
        )
        return RedirectResponse(
            url="/cadastrar-cliente?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/cadastrar-cliente?erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# ==========================================================
# CADASTRO DE SERVIÇOS (LISTAR E CRIAR)
# ==========================================================
@router.get("/servicos", response_class=HTMLResponse)
async def listar_servicos(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Servico).order_by(Servico.nome))
    servicos = result.scalars().all()
    return templates.TemplateResponse(
        "administrador/servicos.html", {"request": request, "servicos": servicos}
    )


@router.post("/servicos")
async def criar_servico(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        nome = form_data["nome"]
        preco = Decimal(form_data["preco"].replace(",", "."))

        novo_servico = Servico(nome=nome, preco=preco)
        db.add(novo_servico)
        await db.commit()
        return RedirectResponse(
            url="/servicos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/servicos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# ==========================================================
# CADASTRO DE PRODUTOS (LISTAR E CRIAR)
# ==========================================================
@router.get("/produtos", response_class=HTMLResponse)
async def listar_produtos(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Produto).order_by(Produto.nome))
    produtos = result.scalars().all()
    return templates.TemplateResponse(
        "administrador/produtos.html", {"request": request, "produtos": produtos}
    )


@router.post("/produtos")
async def criar_produto(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        nome = form_data["nome"]
        preco = Decimal(form_data["preco"].replace(",", "."))
        estoque = int(form_data["estoque"])

        novo_produto = Produto(nome=nome, preco=preco, estoque=estoque)
        db.add(novo_produto)
        await db.commit()
        return RedirectResponse(
            url="/produtos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/produtos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# ==========================================================
# CADASTROS (CLIENTES) - ATUALIZADO
# ==========================================================
@router.get("/cadastrar-cliente", response_class=HTMLResponse)
async def cadastrar_cliente_form(request: Request, db: AsyncSession = Depends(get_db)):
    # Busca os últimos 10 clientes para exibir na lista rápida
    result = await db.execute(select(Cliente).order_by(Cliente.id.desc()).limit(10))
    clientes_recentes = result.scalars().all()

    return templates.TemplateResponse(
        "clientes/cadastrar_cliente.html",
        {
            "request": request,
            "erro": request.query_params.get("erro"),
            "clientes_recentes": clientes_recentes,  # Passa a lista para o template
        },
    )


@router.post("/cadastrar-cliente")
async def cadastrar_cliente_action(
    request: Request, db: AsyncSession = Depends(get_db)
):
    form_data = await request.form()
    try:
        # Chama o service que faz a formatação do telefone e salva
        await admin_service.criar_cliente(
            db,
            form_data["nome"],
            form_data["telefone"],
            datetime.strptime(form_data["data_nascimento"], "%Y-%m-%d").date(),
        )
        return RedirectResponse(
            url="/cadastrar-cliente?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        # Em caso de erro, retorna com a mensagem
        return RedirectResponse(
            url=f"/cadastrar-cliente?erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/produtos")
async def criar_produto(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        nome = form_data["nome"]
        preco = Decimal(form_data["preco"].replace(",", "."))
        estoque = int(form_data["estoque"])

        novo_produto = Produto(nome=nome, preco=preco, estoque=estoque)
        db.add(novo_produto)
        await db.commit()
        return RedirectResponse(
            url="/produtos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/produtos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# ==========================================================
# EXCLUIR PRODUTO (NOVA ROTA)
# ==========================================================
@router.get("/excluir-produto/{produto_id}")
async def excluir_produto(
    produto_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Produto).where(Produto.id == produto_id)
        result = await db.execute(stmt)
        produto = result.scalars().first()

        if produto:
            # Verifica se há estoque (opcional, mas bom pra evitar exclusão acidental de itens em uso)
            # Se quiser permitir exclusão mesmo com histórico, basta deletar direto.
            await db.delete(produto)
            await db.commit()
            return RedirectResponse(
                url="/produtos?msg=excluido", status_code=status.HTTP_303_SEE_OTHER
            )
        else:
            return RedirectResponse(
                url="/produtos?erro=Produto+não+encontrado",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    except Exception as e:
        # Pode falhar se houver chave estrangeira (ex: histórico de vendas vinculado)
        return RedirectResponse(
            url=f"/produtos?erro=Não+foi+possível+excluir:+{str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/servicos")
async def criar_servico(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        nome = form_data["nome"]
        preco = Decimal(form_data["preco"].replace(",", "."))

        novo_servico = Servico(nome=nome, preco=preco)
        db.add(novo_servico)
        await db.commit()
        return RedirectResponse(
            url="/servicos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/servicos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# ==========================================================
# EXCLUIR SERVIÇO (NOVA ROTA)
# ==========================================================
@router.get("/excluir-servico/{servico_id}")
async def excluir_servico(
    servico_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Servico).where(Servico.id == servico_id)
        result = await db.execute(stmt)
        servico = result.scalars().first()

        if servico:
            # Tenta excluir. Se houver agendamentos vinculados, o banco pode bloquear (FK Constraint).
            # Nesse caso, a exceção abaixo será capturada e avisará o usuário.
            await db.delete(servico)
            await db.commit()
            return RedirectResponse(
                url="/servicos?msg=excluido", status_code=status.HTTP_303_SEE_OTHER
            )
        else:
            return RedirectResponse(
                url="/servicos?erro=Serviço+não+encontrado",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    except Exception as e:
        # Captura erro de chave estrangeira se o serviço já foi usado em agendamentos
        error_msg = str(e)
        if "foreign key constraint" in error_msg.lower():
            return RedirectResponse(
                url="/servicos?erro=Não+foi+possível+excluir.+Este+serviço+já+foi+utilizado+em+agendamentos.",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url=f"/servicos?erro=Erro+ao+excluir:+{error_msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/estatisticas", response_class=HTMLResponse)
async def estatisticas(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Segurança
    if not request.session.get("is_admin"):
        return RedirectResponse(
            url="/login?erro=Acesso+restrito", status_code=status.HTTP_303_SEE_OTHER
        )

    # 2. Datas Base
    hoje = datetime.now(tz_br).date()
    inicio_mes = hoje.replace(day=1)
    dia_semana = hoje.weekday()
    inicio_semana = hoje - timedelta(days=dia_semana)

    print(f"📅 Calculando estatísticas para hoje: {hoje}")

    # 3. Função Auxiliar para Somar Receitas (Cortes e Produtos)
    async def calcular_receita(data_ini, data_fim):
        try:
            # Soma Cortes
            stmt_cortes = (
                select(func.sum(Servico.preco))
                .select_from(Agendamento)
                .join(
                    agendamento_servico,
                    Agendamento.id == agendamento_servico.c.agendamento_id,
                )
                .join(Servico, agendamento_servico.c.servico_id == Servico.id)
                .where(
                    Agendamento.pago == True,
                    Agendamento.data >= data_ini,
                    Agendamento.data <= data_fim,
                )
            )

            res_cortes = await db.execute(stmt_cortes)
            total_cortes = float(res_cortes.scalar() or 0.0)

            # Soma Produtos
            stmt_produtos = (
                select(func.sum(Produto.preco))
                .select_from(Agendamento)
                .join(
                    agendamento_produto,
                    Agendamento.id == agendamento_produto.c.agendamento_id,
                )
                .join(Produto, agendamento_produto.c.produto_id == Produto.id)
                .where(
                    Agendamento.pago == True,
                    Agendamento.data >= data_ini,
                    Agendamento.data <= data_fim,
                )
            )

            res_produtos = await db.execute(stmt_produtos)
            total_produtos = float(res_produtos.scalar() or 0.0)

            return total_cortes, total_produtos, total_cortes + total_produtos
        except Exception as e:
            print(f"Erro ao calcular receita: {e}")
            return 0.0, 0.0, 0.0

    # 4. Calcular Valores Reais
    cortes_dia, prod_dia, total_dia = await calcular_receita(hoje, hoje)
    cortes_sem, prod_sem, total_sem = await calcular_receita(inicio_semana, hoje)
    cortes_mes, prod_mes, total_mes = await calcular_receita(inicio_mes, hoje)

    print(f"💰 Resultados: Dia={total_dia}, Sem={total_sem}, Mês={total_mes}")

    # 5. Contar Atendimentos da Semana
    stmt_count = select(func.count(Agendamento.id)).where(
        Agendamento.pago == True,
        Agendamento.data >= inicio_semana,
        Agendamento.data <= hoje,
    )
    res_count = await db.execute(stmt_count)
    qtd_atendimentos = res_count.scalar() or 0
    print(f"🔢 Atendimentos na semana: {qtd_atendimentos}")

    # 6. Buscar Top Clientes do Mês
    stmt_top = (
        select(Cliente.nome, func.count(Agendamento.id).label("qtd"))
        .join(Agendamento, Agendamento.cliente_id == Cliente.id)
        .where(
            Agendamento.pago == True,
            Agendamento.data >= inicio_mes,
            Agendamento.data <= hoje,
        )
        .group_by(Cliente.id, Cliente.nome)
        .order_by(func.count(Agendamento.id).desc())
        .limit(5)
    )

    res_top = await db.execute(stmt_top)
    top_clientes = res_top.fetchall()
    print(f"🏆 Top Clientes: {top_clientes}")

    # 7. Enviar TUDO para o Template
    return templates.TemplateResponse(
        "estatisticas.html",
        {
            "request": request,
            "hoje": hoje,
            "inicio_mes": inicio_mes,
            # Dados do Dia
            "cortes_dia": cortes_dia,
            "prod_dia": prod_dia,
            "total_dia": total_dia,
            # Dados da Semana
            "cortes_sem": cortes_sem,
            "prod_sem": prod_sem,
            "total_sem": total_sem,
            "qtd_atendimentos_sem": qtd_atendimentos,
            # Dados do Mês
            "cortes_mes": cortes_mes,
            "prod_mes": prod_mes,
            "total_mes": total_mes,
            # Listas
            "top_clientes": top_clientes,
        },
    )
