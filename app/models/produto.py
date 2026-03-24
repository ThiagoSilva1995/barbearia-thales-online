from sqlalchemy import Column, Integer, String, Numeric, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

# Tabela Associativa COM QUANTIDADE
agendamento_produto = Table(
    "agendamento_produto",
    Base.metadata,
    Column("agendamento_id", Integer, ForeignKey("agendamentos.id"), primary_key=True),
    Column("produto_id", Integer, ForeignKey("produtos.id"), primary_key=True),
    Column("quantidade", Integer, nullable=False, default=1),  # NOVO CAMPO ESSENCIAL
)


class Produto(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    preco = Column(Numeric(10, 2), nullable=False)
    estoque = Column(Integer, default=0, nullable=False)

    agendamentos = relationship(
        "Agendamento", secondary=agendamento_produto, back_populates="produtos"
    )
