from pydantic import BaseModel, Field
from datetime import date, time
from typing import List, Optional


class AgendamentoBase(BaseModel):
    cliente_id: int
    barbeiro_id: int
    data: date
    hora: time
    servico_ids: List[int] = []
    produto_ids: List[int] = []


class AgendamentoCreate(AgendamentoBase):
    pass


class AgendamentoResponse(AgendamentoBase):
    id: int
    pago: bool
    is_confirmed: bool

    class Config:
        from_attributes = True
