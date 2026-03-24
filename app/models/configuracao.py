from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True, index=True)

    # Dados da Barbearia
    nome_fantasia = Column(String, default="Barbearia do Thales")
    telefone_barbearia = Column(String, default="5573991449063")
    endereco = Column(String, default="Rua Exemplo, 123 - Centro")

    # Dados do Admin
    admin_nome = Column(String, default="Thales")
    admin_login = Column(String, default="admin")

    # Mensagens
    msg_aniversario = Column(
        Text, default="🎉 Feliz Aniversário! Que seu dia seja incrível!"
    )
    msg_confirmacao = Column(
        Text, default="✅ Agendamento confirmado! Te esperamos em breve."
    )
