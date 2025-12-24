from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json
from datetime import datetime

app = FastAPI()

# -----------------------------
# CORS (для file://)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).parent
ITEMS_DIR = ROOT / "storage" / "items"
HISTORY_DIR = ROOT / "storage" / "history"

ITEMS_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# MODELS
# -----------------------------
class StatusUpdate(BaseModel):
    item_id: str
    new_status: str
    user: str | None = None

# -----------------------------
# API
# -----------------------------
@app.get("/api/items")
def get_items():
    items = []

    for file in ITEMS_DIR.glob("*.json"):
        with open(file, encoding="utf-8") as f:
            items.append(json.load(f))

    return {"items": items}


@app.post("/api/item/update")
def update_item(payload: StatusUpdate):
    item_file = ITEMS_DIR / f"{payload.item_id}.json"

    if not item_file.exists():
        return {"status": "error", "message": "item not found"}

    with open(item_file, encoding="utf-8") as f:
        item = json.load(f)

    old_status = item.get("status")
    item["status"] = payload.new_status
    item["updated_at"] = datetime.utcnow().isoformat()

    with open(item_file, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)

    # history
    history_record = {
        "item_id": payload.item_id,
        "from": old_status,
        "to": payload.new_status,
        "user": payload.user,
        "timestamp": datetime.utcnow().isoformat(),
    }

    history_file = HISTORY_DIR / f"{payload.item_id}_{int(datetime.utcnow().timestamp())}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_record, f, ensure_ascii=False, indent=2)

    return {"status": "ok"}
