import urllib.parse
from app.models.cliente import Cliente


def gerar_mensagem_aniversario(
    cliente: Cliente, texto_personalizado: str = None
) -> str:
    """Gera a mensagem personalizada. Se receber um texto personalizado, usa ele."""

    primeiro_nome = cliente.nome.split()[0]

    # Se tiver texto personalizado (vindo do banco), usa ele. Senão, usa o padrão.
    if texto_personalizado:
        mensagem = texto_personalizado.replace("{nome}", primeiro_nome)
    else:
        mensagem = (
            f"🎉 Feliz Aniversário, *{primeiro_nome}*! 🎉\n\n"
            f"A *Barbearia do Thales* te deseja um dia cheio de alegria!\n\n"
            f'"Que darei eu ao Senhor por todos os benefícios que me tem feito?" (Salmos 116:12)\n\n'
            f"Um grande abraço!\n"
            f"Equipe *Barbearia do Thales* 💈✂️"
        )

    return mensagem


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    tel_limpo = "".join(filter(str.isdigit, telefone))
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + tel_limpo.lstrip("0")

    msg_codificada = urllib.parse.quote(mensagem)
    return f"https://wa.me/{tel_limpo}?text={msg_codificada}"


async def enviar_parabens_aniversariantes(
    db, aniversariantes, texto_personalizado=None
):
    resultados = []
    for cliente in aniversariantes:
        msg = gerar_mensagem_aniversario(cliente, texto_personalizado)
        link = gerar_link_whatsapp(cliente.telefone, msg)
        resultados.append({"cliente": cliente, "mensagem": msg, "link": link})
    return resultados
