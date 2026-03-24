from fastapi import APIRouter, Request, Depends, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, date
import pytz
from app.database import get_db
from app.models import Cliente, Barbeiro, Servico, Agendamento
from app.schemas.agendamento import AgendamentoCreate
from app.services.agendamento_service import criar_agendamento, remover_agendamento
from app.services.whatsapp_service import (
    gerar_mensagem_aniversario,
    gerar_link_whatsapp,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
tz_br = pytz.timezone("America/Sao_Paulo")


@router.get("/cliente", response_class=HTMLResponse)
async def area_cliente_acesso(request: Request):
    return templates.TemplateResponse(
        "cliente/acesso.html",
        {"request": request, "erro": None, "cliente_logado": False},
    )


@router.post("/cliente/acessar")
async def cliente_acessar_action(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    telefone = "".join(filter(str.isdigit, form_data.get("telefone", "")))
    if not telefone:
        return RedirectResponse(
            url="/cliente?erro=Digite+o+telefone", status_code=status.HTTP_303_SEE_OTHER
        )

    stmt = select(Cliente).where(Cliente.telefone.like(f"%{telefone[-9:]}"))
    res = await db.execute(stmt)
    cliente = res.scalars().first()

    if cliente:
        request.session["cliente_id"] = cliente.id
        request.session["cliente_nome"] = cliente.nome
        return RedirectResponse(
            url="/cliente/meus-agendamentos", status_code=status.HTTP_303_SEE_OTHER
        )
    else:
        return RedirectResponse(
            url=f"/cliente/cadastro?telefone={telefone}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/cliente/cadastro", response_class=HTMLResponse)
async def area_cliente_cadastro(request: Request, telefone: str = ""):
    return templates.TemplateResponse(
        "cliente/cadastro.html",
        {
            "request": request,
            "telefone": telefone,
            "erro": None,
            "cliente_logado": False,
        },
    )


@router.post("/cliente/cadastrar")
async def cliente_cadastrar_action(
    request: Request, db: AsyncSession = Depends(get_db)
):
    form_data = await request.form()
    try:
        nome = form_data.get("nome")
        telefone = "".join(filter(str.isdigit, form_data.get("telefone", "")))
        data_nasc_str = form_data.get("data_nascimento")
        if not nome or not telefone or not data_nasc_str:
            raise ValueError("Preencha todos os campos.")

        data_nasc = datetime.strptime(data_nasc_str, "%Y-%m-%d").date()
        stmt_check = select(Cliente).where(Cliente.telefone.like(f"%{telefone[-9:]}"))
        if (await db.execute(stmt_check)).scalars().first():
            raise ValueError("Telefone já cadastrado!")

        novo_cliente = Cliente(
            nome=nome.title(),
            telefone=telefone,
            data_nascimento=data_nasc,
            parabens_enviado=False,
        )
        db.add(novo_cliente)
        await db.commit()
        await db.refresh(novo_cliente)

        request.session["cliente_id"] = novo_cliente.id
        request.session["cliente_nome"] = novo_cliente.nome
        return RedirectResponse(
            url="/cliente/meus-agendamentos", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/cliente/cadastro?telefone={form_data.get('telefone', '')}&erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/cliente/sair")
async def cliente_sair(request: Request):
    request.session.pop("cliente_id", None)
    request.session.pop("cliente_nome", None)
    return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/cliente/agendar", response_class=HTMLResponse)
async def area_cliente_agendar(request: Request, db: AsyncSession = Depends(get_db)):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)

    hoje = datetime.now(tz_br).date()
    data_str = request.query_params.get("data", str(hoje))
    barbeiro_id = request.query_params.get("barbeiro")

    try:
        data_selecionada = datetime.strptime(data_str, "%Y-%m-%d").date()
    except:
        data_selecionada = hoje

    cliente_atual = (
        (await db.execute(select(Cliente).where(Cliente.id == cliente_id)))
        .scalars()
        .first()
    )
    barbeiros = (
        (await db.execute(select(Barbeiro).order_by(Barbeiro.nome))).scalars().all()
    )
    servicos = (
        (await db.execute(select(Servico).order_by(Servico.nome))).scalars().all()
    )

    horarios_sugeridos = []
    inicio = datetime.strptime("08:00", "%H:%M")
    fim = datetime.strptime("19:00", "%H:%M")
    while inicio <= fim:
        horarios_sugeridos.append(inicio.strftime("%H:%M"))
        inicio += timedelta(minutes=30)

    stmt_ocupados = select(Agendamento.hora, Agendamento.barbeiro_id).where(
        Agendamento.data == data_selecionada
    )
    if barbeiro_id:
        stmt_ocupados = stmt_ocupados.where(Agendamento.barbeiro_id == int(barbeiro_id))
    ocupados = (await db.execute(stmt_ocupados)).all()

    horarios_livres = []
    for h_str in horarios_sugeridos:
        h_time = datetime.strptime(h_str, "%H:%M").time()
        esta_livre = True
        for occ_hora, occ_barb_id in ocupados:
            if occ_hora == h_time and (
                not barbeiro_id or int(barbeiro_id) == occ_barb_id
            ):
                esta_livre = False
                break
        if esta_livre:
            horarios_livres.append(h_str)

    return templates.TemplateResponse(
        "cliente/agendar.html",
        {
            "request": request,
            "cliente": cliente_atual,
            "barbeiros": barbeiros,
            "servicos": servicos,
            "horarios_livres": horarios_livres,
            "data_selecionada": data_selecionada,
            "barbeiro_selecionado": int(barbeiro_id) if barbeiro_id else None,
            "hoje": hoje,
            "msg": request.query_params.get("msg"),
            "erro": request.query_params.get("erro"),
            "cliente_logado": True,
        },
    )


@router.post("/cliente/agendar/confirmar")
async def cliente_agendar_confirmar(
    request: Request, db: AsyncSession = Depends(get_db)
):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)
    form_data = await request.form()
    try:
        servico_ids = [int(x) for x in form_data.getlist("servico")]
        if not all(
            [
                servico_ids,
                form_data.get("hora"),
                form_data.get("barbeiro"),
                form_data.get("data"),
            ]
        ):
            raise ValueError("Preencha todos os campos.")

        dados = AgendamentoCreate(
            cliente_id=cliente_id,
            barbeiro_id=int(form_data["barbeiro"]),
            data=datetime.strptime(form_data["data"], "%Y-%m-%d").date(),
            hora=datetime.strptime(form_data["hora"], "%H:%M").time(),
            servico_ids=servico_ids,
        )
        await criar_agendamento(db, dados)
        return RedirectResponse(
            url="/cliente/meus-agendamentos?msg=Agendamento+realizado+com+sucesso!",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        print(f"Erro: {e}")
        return RedirectResponse(
            url=f"/cliente/agendar?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


@router.get("/cliente/meus-agendamentos", response_class=HTMLResponse)
async def cliente_meus_agendamentos(
    request: Request, db: AsyncSession = Depends(get_db)
):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)

    cliente = (
        (await db.execute(select(Cliente).where(Cliente.id == cliente_id)))
        .scalars()
        .first()
    )
    stmt_agd = (
        select(Agendamento)
        .options(selectinload(Agendamento.barbeiro), selectinload(Agendamento.servicos))
        .where(Agendamento.cliente_id == cliente_id)
        .order_by(Agendamento.data.desc(), Agendamento.hora.desc())
    )
    agendamentos = (await db.execute(stmt_agd)).scalars().all()

    hoje = datetime.now(tz_br).date()
    hora_atual = datetime.now(tz_br).time()

    return templates.TemplateResponse(
        "cliente/meus_agendamentos.html",
        {
            "request": request,
            "cliente": cliente,
            "agendamentos": agendamentos,
            "hoje": hoje,
            "hora_atual": hora_atual,
            "cliente_logado": True,
        },
    )


@router.get("/cliente/cancelar/{agendamento_id}")
async def cliente_cancelar_agendamento(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)
    stmt = select(Agendamento).where(
        Agendamento.id == agendamento_id, Agendamento.cliente_id == cliente_id
    )
    agd = (await db.execute(stmt)).scalars().first()
    if agd and not agd.pago:
        await remover_agendamento(db, agendamento_id)
        return RedirectResponse(
            url="/cliente/meus-agendamentos?msg=Agendamento+cancelado",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    erro_msg = (
        "Não+é+possível+cancelar+após+pago"
        if agd and agd.pago
        else "Agendamento+não+encontrado"
    )
    return RedirectResponse(
        url=f"/cliente/meus-agendamentos?erro={erro_msg}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
