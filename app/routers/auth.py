from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import os
from app.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Credenciais (Idealmente viriam do .env)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
RECEPCAO_PASSWORD = os.getenv("RECEPCAO_PASSWORD", "recepcao123")


@router.get("/")
async def root(request: Request):
    """Redireciona a página inicial para a Home."""
    return RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/home", response_class=HTMLResponse)
async def home_simplificada(request: Request):
    # CORREÇÃO: Verifica se está logado antes de mostrar a home
    is_logged = request.session.get("is_logged", False)

    if not is_logged:
        # Se não estiver logado, manda para o login
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Se estiver logado, mostra a home com as informações da sessão
    user_role = request.session.get("user_role", "recepcao")
    user_name = request.session.get("user_name", "Usuário")

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "is_logged": is_logged,
            "user_role": user_role,
            "user_name": user_name,
        },
    )


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    erro = request.query_params.get("erro")
    return templates.TemplateResponse("login.html", {"request": request, "erro": erro})


@router.post("/login")
async def login_action(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    senha = form_data.get("senha")

    # Verifica qual senha foi digitada para definir o cargo (role)
    if senha == ADMIN_PASSWORD:
        request.session["is_logged"] = True
        request.session["user_role"] = "admin"
        request.session["user_name"] = "Administrador"
        # Redireciona para a Agenda, que é o ponto central
        return RedirectResponse(
            url="/agendamentos", status_code=status.HTTP_303_SEE_OTHER
        )

    elif senha == RECEPCAO_PASSWORD:
        request.session["is_logged"] = True
        request.session["user_role"] = "recepcao"
        request.session["user_name"] = "Recepção"
        return RedirectResponse(
            url="/agendamentos", status_code=status.HTTP_303_SEE_OTHER
        )

    else:
        return RedirectResponse(
            url="/login?erro=Senha+incorreta+ou+perfil+não+reconhecido",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/home", status_code=status.HTTP_303_SEE_OTHER)
