from pydantic import BaseModel, Field
from decimal import Decimal


class ProdutoBase(BaseModel):
    nome: str
    preco: Decimal
    estoque: int = 0


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoResponse(ProdutoBase):
    id: int

    class Config:
        from_attributes = True
