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
from app.models.configuracao import Configuracao
from app.schemas.agendamento import AgendamentoCreate
from app.services.agendamento_service import (
    criar_agendamento,
    remover_agendamento,
    verificar_disponibilidade,
)
from app.services.whatsapp_service import (
    gerar_mensagem_aniversario,
    gerar_link_whatsapp,
    gerar_mensagem_novo_agendamento,
    gerar_mensagem_alteracao_agendamento,
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
    except ValueError:
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
        hora_str = form_data.get("hora")
        barbeiro_str = form_data.get("barbeiro")
        data_str = form_data.get("data")

        if not servico_ids or not hora_str or not barbeiro_str or not data_str:
            raise ValueError("Preencha todos os campos obrigatórios.")

        # 1. Criar o agendamento no banco
        dados = AgendamentoCreate(
            cliente_id=cliente_id,
            barbeiro_id=int(barbeiro_str),
            data=datetime.strptime(data_str, "%Y-%m-%d").date(),
            hora=datetime.strptime(hora_str, "%H:%M").time(),
            servico_ids=servico_ids,
        )
        await criar_agendamento(db, dados)

        # 2. Preparar dados para o aviso no WhatsApp
        stmt_cliente = select(Cliente).where(Cliente.id == cliente_id)
        cliente = (await db.execute(stmt_cliente)).scalars().first()

        stmt_barbeiro = select(Barbeiro).where(Barbeiro.id == int(barbeiro_str))
        barbeiro = (await db.execute(stmt_barbeiro)).scalars().first()

        stmt_servicos = select(Servico).where(Servico.id.in_(servico_ids))
        servicos = (await db.execute(stmt_servicos)).scalars().all()

        # Buscar telefone da barbearia
        stmt_config = select(Configuracao).limit(1)
        config = (await db.execute(stmt_config)).scalars().first()
        telefone_barbearia = (
            config.telefone_barbearia if config and config.telefone_barbearia else ""
        )

        # 3. Gerar Mensagem e Link
        if telefone_barbearia:
            nomes_servicos = [s.nome for s in servicos]
            data_formatada = datetime.strptime(data_str, "%Y-%m-%d").strftime(
                "%d/%m/%Y"
            )

            msg_aviso = gerar_mensagem_novo_agendamento(
                cliente_nome=cliente.nome,
                servicos_nomes=nomes_servicos,
                data_str=data_formatada,
                hora_str=hora_str,
                barbeiro_nome=barbeiro.nome if barbeiro else "Não definido",
            )

            link_whatsapp_barbearia = gerar_link_whatsapp(telefone_barbearia, msg_aviso)

            # 4. Retornar uma página HTML que salva e depois abre o Zap imediatamente
            html_content = f"""
            <!DOCTYPE html>
            <html lang="pt-br">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Enviando...</title>
                <script>
                    window.location.href = "{link_whatsapp_barbearia}";
                    // Após abrir o zap, redireciona para a lista de agendamentos em 3 segundos
                    setTimeout(function() {{
                        window.location.href = "/cliente/meus-agendamentos?msg=Agendamento+realizado!+Aviso+enviado.";
                    }}, 3000);
                </script>
                <style>
                    body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f3f4f6; text-align: center; }}
                    .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #25D366; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }}
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                </style>
            </head>
            <body>
                <div>
                    <div class="loader" style="margin: 0 auto 20px;"></div>
                    <h2>Agendamento Confirmado! 🚀</h2>
                    <p>Abrindo WhatsApp para enviar o aviso...</p>
                    <p style="font-size: 0.8rem; color: #666; margin-top: 20px;">Se não abrir automaticamente, <a href="{link_whatsapp_barbearia}" target="_blank" style="color: #25D366;">clique aqui</a>.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)

        else:
            # Se não tiver telefone, vai direto para o sucesso
            return RedirectResponse(
                url="/cliente/meus-agendamentos?msg=Agendamento+realizado+com+sucesso!",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    except Exception as e:
        print(f"Erro ao agendar: {e}")
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

    # 1. Buscar dados do agendamento ANTES de cancelar (para montar a mensagem)
    stmt = (
        select(Agendamento)
        .options(selectinload(Agendamento.barbeiro), selectinload(Agendamento.servicos))
        .where(Agendamento.id == agendamento_id, Agendamento.cliente_id == cliente_id)
    )
    res = await db.execute(stmt)
    agd = res.scalars().first()

    if not agd:
        return RedirectResponse(
            url="/cliente/meus-agendamentos?erro=Agendamento+não+encontrado",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if agd.pago:
        return RedirectResponse(
            url="/cliente/meus-agendamentos?erro=Não+é+possível+cancelar+após+pago",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # 2. Preparar dados para a mensagem
    stmt_cliente = select(Cliente).where(Cliente.id == cliente_id)
    cliente = (await db.execute(stmt_cliente)).scalars().first()

    nomes_servicos = [s.nome for s in agd.servicos]
    data_fmt = agd.data.strftime("%d/%m/%Y")
    hora_fmt = agd.hora.strftime("%H:%M")
    nome_barbeiro = agd.barbeiro.nome if agd.barbeiro else "Não definido"

    # 3. Buscar telefone da barbearia
    stmt_config = select(Configuracao).limit(1)
    config = (await db.execute(stmt_config)).scalars().first()
    telefone_barbearia = (
        config.telefone_barbearia if config and config.telefone_barbearia else ""
    )

    # 4. Realizar o Cancelamento no Banco
    await remover_agendamento(db, agendamento_id)

    # 5. Gerar Link do WhatsApp se tiver telefone cadastrado
    if telefone_barbearia:
        from app.services.whatsapp_service import (
            gerar_mensagem_cancelamento,
            gerar_link_whatsapp,
        )

        msg_aviso = gerar_mensagem_cancelamento(
            cliente_nome=cliente.nome,
            data_str=data_fmt,
            hora_str=hora_fmt,
            barbeiro_nome=nome_barbeiro,
            servicos_nomes=nomes_servicos,
        )

        link_whatsapp = gerar_link_whatsapp(telefone_barbearia, msg_aviso)

        # Retorna HTML intermediário para abrir o Zap e depois ir para a lista
        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cancelando...</title>
            <script>
                window.location.href = "{link_whatsapp}";
                setTimeout(function() {{
                    window.location.href = "/cliente/meus-agendamentos?msg=Agendamento+cancelado!+Por+favor,+avise+a+barbearia.";
                }}, 3000);
            </script>
            <style>
                body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f3f4f6; text-align: center; }}
                .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #EF4444; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            </style>
        </head>
        <body>
            <div>
                <div class="loader" style="margin: 0 auto 20px;"></div>
                <h2>Agendamento Cancelado! ❌</h2>
                <p>Abrindo WhatsApp para avisar sobre o cancelamento...</p>
                <p style="font-size: 0.8rem; color: #666; margin-top: 20px;">Se não abrir, <a href="{link_whatsapp}" target="_blank" style="color: #EF4444;">clique aqui</a>.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    # Se não tiver telefone, vai direto para a lista
    return RedirectResponse(
        url="/cliente/meus-agendamentos?msg=Agendamento+cancelado+com+sucesso!",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================
# 4. EDITAR AGENDAMENTO (COM WHATSAPP DE AVISO)
# ==========================================================


@router.get("/cliente/editar/{agendamento_id}", response_class=HTMLResponse)
async def cliente_editar_form(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)

    # Busca o agendamento
    stmt = (
        select(Agendamento)
        .options(selectinload(Agendamento.barbeiro), selectinload(Agendamento.servicos))
        .where(Agendamento.id == agendamento_id, Agendamento.cliente_id == cliente_id)
    )
    res = await db.execute(stmt)
    agd = res.scalars().first()

    if not agd or agd.pago:
        return RedirectResponse(
            url="/cliente/meus-agendamentos?erro=Não+é+possível+editar+este+agendamento",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Prepara dados
    hoje = datetime.now(tz_br).date()
    barbeiros = (
        (await db.execute(select(Barbeiro).order_by(Barbeiro.nome))).scalars().all()
    )
    servicos = (
        (await db.execute(select(Servico).order_by(Servico.nome))).scalars().all()
    )

    # Gera lista de horários sugeridos
    horarios_sugeridos = []
    inicio = datetime.strptime("08:00", "%H:%M")
    fim = datetime.strptime("19:00", "%H:%M")
    while inicio <= fim:
        horarios_sugeridos.append(inicio.strftime("%H:%M"))
        inicio += timedelta(minutes=30)

    servicos_atuais_ids = [s.id for s in agd.servicos]

    return templates.TemplateResponse(
        "cliente/editar_agendamento.html",
        {
            "request": request,
            "agendamento": agd,
            "barbeiros": barbeiros,
            "servicos": servicos,
            "horarios_sugeridos": horarios_sugeridos,
            "servicos_atuais_ids": servicos_atuais_ids,
            "hoje": hoje,
            "erro": request.query_params.get("erro"),
            "cliente_logado": True,
        },
    )


@router.post("/cliente/editar/{agendamento_id}")
async def cliente_editar_action(
    agendamento_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return RedirectResponse(url="/cliente", status_code=status.HTTP_303_SEE_OTHER)

    form_data = await request.form()
    try:
        # 1. Buscar agendamento atual
        stmt = (
            select(Agendamento)
            .options(selectinload(Agendamento.servicos))
            .where(
                Agendamento.id == agendamento_id, Agendamento.cliente_id == cliente_id
            )
        )
        res = await db.execute(stmt)
        agd = res.scalars().first()

        if not agd or agd.pago:
            raise ValueError("Agendamento inválido.")

        # 2. Capturar novos dados
        nova_data_str = form_data.get("data")
        nova_hora_str = form_data.get("hora")
        novo_barbeiro_str = form_data.get("barbeiro")
        novos_servico_ids = [int(x) for x in form_data.getlist("servico")]

        if not all(
            [nova_data_str, nova_hora_str, novo_barbeiro_str, novos_servico_ids]
        ):
            raise ValueError("Preencha todos os campos.")

        nova_data = datetime.strptime(nova_data_str, "%Y-%m-%d").date()
        nova_hora = datetime.strptime(nova_hora_str, "%H:%M").time()
        novo_barbeiro_id = int(novo_barbeiro_str)

        # 3. Verificar disponibilidade do NOVO horário
        ocupado = await verificar_disponibilidade(
            db, novo_barbeiro_id, nova_data, nova_hora, exclude_id=agd.id
        )
        if ocupado:
            raise ValueError("Este novo horário já está ocupado!")

        # 4. Salvar dados ANTIGOS para a mensagem de WhatsApp
        data_antiga_fmt = agd.data.strftime("%d/%m/%Y")
        hora_antiga_fmt = agd.hora.strftime("%H:%M")

        # 5. Atualizar no Banco
        agd.data = nova_data
        agd.hora = nova_hora
        agd.barbeiro_id = novo_barbeiro_id

        agd.servicos.clear()
        stmt_serv = select(Servico).where(Servico.id.in_(novos_servico_ids))
        res_serv = await db.execute(stmt_serv)
        for s in res_serv.scalars().all():
            agd.servicos.append(s)

        await db.commit()

        # 6. Gerar Aviso no WhatsApp da Barbearia
        stmt_config = select(Configuracao).limit(1)
        config = (await db.execute(stmt_config)).scalars().first()
        telefone_barbearia = config.telefone_barbearia if config else ""

        if telefone_barbearia:
            cliente = (
                (await db.execute(select(Cliente).where(Cliente.id == cliente_id)))
                .scalars()
                .first()
            )
            nomes_novos_servicos = [s.nome for s in agd.servicos]
            data_nova_fmt = nova_data.strftime("%d/%m/%Y")

            # Monta a mensagem de alteração
            msg_aviso = (
                f"⚠️ *ALTERAÇÃO DE HORÁRIO*\n\n"
                f"👤 *Cliente:* {cliente.nome}\n"
                f"✂️ *Serviços:* {', '.join(nomes_novos_servicos)}\n\n"
                f"❌ *ANTIGO:* {data_antiga_fmt} às {hora_antiga_fmt}\n"
                f"✅ *NOVO:* {data_nova_fmt} às {nova_hora_str}\n\n"
                f"_Por favor, confirme a mudança._"
            )

            link_whatsapp = gerar_link_whatsapp(telefone_barbearia, msg_aviso)

            # Retorna HTML que abre o Zap automaticamente
            html_content = f"""
            <!DOCTYPE html>
            <html lang="pt-br">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Enviando alteração...</title>
                <script>
                    window.location.href = "{link_whatsapp}";
                    setTimeout(function() {{
                        window.location.href = "/cliente/meus-agendamentos?msg=Horário+alterado!+Envie+a+mensagem+no+WhatsApp.";
                    }}, 3000);
                </script>
                <style>
                    body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f3f4f6; text-align: center; }}
                    .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #F59E0B; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }}
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                </style>
            </head>
            <body>
                <div>
                    <div class="loader" style="margin: 0 auto 20px;"></div>
                    <h2>Agendamento Alterado! 🔄</h2>
                    <p>Abrindo WhatsApp para avisar a barbearia sobre a mudança...</p>
                    <p style="font-size: 0.8rem; color: #666; margin-top: 20px;">Se não abrir, <a href="{link_whatsapp}" target="_blank" style="color: #F59E0B;">clique aqui</a>.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)

        return RedirectResponse(
            url="/cliente/meus-agendamentos?msg=Agendamento+alterado+com+sucesso!",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Exception as e:
        print(f"Erro ao editar: {e}")
        return RedirectResponse(
            url=f"/cliente/editar/{agendamento_id}?erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
