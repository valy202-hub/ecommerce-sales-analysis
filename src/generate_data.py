"""Generate reproducible synthetic e-commerce data for portfolio practice.
All data and names are fictional. Seed is fixed for repeatability.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20261012)

# ---- Product dimension ----
categories = {
    "Электроника": {"n": 18, "price": (1800, 18000), "margin": (0.18, 0.31)},
    "Дом и кухня": {"n": 18, "price": (500, 8500), "margin": (0.30, 0.46)},
    "Спорт": {"n": 12, "price": (700, 9000), "margin": (0.28, 0.43)},
    "Аксессуары": {"n": 12, "price": (250, 4200), "margin": (0.42, 0.62)},
}
product_names = {
    "Электроника": ["Беспроводные наушники", "Портативная колонка", "Веб-камера", "Механическая клавиатура", "Мышь", "Монитор", "Зарядное устройство", "Пауэрбанк", "Роутер", "Внешний SSD", "Микрофон", "Смарт-часы", "Планшет", "Кабель USB-C", "Умная лампа", "Игровой контроллер", "Подставка для ноутбука", "Видеорегистратор"],
    "Дом и кухня": ["Термокружка", "Электрочайник", "Кофемолка", "Настольная лампа", "Органайзер", "Коврик для кухни", "Контейнеры для хранения", "Увлажнитель воздуха", "Весы кухонные", "Набор ножей", "Плед", "Постельное бельё", "Сковорода", "Френч-пресс", "Утюг", "Пылесос ручной", "Тостер", "Светильник"],
    "Спорт": ["Коврик для йоги", "Гантели", "Фитнес-резинки", "Бутылка для воды", "Скакалка", "Ролик для пресса", "Спортивная сумка", "Мяч", "Эспандер", "Перчатки для фитнеса", "Шагомер", "Массажный ролик"],
    "Аксессуары": ["Чехол для телефона", "Защитное стекло", "Кабель-органайзер", "Держатель телефона", "Картхолдер", "Сумка-шоппер", "Кошелёк", "Ключница", "Компактный зонт", "Очки для компьютера", "Брелок", "Набор наклеек"],
}
product_rows = []
pid = 1
for cat, cfg in categories.items():
    for j in range(cfg["n"]):
        price = float(np.exp(rng.uniform(np.log(cfg["price"][0]), np.log(cfg["price"][1]))))
        margin = float(rng.uniform(*cfg["margin"]))
        nm = product_names[cat][j]
        # Some products intentionally have stronger baseline demand.
        popularity = float(rng.lognormal(mean=0.0, sigma=0.55))
        product_rows.append({
            "product_id": f"P{pid:03d}", "product_name": nm,
            "category": cat, "list_price": round(price, 2),
            "unit_cost": round(price * (1 - margin), 2),
            "popularity_weight": round(popularity, 4),
            "is_active": True
        })
        pid += 1
products = pd.DataFrame(product_rows)
products.to_csv(OUT / "products.csv", index=False, encoding="utf-8-sig")

# ---- Customer dimension ----
N_CUSTOMERS = 1800
regions = ["Центральный", "Северо-Западный", "Приволжский", "Уральский", "Сибирский", "Южный", "Дальневосточный", "Северо-Кавказский"]
region_probs = [0.26, 0.16, 0.17, 0.12, 0.12, 0.09, 0.05, 0.03]
cities = {
    "Центральный": ["Москва", "Тула", "Воронеж", "Ярославль"],
    "Северо-Западный": ["Санкт-Петербург", "Псков", "Архангельск"],
    "Приволжский": ["Казань", "Самара", "Уфа", "Пермь"],
    "Уральский": ["Екатеринбург", "Челябинск", "Тюмень"],
    "Сибирский": ["Новосибирск", "Омск", "Красноярск"],
    "Южный": ["Краснодар", "Ростов-на-Дону", "Волгоград"],
    "Дальневосточный": ["Владивосток", "Хабаровск"],
    "Северо-Кавказский": ["Ставрополь", "Махачкала"],
}
customer_regions = rng.choice(regions, size=N_CUSTOMERS, p=region_probs)
customer_rows = []
for i in range(N_CUSTOMERS):
    reg = customer_regions[i]
    customer_rows.append({
        "customer_id": f"C{i+1:05d}",
        "signup_date": (pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 731)))).date().isoformat(),
        "region": reg,
        "city": rng.choice(cities[reg]),
    })
customers = pd.DataFrame(customer_rows)
# Save after orders are generated so signup dates can be checked against first purchase.

# ---- Orders ----
N_ORDERS = 3600
days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
month_weights = np.array([0.65,0.68,0.75,0.78,0.84,0.90,0.88,0.92,0.98,1.08,1.35,1.62], dtype=float)
month_weights /= month_weights.sum()
monthly_counts = rng.multinomial(N_ORDERS, month_weights)
order_dates = []
for month, n in enumerate(monthly_counts, start=1):
    month_days = pd.date_range(f"2025-{month:02d}-01", periods=pd.Period(f"2025-{month:02d}").days_in_month, freq="D")
    order_dates.extend(rng.choice(month_days, size=n, replace=True).tolist())
order_dates = pd.to_datetime(order_dates).to_numpy()
rng.shuffle(order_dates)
channels = ["Органический поиск", "Платная реклама", "Маркетплейс", "Email", "Рекомендации"]
channel_probs = [0.26, 0.24, 0.25, 0.15, 0.10]
payments = ["Карта", "СБП", "Электронный кошелёк"]
status_vals = ["Доставлен", "Отменён", "Возврат"]
orders_rows = []
for i in range(N_ORDERS):
    cust_idx = int(rng.integers(0, N_CUSTOMERS))
    dt = pd.Timestamp(order_dates[i]).normalize()
    ch = str(rng.choice(channels, p=channel_probs))
    # Promotion intensity increases in Nov-Dec, especially paid ads and marketplace.
    m = dt.month
    base_cancel = 0.045 + (0.015 if ch == "Платная реклама" else 0) + (0.01 if m in (11,12) else 0)
    base_return = 0.055 + (0.025 if ch == "Маркетплейс" else 0)
    u = rng.random()
    if u < base_cancel:
        status = "Отменён"
    elif u < base_cancel + base_return:
        status = "Возврат"
    else:
        status = "Доставлен"
    if m in (11,12):
        discount_mean = 0.12 if ch in ("Платная реклама", "Маркетплейс") else 0.085
    elif m in (1,2):
        discount_mean = 0.035
    else:
        discount_mean = 0.055 if ch != "Email" else 0.035
    discount_rate = float(np.clip(rng.normal(discount_mean, 0.035), 0, 0.30))
    orders_rows.append({
        "order_id": f"O{i+1:06d}",
        "customer_id": customers.iloc[cust_idx]["customer_id"],
        "order_date": dt.date().isoformat(),
        "sales_channel": ch,
        "payment_method": str(rng.choice(payments, p=[0.72,0.23,0.05])),
        "order_status": status,
        "discount_rate": round(discount_rate, 4),
    })
orders = pd.DataFrame(orders_rows)
# For customers who purchased in 2025, make sure account creation predates the first purchase.
first_order = orders.groupby("customer_id")["order_date"].min()
for customer_id, first_date in first_order.items():
    idx = customers.index[customers["customer_id"] == customer_id][0]
    current_signup = pd.Timestamp(customers.loc[idx, "signup_date"])
    first_purchase = pd.Timestamp(first_date)
    if current_signup >= first_purchase:
        days_before = int(rng.integers(1, 366))
        customers.loc[idx, "signup_date"] = (first_purchase - pd.Timedelta(days=days_before)).date().isoformat()
customers.to_csv(OUT / "customers.csv", index=False, encoding="utf-8-sig")
orders.to_csv(OUT / "orders.csv", index=False, encoding="utf-8-sig")

# ---- Order line items ----
product_weights = products["popularity_weight"].to_numpy()
product_weights = product_weights / product_weights.sum()
item_rows = []
line_id = 1
for row in orders.itertuples(index=False):
    n_lines = int(rng.choice([1,2,3,4], p=[0.61,0.27,0.095,0.025]))
    chosen = rng.choice(len(products), size=min(n_lines, len(products)), replace=False, p=product_weights)
    # Some channels give slightly larger baskets.
    for idx in chosen:
        p = products.iloc[int(idx)]
        qty = int(rng.choice([1,2,3], p=[0.76,0.20,0.04]))
        discount = float(np.clip(rng.normal(row.discount_rate, 0.025), 0, 0.32))
        item_rows.append({
            "order_item_id": f"L{line_id:07d}",
            "order_id": row.order_id,
            "product_id": p.product_id,
            "quantity": qty,
            "unit_price": round(float(p.list_price), 2),
            "discount_pct": round(discount, 4),
        })
        line_id += 1
items = pd.DataFrame(item_rows)
items.to_csv(OUT / "order_items.csv", index=False, encoding="utf-8-sig")

print(f"Generated: {len(customers)} customers, {len(products)} products, {len(orders)} orders, {len(items)} line items")
print("Order status mix:")
print(orders.order_status.value_counts(normalize=True).round(3).to_string())
print("Monthly order counts:")
print(orders.assign(month=pd.to_datetime(orders.order_date).dt.to_period('M').astype(str)).groupby('month').size().to_string())
