from sqlalchemy import Column, Integer, String, Numeric, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

agendamento_servico = Table(
    "agendamento_servico",
    Base.metadata,
    Column("agendamento_id", Integer, ForeignKey("agendamentos.id"), primary_key=True),
    Column("servico_id", Integer, ForeignKey("servicos.id"), primary_key=True),
)


class Servico(Base):
    __tablename__ = "servicos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    preco = Column(Numeric(10, 2), nullable=False)
    agendamentos = relationship(
        "Agendamento", secondary=agendamento_servico, back_populates="servicos"
    )
