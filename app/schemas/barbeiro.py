from pydantic import BaseModel, Field


class BarbeiroBase(BaseModel):
    nome: str = Field(..., min_length=3)
    telefone: str = Field(..., pattern=r"^\d{10,15}$")


class BarbeiroCreate(BarbeiroBase):
    pass


class BarbeiroResponse(BarbeiroBase):
    id: int

    class Config:
        from_attributes = True
