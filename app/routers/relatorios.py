from fastapi import APIRouter, Request, Depends, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date
import pytz
from sqlalchemy import select, func, distinct

from app.database import get_db
from app.models import Cliente, Agendamento, Servico, Produto, Barbeiro
from app.models.servico import agendamento_servico
from app.models.produto import agendamento_produto

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
tz_br = pytz.timezone("America/Sao_Paulo")


@router.get("/estatisticas", response_class=HTMLResponse)
async def estatisticas(
    request: Request,
    db: AsyncSession = Depends(get_db),
    inicio: str = Query(None),
    fim: str = Query(None),
):
    # Segurança: Apenas Admin pode ver relatórios financeiros detalhados
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+restrito+apenas+para+Administradores",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    hoje = datetime.now(tz_br).date()

    # Datas base para cálculos automáticos
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1)
    inicio_ano = hoje.replace(month=1, day=1)

    # Lógica de Seleção de Período
    periodo_atual = "mes"
    data_ini = inicio_mes
    data_fim = hoje

    if inicio and fim:
        try:
            data_ini = datetime.strptime(inicio, "%Y-%m-%d").date()
            data_fim = datetime.strptime(fim, "%Y-%m-%d").date()
            periodo_atual = "personalizado"
        except ValueError:
            pass
    else:
        tipo = request.query_params.get("tipo", "mes")
        if tipo == "hoje":
            data_ini = hoje
            data_fim = hoje
            periodo_atual = "hoje"
        elif tipo == "semana":
            data_ini = inicio_semana
            data_fim = hoje
            periodo_atual = "semana"
        elif tipo == "ano":
            data_ini = inicio_ano
            data_fim = hoje
            periodo_atual = "ano"

    # Função auxiliar para calcular receita GERAL (Cortes + Produtos * Qtd)
    async def calcular_receita_periodo(d_ini, d_fim):
        try:
            # Cortes
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
                    Agendamento.data >= d_ini,
                    Agendamento.data <= d_fim,
                )
            )
            v_c = float((await db.execute(stmt_cortes)).scalar() or 0.0)

            # Produtos (Preço * Quantidade)
            stmt_prod = (
                select(func.sum(Produto.preco * agendamento_produto.c.quantidade))
                .select_from(Agendamento)
                .join(
                    agendamento_produto,
                    Agendamento.id == agendamento_produto.c.agendamento_id,
                )
                .join(Produto, agendamento_produto.c.produto_id == Produto.id)
                .where(
                    Agendamento.pago == True,
                    Agendamento.data >= d_ini,
                    Agendamento.data <= d_fim,
                )
            )
            v_p = float((await db.execute(stmt_prod)).scalar() or 0.0)

            return v_c, v_p, v_c + v_p
        except Exception as e:
            print(f"Erro stats: {e}")
            return 0.0, 0.0, 0.0

    # 1. Totais Gerais do Período Selecionado (Cards Superiores)
    cortes, prods, total_geral = await calcular_receita_periodo(data_ini, data_fim)

    # Contagem de atendimentos
    stmt_count = select(func.count(distinct(Agendamento.id))).where(
        Agendamento.pago == True,
        Agendamento.data >= data_ini,
        Agendamento.data <= data_fim,
    )
    qtd_atendimentos = (await db.execute(stmt_count)).scalar() or 0

    # 2. Totais Fixos (Semana e Mês Atuais) para visão geral
    cortes_sem, prods_sem, total_sem = await calcular_receita_periodo(
        inicio_semana, hoje
    )
    cortes_mes, prods_mes, total_mes = await calcular_receita_periodo(inicio_mes, hoje)

    # 3. Desempenho por Barbeiro (APENAS CORTES/SERVIÇOS)
    # Query para Semana (Somente Serviços)
    stmt_barb_sem = (
        select(Barbeiro.nome, func.coalesce(func.sum(Servico.preco), 0).label("total"))
        .select_from(Barbeiro)
        .outerjoin(
            Agendamento,
            (Agendamento.barbeiro_id == Barbeiro.id)
            & (Agendamento.pago == True)
            & (Agendamento.data >= inicio_semana)
            & (Agendamento.data <= hoje),
        )
        .outerjoin(
            agendamento_servico, Agendamento.id == agendamento_servico.c.agendamento_id
        )
        .outerjoin(Servico, agendamento_servico.c.servico_id == Servico.id)
        .group_by(Barbeiro.id, Barbeiro.nome)
        .order_by(func.sum(Servico.preco).desc())
    )
    res_barb_sem = await db.execute(stmt_barb_sem)
    dados_semana = res_barb_sem.fetchall()

    # Query para Mês (Somente Serviços)
    stmt_barb_mes = (
        select(Barbeiro.nome, func.coalesce(func.sum(Servico.preco), 0).label("total"))
        .select_from(Barbeiro)
        .outerjoin(
            Agendamento,
            (Agendamento.barbeiro_id == Barbeiro.id)
            & (Agendamento.pago == True)
            & (Agendamento.data >= inicio_mes)
            & (Agendamento.data <= hoje),
        )
        .outerjoin(
            agendamento_servico, Agendamento.id == agendamento_servico.c.agendamento_id
        )
        .outerjoin(Servico, agendamento_servico.c.servico_id == Servico.id)
        .group_by(Barbeiro.id, Barbeiro.nome)
        .order_by(func.sum(Servico.preco).desc())
    )
    res_barb_mes = await db.execute(stmt_barb_mes)
    dados_mes = res_barb_mes.fetchall()

    # Unir dados em um dicionário fácil para o template
    desempenho_barbeiros = {}
    for nome, val in dados_semana:
        desempenho_barbeiros[nome] = {"semana": float(val), "mes": 0.0}

    for nome, val in dados_mes:
        if nome in desempenho_barbeiros:
            desempenho_barbeiros[nome]["mes"] = float(val)
        else:
            desempenho_barbeiros[nome] = {"semana": 0.0, "mes": float(val)}

    return templates.TemplateResponse(
        "estatisticas.html",
        {
            "request": request,
            "hoje": hoje,
            "inicio_semana": inicio_semana,
            "inicio_mes": inicio_mes,
            "inicio_ano": inicio_ano,
            # Totais do Período Selecionado
            "periodo_atual": periodo_atual,
            "data_ini_display": data_ini.strftime("%d/%m/%Y"),
            "data_fim_display": data_fim.strftime("%d/%m/%Y"),
            "cortes_periodo": cortes,
            "prods_periodo": prods,
            "total_periodo": total_geral,
            "qtd_atendimentos": qtd_atendimentos,
            # Totais Fixos (Visão Geral)
            "total_semana": total_sem,
            "total_mes": total_mes,
            # Tabela de Barbeiros (Apenas Cortes)
            "desempenho_barbeiros": desempenho_barbeiros,
        },
    )
