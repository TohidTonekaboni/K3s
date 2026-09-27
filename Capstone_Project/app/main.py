from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="k3s-capstone-app", version="0.1.0")


class Item(BaseModel):
    name: str


class StoredItem(Item):
    id: int


_items: list[StoredItem] = []
_next_id = 1


@app.get("/")
def root():
    return {"name": app.title, "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items")
def list_items():
    return _items


@app.post("/items", status_code=201)
def create_item(item: Item):
    global _next_id
    stored = StoredItem(id=_next_id, name=item.name)
    _items.append(stored)
    _next_id += 1
    return stored


@app.get("/items/{item_id}")
def get_item(item_id: int):
    for item in _items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")
