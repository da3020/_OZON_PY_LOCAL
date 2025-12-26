from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
from pathlib import Path
from datetime import datetime, timezone

app = FastAPI()

ROOT = Path(__file__).parent
DATA_ITEMS = ROOT / "data" / "items"
DATA_HISTORY = ROOT / "data" / "history"
UI_DIR = ROOT / "ui"

DATA_ITEMS.mkdir(parents=True, exist_ok=True)
DATA_HISTORY.mkdir(parents=True, exist_ok=True)

# -----------------------------
# MODELS
# -----------------------------
class ItemUpdate(BaseModel):
    item_id: str
    status: str

# -----------------------------
# API
# -----------------------------
@app.get("/api/items")
def get_items():
    items = []

    for f in DATA_ITEMS.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fh:
            items.append(json.load(fh))

    return {"items": items}


@app.post("/api/item/update")
def update_item(payload: ItemUpdate):
    item_file = DATA_ITEMS / f"{payload.item_id}.json"

    if not item_file.exists():
        raise HTTPException(status_code=404, detail="item не найден")

    with open(item_file, "r", encoding="utf-8") as fh:
        item = json.load(fh)

    old_status = item.get("status")

    item["status"] = payload.status
    item["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(item_file, "w", encoding="utf-8") as fh:
        json.dump(item, fh, ensure_ascii=False, indent=2)

    # history
    history_entry = {
        "item_id": payload.item_id,
        "from": old_status,
        "to": payload.status,
        "at": item["updated_at"],
    }

    history_file = DATA_HISTORY / f"{payload.item_id}.json"
    history = []

    if history_file.exists():
        history = json.loads(history_file.read_text(encoding="utf-8"))

    history.append(history_entry)
    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {"status": "ok"}


# -----------------------------
# UI
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (UI_DIR / "dashboard.html").read_text(encoding="utf-8")
