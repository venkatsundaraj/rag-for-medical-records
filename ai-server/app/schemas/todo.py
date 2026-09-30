from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TodoBase(BaseModel):
    title:str
class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title:str | None = None
    completed:bool | None = None

class TodoRead(TodoBase):
    model_config = ConfigDict(from_attributes=True)
    id:int
    completed:bool
    created_at:datetime