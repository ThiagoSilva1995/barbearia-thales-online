from pydantic import BaseModel, Field
from decimal import Decimal


class ServicoBase(BaseModel):
    nome: str
    preco: Decimal


class ServicoCreate(ServicoBase):
    pass


class ServicoResponse(ServicoBase):
    id: int

    class Config:
        from_attributes = True
