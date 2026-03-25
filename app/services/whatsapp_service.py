import urllib.parse
from app.models.cliente import Cliente


def gerar_mensagem_aniversario(
    cliente: Cliente, texto_personalizado: str = None
) -> str:
    primeiro_nome = cliente.nome.split()[0]
    if texto_personalizado:
        mensagem = texto_personalizado.replace("{nome}", primeiro_nome)
    else:
        mensagem = (
            f"🎉 Feliz Aniversário, *{primeiro_nome}*! 🎉\n\n"
            f"A *Barbearia* te deseja um dia incrível!\n\n"
            f"Um grande abraço!\n💈"
        )
    return mensagem


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    tel_limpo = "".join(filter(str.isdigit, telefone))
    if not tel_limpo.startswith("55"):
        tel_limpo = "55" + tel_limpo.lstrip("0")
    msg_codificada = urllib.parse.quote(mensagem)
    # CORREÇÃO: URL limpa sem espaços
    return f"https://wa.me/{tel_limpo}?text={msg_codificada}"


def gerar_mensagem_novo_agendamento(
    cliente_nome, servicos_nomes, data_str, hora_str, barbeiro_nome
):
    lista_servicos = ", ".join(servicos_nomes)
    mensagem = (
        f"💈 *NOVO AGENDAMENTO REALIZADO!* 💈\n\n"
        f"👤 *Cliente:* {cliente_nome}\n"
        f"✂️ *Serviços:* {lista_servicos}\n"
        f"📅 *Data:* {data_str}\n"
        f"⏰ *Horário:* {hora_str}\n"
        f"💇‍♂️ *Barbeiro:* {barbeiro_nome}\n\n"
        f"_Aguardando confirmação._"
    )
    return mensagem


async def enviar_parabens_aniversariantes(
    db, aniversariantes, texto_personalizado=None
):
    resultados = []
    for cliente in aniversariantes:
        msg = gerar_mensagem_aniversario(cliente, texto_personalizado)
        link = gerar_link_whatsapp(cliente.telefone, msg)
        resultados.append({"cliente": cliente, "mensagem": msg, "link": link})
    return resultados


def gerar_mensagem_alteracao_agendamento(
    cliente_nome, data_antiga, hora_antiga, data_nova, hora_nova, servicos_nomes
):
    lista_servicos = ", ".join(servicos_nomes)
    mensagem = (
        f"⚠️ *ALTERAÇÃO DE AGENDAMENTO REALIZADA!* ⚠️\n\n"
        f"👤 *Cliente:* {cliente_nome}\n"
        f"✂️ *Serviços:* {lista_servicos}\n\n"
        f"❌ *HORÁRIO ANTIGO:*\n"
        f"📅 {data_antiga} às ⏰ {hora_antiga}\n\n"
        f"✅ *NOVO HORÁRIO:*\n"
        f"📅 {data_nova} às ⏰ {hora_nova}\n\n"
        f"_Por favor, confirme a disponibilidade._"
    )
    return mensagem


def gerar_mensagem_cancelamento(
    cliente_nome, data_str, hora_str, barbeiro_nome, servicos_nomes
):
    """Gera a mensagem de aviso de cancelamento."""
    lista_servicos = ", ".join(servicos_nomes)

    mensagem = (
        f"❌ *CANCELAMENTO DE AGENDAMENTO* ❌\n\n"
        f"👤 *Cliente:* {cliente_nome}\n"
        f"✂️ *Serviços:* {lista_servicos}\n"
        f"📅 *Data:* {data_str}\n"
        f"⏰ *Horário:* {hora_str}\n"
        f"💇‍♂️ *Barbeiro:* {barbeiro_nome}\n\n"
        f"_O horário foi liberado na agenda._"
    )
    return mensagem
