import os
import yaml
import json
import uuid
import pandas as pd

from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from ozon_client import OzonClient
from ozon_product_client import OzonProductClient
from utils.html_report import save_html_report


# -----------------------------
# PATHS (FIXED ARCHITECTURE)
# -----------------------------
BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "backend" / "storage"
ITEMS_DIR = STORAGE_DIR / "items"
HISTORY_DIR = STORAGE_DIR / "history"

ITEMS_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# LOADERS
# -----------------------------
def load_accounts():
    with open("config/accounts.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["accounts"]


def load_category_config():
    with open("config/product_categories.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    return cfg.get("categories", {}), cfg.get("default", "Иное")


def map_category_name(category_id, category_map, default_name):
    if category_id is None:
        return default_name
    return category_map.get(int(category_id), default_name)


# -----------------------------
# MAIN
# -----------------------------
def main():
    load_dotenv()

    accounts = load_accounts()
    category_map, default_category = load_category_config()

    all_rows = []

    batch_id = (
        datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid.uuid4().hex[:4]
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    for acc in accounts:
        print(f"\n=== Аккаунт: {acc['name']} ===")

        client_id = os.getenv(acc["client_id_env"])
        api_key = os.getenv(acc["api_key_env"])

        if not client_id or not api_key:
            raise RuntimeError(f"Нет ключей для аккаунта {acc['name']}")

        ozon_client = OzonClient(client_id, api_key)
        product_client = OzonProductClient(client_id, api_key)

        postings = ozon_client.get_unfulfilled()
        print(f"Получено заказов: {len(postings)}")

        # -----------------------------
        # COLLECT OFFER IDS
        # -----------------------------
        offer_ids = set()
        for p in postings:
            for item in p.get("products", []):
                if item.get("offer_id"):
                    offer_ids.add(item["offer_id"])

        # -----------------------------
        # LOAD PRODUCT INFO (IMAGES)
        # -----------------------------
        product_info = {}
        if offer_ids:
            print(f"Загрузка информации о товарах ({len(offer_ids)})")
            product_info = product_client.get_products_info_by_offer_ids(
                list(offer_ids)
            )

        # -----------------------------
        # PROCESS POSTINGS
        # -----------------------------
        for p in postings:
            posting_number = p.get("posting_number")
            order_date = p.get("in_process_at")
            products = p.get("products", [])

            items_str = ", ".join(
                f"{item.get('offer_id')} "
                f"({map_category_name(item.get('description_category_id'), category_map, default_category)}) "
                f"x{item.get('quantity')}"
                for item in products
            )

            all_rows.append(
                {
                    "account": acc["name"],
                    "posting_number": posting_number,
                    "order_date": order_date,
                    "items": items_str,
                }
            )

            for item in products:
                offer_id = item.get("offer_id")
                quantity = item.get("quantity", 1)

                info = product_info.get(offer_id, {})
                if not isinstance(info, dict):
                    info = {}

                image_url = info.get("primary_image")

                category_name = map_category_name(
                    item.get("description_category_id"),
                    category_map,
                    default_category,
                )

                item_id = f"{posting_number}_{offer_id}"
                item_path = ITEMS_DIR / f"{item_id}.json"

                if item_path.exists():
                    existing = json.loads(item_path.read_text(encoding="utf-8"))
                    existing["updated_at"] = now_iso
                    item_path.write_text(
                        json.dumps(existing, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    continue

                item_data = {
                    "item_id": item_id,
                    "account": acc["name"],
                    "posting_number": posting_number,
                    "offer_id": offer_id,
                    "quantity": quantity,
                    "category": category_name,
                    "image_url": image_url,

                    "status": "awaiting_packaging",

                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "source_batch_id": batch_id,
                }

                item_path.write_text(
                    json.dumps(item_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    # -----------------------------
    # REPORTS
    # -----------------------------
    df = pd.DataFrame(all_rows)

    print("\n=== Заказы awaiting_packaging ===\n")
    if df.empty:
        print("Нет заказов")
    else:
        print(df.to_string(index=False))
        print("\nВсего заказов:", len(df))

    os.makedirs("reports", exist_ok=True)

    html_path = save_html_report(
        df,
        "reports/unfulfilled.html",
        title="Невыполненные заказы (awaiting_packaging)",
    )

    excel_path = "reports/unfulfilled.xlsx"
    df.to_excel(excel_path, index=False, sheet_name="awaiting_packaging")

    print(f"\nHTML-отчёт сохранён: {html_path}")
    print(f"Excel-отчёт сохранён: {excel_path}")
    print("\n✅ Items сохранены в backend/storage/items")


if __name__ == "__main__":
    main()
