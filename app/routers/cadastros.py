from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from app.database import get_db
from app.models import Cliente, Barbeiro, Servico, Produto
from app.services import admin_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# --- CLIENTES ---
@router.get("/cadastrar-cliente", response_class=HTMLResponse)
async def cadastrar_cliente_form(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Cliente).order_by(Cliente.id.desc()).limit(10))
    return templates.TemplateResponse(
        "clientes/cadastrar_cliente.html",
        {
            "request": request,
            "erro": request.query_params.get("erro"),
            "clientes_recentes": result.scalars().all(),
        },
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


# --- SERVIÇOS ---
@router.get("/servicos", response_class=HTMLResponse)
async def listar_servicos(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Servico).order_by(Servico.nome))
    return templates.TemplateResponse(
        "administrador/servicos.html",
        {"request": request, "servicos": result.scalars().all()},
    )


@router.post("/servicos")
async def criar_servico(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        db.add(
            Servico(
                nome=form_data["nome"],
                preco=Decimal(form_data["preco"].replace(",", ".")),
            )
        )
        await db.commit()
        return RedirectResponse(
            url="/servicos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/servicos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


@router.get("/excluir-servico/{servico_id}")
async def excluir_servico(
    servico_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Servico).where(Servico.id == servico_id)
        res = await db.execute(stmt)
        servico = res.scalars().first()
        if servico:
            await db.delete(servico)
            await db.commit()
            return RedirectResponse(
                url="/servicos?msg=excluido", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            url="/servicos?erro=Não+encontrado", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        if "foreign key" in str(e).lower():
            return RedirectResponse(
                url="/servicos?erro=Em+uso+em+agendamentos",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url=f"/servicos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# --- PRODUTOS ---
@router.get("/produtos", response_class=HTMLResponse)
async def listar_produtos(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Produto).order_by(Produto.nome))
    return templates.TemplateResponse(
        "administrador/produtos.html",
        {"request": request, "produtos": result.scalars().all()},
    )


@router.post("/produtos")
async def criar_produto(request: Request, db: AsyncSession = Depends(get_db)):
    form_data = await request.form()
    try:
        db.add(
            Produto(
                nome=form_data["nome"],
                preco=Decimal(form_data["preco"].replace(",", ".")),
                estoque=int(form_data["estoque"]),
            )
        )
        await db.commit()
        return RedirectResponse(
            url="/produtos?msg=sucesso", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/produtos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


@router.get("/excluir-produto/{produto_id}")
async def excluir_produto(
    produto_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Produto).where(Produto.id == produto_id)
        res = await db.execute(stmt)
        produto = res.scalars().first()
        if produto:
            await db.delete(produto)
            await db.commit()
            return RedirectResponse(
                url="/produtos?msg=excluido", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            url="/produtos?erro=Não+encontrado", status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/produtos?erro={str(e)}", status_code=status.HTTP_303_SEE_OTHER
        )


# ==========================================================
# GERENCIAR BARBEIROS (CORRIGIDO)
# ==========================================================
@router.get("/cadastrar-barbeiro", response_class=HTMLResponse)
async def listar_barbeiros(request: Request, db: AsyncSession = Depends(get_db)):
    # CORREÇÃO: Verifica user_role em vez de is_admin
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+restrito+apenas+para+Administradores",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    stmt = select(Barbeiro).order_by(Barbeiro.nome)
    res = await db.execute(stmt)
    barbeiros = res.scalars().all()

    return templates.TemplateResponse(
        "admin/barbeiros.html",
        {
            "request": request,
            "barbeiros": barbeiros,
            "msg": request.query_params.get("msg"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.post("/cadastrar-barbeiro/salvar")
async def salvar_barbeiro(request: Request, db: AsyncSession = Depends(get_db)):
    # CORREÇÃO: Verifica user_role
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+negado", status_code=status.HTTP_303_SEE_OTHER
        )

    form = await request.form()
    nome = form.get("nome")
    telefone = "".join(filter(str.isdigit, form.get("telefone", "")))
    id_barbeiro = form.get("id_barbeiro")

    try:
        if id_barbeiro:
            stmt = select(Barbeiro).where(Barbeiro.id == int(id_barbeiro))
            res = await db.execute(stmt)
            barbeiro = res.scalars().first()
            if barbeiro:
                barbeiro.nome = nome
                barbeiro.telefone = telefone
        else:
            novo_barbeiro = Barbeiro(nome=nome, telefone=telefone)
            db.add(novo_barbeiro)

        await db.commit()
        return RedirectResponse(
            url="/cadastrar-barbeiro?msg=Barbeiro+salvo+com+sucesso",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Exception as e:
        await db.rollback()
        return RedirectResponse(
            url=f"/cadastrar-barbeiro?erro={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/remover-barbeiro/{barbeiro_id}")
async def remover_barbeiro(
    barbeiro_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    # CORREÇÃO: Verifica user_role
    if request.session.get("user_role") != "admin":
        return RedirectResponse(
            url="/login?erro=Acesso+negado", status_code=status.HTTP_303_SEE_OTHER
        )

    stmt = select(Barbeiro).where(Barbeiro.id == barbeiro_id)
    res = await db.execute(stmt)
    barbeiro = res.scalars().first()

    if barbeiro:
        await db.delete(barbeiro)
        await db.commit()
        return RedirectResponse(
            url="/cadastrar-barbeiro?msg=Barbeiro+removido",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url="/cadastrar-barbeiro?erro=Não+encontrado",
        status_code=status.HTTP_303_SEE_OTHER,
    )
