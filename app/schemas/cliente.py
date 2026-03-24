from pydantic import BaseModel, Field
from datetime import date


class ClienteBase(BaseModel):
    nome: str = Field(..., min_length=3)
    telefone: str = Field(..., pattern=r"^\d{10,15}$")
    data_nascimento: date


class ClienteCreate(ClienteBase):
    pass


class ClienteResponse(ClienteBase):
    id: int
    parabens_enviado: bool

    class Config:
        from_attributes = True
