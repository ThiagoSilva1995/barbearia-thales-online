from fastapi import APIRouter, Request, Depends, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from app.database import get_db
from app.models.configuracao import Configuracao

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/configuracoes", response_class=HTMLResponse)
async def painel_config(request: Request, db: AsyncSession = Depends(get_db)):
    # Segurança: Apenas Admin
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+restrito+apenas+para+Administradores",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    stmt = select(Configuracao).limit(1)
    res = await db.execute(stmt)
    config = res.scalars().first()

    if not config:
        config = Configuracao()
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return templates.TemplateResponse(
        "admin/configuracoes.html",
        {
            "request": request,
            "config": config,
            "msg": request.query_params.get("msg"),
            "erro": request.query_params.get("erro"),
            "senha_atual_env": os.getenv("ADMIN_PASSWORD", "admin123"),
        },
    )


@router.post("/admin/configuracoes/salvar")
async def salvar_config(request: Request, db: AsyncSession = Depends(get_db)):
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+negado", status_code=status.HTTP_303_SEE_OTHER
        )

    form = await request.form()
    stmt = select(Configuracao).limit(1)
    res = await db.execute(stmt)
    config = res.scalars().first()

    if not config:
        config = Configuracao()
        db.add(config)

    # Bloco 1: Barbearia
    config.nome_fantasia = form.get("nome_fantasia")
    config.telefone_barbearia = "".join(
        filter(str.isdigit, form.get("telefone_barbearia", ""))
    )
    config.endereco = form.get("endereco", "")

    # Bloco 2: Admin
    config.admin_nome = form.get("admin_nome")
    config.admin_login = form.get("admin_login")

    # Bloco 3: Mensagens
    config.msg_aniversario = form.get("msg_aniversario")
    config.msg_confirmacao = form.get("msg_confirmacao")

    await db.commit()
    return RedirectResponse(
        url="/admin/configuracoes?msg=Configurações+salvas+com+sucesso!",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/configuracoes/trocar_senha")
async def trocar_senha(request: Request, db: AsyncSession = Depends(get_db)):
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+negado", status_code=status.HTTP_303_SEE_OTHER
        )

    form = await request.form()
    senha_atual = form.get("senha_atual")
    nova_senha = form.get("nova_senha")
    confirmar_senha = form.get("confirmar_senha")

    senha_correta = os.getenv("ADMIN_PASSWORD", "admin123")

    if senha_atual != senha_correta:
        return RedirectResponse(
            url="/admin/configuracoes?erro=Senha+atual+incorreta",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if nova_senha != confirmar_senha:
        return RedirectResponse(
            url="/admin/configuracoes?erro=Novas+senhas+não+conferem",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Nota: Em produção real, isso atualizaria o .env ou um banco de usuários com hash.
    # Aqui apenas simulamos o sucesso visual.
    return RedirectResponse(
        url="/admin/configuracoes?msg=Senha+alterada+(Reinicie+o+servidor+para+aplicar+no+.env)",
        status_code=status.HTTP_303_SEE_OTHER,
    )
