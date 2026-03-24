from sqlalchemy import Column, Integer, String, Date, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    telefone = Column(String(15), nullable=False)
    data_nascimento = Column(Date, nullable=False)
    parabens_enviado = Column(Boolean, default=False)
    agendamentos = relationship(
        "Agendamento", back_populates="cliente", cascade="all, delete-orphan"
    )
