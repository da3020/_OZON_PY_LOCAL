import os
import yaml
import json
import pandas as pd
import requests
import uuid

from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

from ozon_client import OzonClient
from ozon_product_client import OzonProductClient
from utils.html_report import save_html_report


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
    if not category_id:
        return default_name
    return category_map.get(int(category_id), default_name)


# -----------------------------
# UI EXPORT (LOCAL DASHBOARD)
# -----------------------------
def export_items_for_ui(items: list):
    base = Path("backend/data/items")
    base.mkdir(parents=True, exist_ok=True)

    for item in items:
        item_id = f"{item['posting_number']}_{item['offer_id']}.json"
        path = base / item_id

        ui_item = {
            "id": item_id,
            "posting_number": item["posting_number"],
            "offer_id": item["offer_id"],
            "account": item["account"],
            "quantity": item["quantity"],
            "category": item["category"],          # ← КАТЕГОРИЯ ДЛЯ UI
            "image_url": item["image_url"],
            "status": "new",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(ui_item, f, ensure_ascii=False, indent=2)


# -----------------------------
# SERVER COMMUNICATION
# -----------------------------
def send_batch_to_server(batch_endpoint: str, payload: dict):
    response = requests.post(batch_endpoint, json=payload, timeout=20)

    if response.status_code != 200:
        raise RuntimeError(
            f"Ошибка отправки batch: {response.status_code} {response.text}"
        )

    print("Batch успешно отправлен на сервер:")
    print(response.json())


# -----------------------------
# MAIN
# -----------------------------
def main():
    load_dotenv()

    batch_endpoint = os.getenv("PRODUCTION_BATCH_CREATE_URL")
    if not batch_endpoint:
        raise RuntimeError("Не задан PRODUCTION_BATCH_CREATE_URL в .env")

    accounts = load_accounts()
    category_map, default_category = load_category_config()

    all_rows = []
    batch_items = []

    batch_id = (
        datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid.uuid4().hex[:4]
    )

    batch_created_at = datetime.now(timezone.utc).isoformat()

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
        offer_ids = {
            item["offer_id"]
            for p in postings
            for item in p.get("products", [])
            if item.get("offer_id")
        }

        # -----------------------------
        # LOAD PRODUCT INFO (icons + categories)
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
            products = p.get("products", [])
            order_date = p.get("in_process_at")

            items_str = ", ".join(
                f"{item['offer_id']} "
                f"({map_category_name(
                    product_info.get(item['offer_id'], {}).get('description_category_id'),
                    category_map,
                    default_category
                )}) x{item.get('quantity', 1)}"
                for item in products
            )

            all_rows.append({
                "account": acc["name"],
                "posting_number": p.get("posting_number"),
                "order_date": order_date,
                "items": items_str,
            })

            for item in products:
                offer_id = item["offer_id"]
                info = product_info.get(offer_id, {}) or {}

                category_id = info.get("description_category_id")
                category_name = map_category_name(
                    category_id,
                    category_map,
                    default_category
                )

                batch_items.append({
                    "account": acc["name"],
                    "posting_number": p.get("posting_number"),
                    "offer_id": offer_id,
                    "quantity": item.get("quantity", 1),
                    "category": category_name,          # ← КЛЮЧЕВО
                    "image_url": info.get("primary_image"),
                })

    # -----------------------------
    # OUTPUT
    # -----------------------------
    df = pd.DataFrame(all_rows)

    print("\n=== Заказы awaiting_packaging ===\n")
    print(df.to_string(index=False) if not df.empty else "Нет заказов")

    os.makedirs("reports", exist_ok=True)

    save_html_report(
        df,
        "reports/unfulfilled.html",
        title="Невыполненные заказы (awaiting_packaging)",
    )

    df.to_excel("reports/unfulfilled.xlsx", index=False)

    # -----------------------------
    # EXPORT FOR LOCAL UI
    # -----------------------------
    print("Экспорт данных для локального UI...")
    export_items_for_ui(batch_items)

    # -----------------------------
    # SEND BATCH
    # -----------------------------
    send_batch_to_server(batch_endpoint, {
        "batch_id": batch_id,
        "batch_created_at": batch_created_at,
        "total_orders": len(df),
        "items": batch_items,
    })


if __name__ == "__main__":
    main()
