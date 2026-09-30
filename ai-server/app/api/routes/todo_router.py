from fastapi import APIRouter, Depends, HTTPException
from app.lib.alchemy_db import get_db
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.todo import TodoCreate, TodoRead, TodoUpdate
from app.models.todo import Todo
from sqlalchemy import select

todo = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]

@todo.post('/create-todo/', response_model=TodoRead)
async def set_todos(input:TodoCreate, db:DB):
    item = Todo(**input.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    # print(dict(item))
    return item

@todo.get('/get-todos/', response_model=list[TodoRead])
async def get_todos(db:DB):
    result = await db.scalars(select(Todo).order_by(Todo.id))
    items = result.all()
    return items

@todo.patch('/update-todo/{todo_id}', response_model=TodoRead)
async def update_todo(todo_id:int, payload:TodoUpdate, db:DB):
    item = await db.get(Todo, todo_id)
    if item is None:
        raise HTTPException(status_code=404, detail="no item found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item

@todo.delete('/delete-todo/{todo_id}', response_model=bool)
async def delete_todo(todo_id:int, db:DB):
    item = await db.get(Todo, todo_id)
    if item is None:
        raise HTTPException(status_code=404, detail="no item found")

    await db.delete(item)
    await db.commit()
    return True

