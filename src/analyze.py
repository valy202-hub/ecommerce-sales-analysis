"""Reproducible exploratory analysis for the synthetic e-commerce sales project."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"
REPORT = ROOT / "report"
for d in (OUT, CHARTS, REPORT):
    d.mkdir(parents=True, exist_ok=True)

customers = pd.read_csv(RAW / "customers.csv", parse_dates=["signup_date"])
products = pd.read_csv(RAW / "products.csv")
orders = pd.read_csv(RAW / "orders.csv", parse_dates=["order_date"])
items = pd.read_csv(RAW / "order_items.csv")

# Data-quality checks are saved before analysis. Most checks should return zero issues.
checks = []
def add_check(name, actual, expected, passed, note):
    checks.append({"check": name, "actual": actual, "expected": expected, "passed": bool(passed), "note": note})

add_check("duplicate customer_id", int(customers.customer_id.duplicated().sum()), 0, not customers.customer_id.duplicated().any(), "Customer primary key should be unique.")
add_check("duplicate product_id", int(products.product_id.duplicated().sum()), 0, not products.product_id.duplicated().any(), "Product primary key should be unique.")
add_check("duplicate order_id", int(orders.order_id.duplicated().sum()), 0, not orders.order_id.duplicated().any(), "Order primary key should be unique.")
add_check("duplicate order_item_id", int(items.order_item_id.duplicated().sum()), 0, not items.order_item_id.duplicated().any(), "Order-line primary key should be unique.")
add_check("orders without customer", int((~orders.customer_id.isin(customers.customer_id)).sum()), 0, orders.customer_id.isin(customers.customer_id).all(), "Every order should map to a customer.")
add_check("items without order", int((~items.order_id.isin(orders.order_id)).sum()), 0, items.order_id.isin(orders.order_id).all(), "Every line item should map to an order.")
add_check("items without product", int((~items.product_id.isin(products.product_id)).sum()), 0, items.product_id.isin(products.product_id).all(), "Every line item should map to a product.")
add_check("missing values in core order fields", int(orders[["order_id", "customer_id", "order_date", "sales_channel", "order_status"]].isna().sum().sum()), 0, not orders[["order_id", "customer_id", "order_date", "sales_channel", "order_status"]].isna().any().any(), "Required order fields should be populated.")
add_check("non-positive quantities", int((items.quantity <= 0).sum()), 0, not (items.quantity <= 0).any(), "Quantity should be positive.")
add_check("discount out of range", int(((items.discount_pct < 0) | (items.discount_pct > 1)).sum()), 0, not (((items.discount_pct < 0) | (items.discount_pct > 1)).any()), "Discount is stored as a fraction from 0 to 1.")
first_order = orders.groupby("customer_id").order_date.min()
check_signup = customers.set_index("customer_id").join(first_order.rename("first_order_date"))
late_signup = check_signup[check_signup.first_order_date.notna() & (check_signup.signup_date > check_signup.first_order_date)]
add_check("signup after first recorded order", len(late_signup), 0, len(late_signup) == 0, "For customers with orders, signup should not be after first order.")
pd.DataFrame(checks).to_csv(OUT / "data_quality_checks.csv", index=False, encoding="utf-8-sig")

# Build a line-level analytical model. Price is the listed unit price; discount is applied per line.
line = (items.merge(orders, on="order_id", how="left", validate="many_to_one")
        .merge(products[["product_id", "product_name", "category", "unit_cost"]], on="product_id", how="left", validate="many_to_one")
        .merge(customers[["customer_id", "region", "city"]], on="customer_id", how="left", validate="many_to_one"))
line["month"] = line.order_date.dt.to_period("M").astype(str)
line["gross_sales"] = line.quantity * line.unit_price
line["discount_amount"] = line.gross_sales * line.discount_pct
line["net_revenue"] = line.gross_sales - line.discount_amount
line["cogs"] = line.quantity * line.unit_cost
line["gross_profit"] = line.net_revenue - line.cogs
line["gross_margin_pct"] = np.where(line.net_revenue > 0, line.gross_profit / line.net_revenue, np.nan)

# Only successfully delivered orders are counted as recognized sales in this case study.
delivered = line[line.order_status.eq("Доставлен")].copy()
delivered_orders = orders[orders.order_status.eq("Доставлен")].copy()
order_amounts = (delivered.groupby(["order_id", "customer_id", "order_date", "sales_channel", "payment_method"])
                 .agg(net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"), units=("quantity", "sum"),
                      gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum"))
                 .reset_index())
order_amounts["month"] = order_amounts.order_date.dt.to_period("M").astype(str)

# Core KPI table.
total_orders = len(orders)
delivered_n = int((orders.order_status == "Доставлен").sum())
returned_n = int((orders.order_status == "Возврат").sum())
cancelled_n = int((orders.order_status == "Отменён").sum())
net_revenue = float(delivered.net_revenue.sum())
gross_profit = float(delivered.gross_profit.sum())
unique_buyers = int(order_amounts.customer_id.nunique())
customer_order_count = order_amounts.groupby("customer_id").order_id.nunique()
repeat_buyers = int((customer_order_count >= 2).sum())
metrics = [
    ("Всего заказов", total_orders, "шт.", "Все статусы заказа"),
    ("Доставленные заказы", delivered_n, "шт.", "Заказы со статусом Доставлен"),
    ("Выручка после скидок", round(net_revenue, 2), "₽", "Учитываются только доставленные заказы; без возвратов и отмен"),
    ("Валовая прибыль", round(gross_profit, 2), "₽", "Выручка минус себестоимость проданных товаров; без логистики, маркетинга и прочих расходов"),
    ("Валовая маржа", round(gross_profit / net_revenue, 4), "доля", "Валовая прибыль / выручка после скидок"),
    ("Средний чек", round(order_amounts.net_revenue.mean(), 2), "₽", "Средняя выручка по доставленному заказу"),
    ("Уникальные покупатели", unique_buyers, "чел.", "Покупатели с минимум одним доставленным заказом"),
    ("Доля повторных покупателей", round(repeat_buyers / unique_buyers, 4) if unique_buyers else 0, "доля", "Покупатели с двумя и более доставленными заказами / все покупатели"),
    ("Доля отмен", round(cancelled_n / total_orders, 4), "доля", "Отменённые заказы / все созданные заказы"),
    ("Доля возвратов среди неотменённых", round(returned_n / (returned_n + delivered_n), 4), "доля", "Возвраты / (доставленные + возвращённые) заказы"),
    ("Средняя скидка по доставленным товарам", round(float(delivered.discount_amount.sum() / delivered.gross_sales.sum()), 4), "доля", "Сумма скидок / цена до скидок по доставленным заказам"),
    ("Количество проданных единиц", int(delivered.quantity.sum()), "шт.", "Единицы товара в доставленных заказах"),
]
summary = pd.DataFrame(metrics, columns=["metric", "value", "unit", "definition"])
summary.to_csv(OUT / "summary_metrics.csv", index=False, encoding="utf-8-sig")

# Monthly performance.
monthly = (order_amounts.groupby("month", as_index=False)
           .agg(delivered_orders=("order_id", "nunique"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"),
                units_sold=("units", "sum"), gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum")))
monthly["gross_margin_pct"] = monthly.gross_profit / monthly.net_revenue
monthly["aov"] = monthly.net_revenue / monthly.delivered_orders
monthly["avg_discount_pct"] = monthly.discount_amount / monthly.gross_sales
monthly.to_csv(OUT / "monthly_kpis.csv", index=False, encoding="utf-8-sig")

# Category and product performance.
category = (delivered.groupby("category", as_index=False)
            .agg(units_sold=("quantity", "sum"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"),
                 gross_sales=("gross_sales", "sum"), discount_amount=("discount_amount", "sum"), order_count=("order_id", "nunique")))
category["gross_margin_pct"] = category.gross_profit / category.net_revenue
category["avg_discount_pct"] = category.discount_amount / category.gross_sales
category["revenue_share_pct"] = category.net_revenue / category.net_revenue.sum()
category = category.sort_values("net_revenue", ascending=False)
category.to_csv(OUT / "category_performance.csv", index=False, encoding="utf-8-sig")

product = (delivered.groupby(["product_id", "product_name", "category"], as_index=False)
           .agg(units_sold=("quantity", "sum"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"),
                order_count=("order_id", "nunique")))
product["gross_margin_pct"] = product.gross_profit / product.net_revenue
product = product.sort_values("net_revenue", ascending=False)
product.to_csv(OUT / "product_performance.csv", index=False, encoding="utf-8-sig")

# Sales channels: financials for delivered orders + operational order statuses for all orders.
channel_fin = (order_amounts.groupby("sales_channel", as_index=False)
               .agg(delivered_orders=("order_id", "nunique"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum")))
channel_fin["aov"] = channel_fin.net_revenue / channel_fin.delivered_orders
channel_fin["gross_margin_pct"] = channel_fin.gross_profit / channel_fin.net_revenue
channel_status = pd.crosstab(orders.sales_channel, orders.order_status).reset_index()
for col in ["Доставлен", "Отменён", "Возврат"]:
    if col not in channel_status:
        channel_status[col] = 0
channel_all = orders.groupby("sales_channel", as_index=False).agg(all_orders=("order_id", "nunique"))
channel = channel_fin.merge(channel_status, on="sales_channel", how="left").merge(channel_all, on="sales_channel", how="left")
channel["cancel_rate_pct"] = channel["Отменён"] / channel.all_orders
channel["return_rate_pct"] = channel["Возврат"] / (channel["Возврат"] + channel["Доставлен"])
channel = channel.sort_values("net_revenue", ascending=False)
channel.to_csv(OUT / "channel_performance.csv", index=False, encoding="utf-8-sig")

# Region performance.
region_fin = (delivered.groupby("region", as_index=False)
              .agg(delivered_orders=("order_id", "nunique"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"),
                   unique_buyers=("customer_id", "nunique")))
region_fin["aov"] = region_fin.net_revenue / region_fin.delivered_orders
region_fin["gross_margin_pct"] = region_fin.gross_profit / region_fin.net_revenue
region_status = pd.crosstab(orders.merge(customers[["customer_id", "region"]], on="customer_id", how="left").region,
                            orders.merge(customers[["customer_id", "region"]], on="customer_id", how="left").order_status).reset_index()
region = region_fin.merge(region_status, on="region", how="left")
region["net_revenue_per_buyer"] = region.net_revenue / region.unique_buyers
region = region.sort_values("net_revenue", ascending=False)
region.to_csv(OUT / "region_performance.csv", index=False, encoding="utf-8-sig")

status = orders.groupby("order_status", as_index=False).agg(order_count=("order_id", "nunique"))
status["share_pct"] = status.order_count / len(orders)
status.to_csv(OUT / "order_status_summary.csv", index=False, encoding="utf-8-sig")

# Monthly orders and order-status rates.
month_status = orders.assign(month=orders.order_date.dt.to_period("M").astype(str)).pivot_table(index="month", columns="order_status", values="order_id", aggfunc="nunique", fill_value=0).reset_index()
month_status.to_csv(OUT / "monthly_order_status.csv", index=False, encoding="utf-8-sig")

# Charts.
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

fig, ax1 = plt.subplots(figsize=(10, 5.5))
ax1.plot(monthly.month, monthly.net_revenue, marker="o", linewidth=2.5, label="Выручка")
ax1.set_ylabel("Выручка, ₽")
ax1.tick_params(axis="x", rotation=45)
ax2 = ax1.twinx()
ax2.plot(monthly.month, monthly.gross_margin_pct * 100, marker="s", linewidth=2, linestyle="--", label="Валовая маржа")
ax2.set_ylabel("Валовая маржа, %")
ax1.set_title("Выручка и валовая маржа по месяцам, 2025")
ax1.grid(axis="y", alpha=.25)
fig.tight_layout()
fig.savefig(CHARTS / "monthly_revenue_margin.png", dpi=160, bbox_inches="tight")
plt.close(fig)

cat_plot = category.sort_values("net_revenue", ascending=True)
fig, ax = plt.subplots(figsize=(9, 5.5))
y = np.arange(len(cat_plot))
ax.barh(y - 0.18, cat_plot.net_revenue / 1000, height=0.35, label="Выручка, тыс. ₽")
ax.barh(y + 0.18, cat_plot.gross_profit / 1000, height=0.35, label="Валовая прибыль, тыс. ₽")
ax.set_yticks(y, cat_plot.category)
ax.set_xlabel("тыс. ₽")
ax.set_title("Выручка и валовая прибыль по категориям")
ax.legend(frameon=False)
ax.grid(axis="x", alpha=.2)
fig.tight_layout()
fig.savefig(CHARTS / "category_revenue_profit.png", dpi=160, bbox_inches="tight")
plt.close(fig)

channel_plot = channel.sort_values("net_revenue", ascending=True)
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.barh(channel_plot.sales_channel, channel_plot.net_revenue / 1000)
ax.set_xlabel("Выручка, тыс. ₽")
ax.set_title("Выручка по каналам продаж")
ax.grid(axis="x", alpha=.25)
for i, val in enumerate(channel_plot.net_revenue / 1000):
    ax.text(val, i, f" {val:,.0f}".replace(",", " "), va="center", fontsize=9)
fig.tight_layout()
fig.savefig(CHARTS / "channel_revenue.png", dpi=160, bbox_inches="tight")
plt.close(fig)

region_plot = region.sort_values("gross_margin_pct", ascending=True)
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.barh(region_plot.region, region_plot.gross_margin_pct * 100)
ax.set_xlabel("Валовая маржа, %")
ax.set_title("Валовая маржа по регионам")
ax.grid(axis="x", alpha=.25)
fig.tight_layout()
fig.savefig(CHARTS / "region_margin.png", dpi=160, bbox_inches="tight")
plt.close(fig)

# Machine-readable analysis result.
summary_dict = {r.metric: r.value for r in summary.itertuples(index=False)}
with open(OUT / "summary_metrics.json", "w", encoding="utf-8") as f:
    json.dump(summary_dict, f, ensure_ascii=False, indent=2)

# Report with numbers calculated from generated dataset.
month_start = monthly.iloc[0]
month_end = monthly.iloc[-1]
month_oct = monthly[monthly.month == "2025-10"].iloc[0]
month_dec = monthly[monthly.month == "2025-12"].iloc[0]
monthly_revenue_growth = (month_end.net_revenue / month_start.net_revenue - 1) if month_start.net_revenue else np.nan
best_category = category.iloc[0]
best_profit_category = category.sort_values("gross_profit", ascending=False).iloc[0]
lowest_margin_category = category.sort_values("gross_margin_pct").iloc[0]
best_channel = channel.iloc[0]
best_margin_channel = channel.sort_values("gross_margin_pct", ascending=False).iloc[0]
top_product = product.iloc[0]
biggest_region = region.iloc[0]
checks_failed = int((~pd.DataFrame(checks).passed).sum())
report = f'''# Отчёт: анализ продаж интернет-магазина за 2025 год

> **Тип данных:** синтетические данные, созданные для учебного портфолио. Результаты не описывают реальную компанию.

## 1. Краткое резюме

- За год создано **{total_orders:,} заказов**, из них доставлено **{delivered_n:,}**.
- Выручка после скидок по доставленным заказам составила **{net_revenue:,.0f} ₽**.
- Валовая прибыль составила **{gross_profit:,.0f} ₽**, валовая маржа — **{gross_profit / net_revenue:.1%}**.
- Средний чек доставленного заказа — **{order_amounts.net_revenue.mean():,.0f} ₽**.
- Доля отмен от всех заказов — **{cancelled_n / total_orders:.1%}**; доля возвратов среди неотменённых заказов — **{returned_n / (returned_n + delivered_n):.1%}**.

## 2. Бизнес-вопросы

1. Как менялись выручка и валовая маржа по месяцам?
2. Какие товарные категории и товары дают больше всего выручки и валовой прибыли?
3. Какие каналы продаж дают наибольшую выручку и какой у них средний чек?
4. Отличается ли валовая маржа между регионами?
5. Каковы доли отмен и возвратов?

## 3. Основные наблюдения

### Динамика

Выручка в декабре относительно января изменилась на **{monthly_revenue_growth:.1%}**. В данных выражен сезонный рост количества заказов к концу года. Одновременно валовая маржа снизилась с **{month_oct.gross_margin_pct:.1%}** в октябре до **{month_dec.gross_margin_pct:.1%}** в декабре, а средняя скидка выросла с **{month_oct.avg_discount_pct:.1%}** до **{month_dec.avg_discount_pct:.1%}**. В этой синтетической выборке динамика согласуется с более интенсивными скидками в пиковые месяцы, но сама по себе не доказывает причинность.

![Выручка и маржа по месяцам](../charts/monthly_revenue_margin.png)

### Категории и товары

Категория с наибольшей выручкой — **{best_category.category}** ({best_category.net_revenue:,.0f} ₽, доля выручки {best_category.revenue_share_pct:.1%}).
Категория с наибольшей валовой прибылью — **{best_profit_category.category}** ({best_profit_category.gross_profit:,.0f} ₽). Самая низкая валовая маржа наблюдается в категории **{lowest_margin_category.category}** ({lowest_margin_category.gross_margin_pct:.1%}).
Самый высокий товар по выручке — **{top_product.product_name}** ({top_product.net_revenue:,.0f} ₽). Категория «Электроника» формирует около **{best_category.revenue_share_pct:.1%}** выручки, но её маржа (**{best_category.gross_margin_pct:.1%}**) ниже, чем у аксессуаров (**{category.loc[category.category == "Аксессуары", "gross_margin_pct"].iloc[0]:.1%}**).

![Выручка и валовая прибыль по категориям](../charts/category_revenue_profit.png)

### Каналы продаж

Наибольшая выручка приходится на канал **{best_channel.sales_channel}** ({best_channel.net_revenue:,.0f} ₽). Наибольшая валовая маржа — у канала **{best_margin_channel.sales_channel}** ({best_margin_channel.gross_margin_pct:.1%}). Это разные метрики: канал с максимальной выручкой не обязательно максимизирует прибыльность.

![Выручка по каналам продаж](../charts/channel_revenue.png)

### Регионы

Наибольшая выручка в данных приходится на регион **{biggest_region.region}** ({biggest_region.net_revenue:,.0f} ₽). Сравнение регионов стоит дополнять числом покупателей и заказов: абсолютная выручка зависит от масштаба аудитории.

![Валовая маржа по регионам](../charts/region_margin.png)

## 4. Рекомендации бизнесу

1. **Планировать сезонные запасы заранее.** В данных объём заказов повышается в конце года; подготовка запасов и логистики должна начинаться до пиковых месяцев.
2. **Сравнивать каналы по валовой прибыли, а не только по выручке.** В реальной задаче нужно добавить расходы на рекламу, комиссии и логистику, чтобы оценить вклад после переменных расходов.
3. **Проверить скидочную политику.** Скидка может увеличить продажи, но уменьшает выручку на единицу товара. Её эффект нужно оценивать вместе с валовой прибылью и объёмом.
4. **Разобрать отмены и возвраты по причинам.** В этой синтетической таблице причины не предоставлены, поэтому следующий шаг для реального бизнеса — собрать причины, сроки доставки и обращения в поддержку.
5. **Проверить товарный ассортимент.** Сопоставить товары с высокой выручкой и низкой маржой, а также товары с меньшей выручкой, но высоким вкладом в прибыль.

## 5. Методология и ограничения

- В выручку включены только строки заказов со статусом **«Доставлен»**.
- Выручка рассчитана после скидки: `quantity * unit_price * (1 - discount_pct)`.
- Себестоимость товаров: `quantity * unit_cost`.
- Валовая прибыль = выручка после скидки − себестоимость товаров.
- Валовая прибыль не включает логистику, комиссии площадок, рекламные расходы, зарплаты и другие операционные затраты.
- Канал продаж сравнивается по финансовому результату и статусам заказов; конверсию канала посчитать нельзя без данных о посещениях и рекламных расходах.
- Данные сгенерированы случайным образом с фиксированным seed и сезонными допущениями. Найденные закономерности иллюстрируют метод анализа, а не подтверждают реальные рыночные факты.

## 6. Контроль качества

Выполнено {len(checks)} автоматических проверок: уникальность ключей, целостность связей между таблицами, заполненность основных полей, допустимость скидок и количеств, корректность дат регистрации относительно первой покупки. Не пройдено проверок: **{checks_failed}**.

Подробные результаты — в `outputs/data_quality_checks.csv`.
'''
with open(REPORT / "analysis_report.md", "w", encoding="utf-8") as f:
    f.write(report)

# Useful flat table for quick review, but normalized tables remain the source of truth.
line.to_csv(OUT / "joined_line_items.csv", index=False, encoding="utf-8-sig")
print(summary.to_string(index=False))
print("\nTop categories:\n", category[["category", "net_revenue", "gross_profit", "gross_margin_pct"]].to_string(index=False))
print("\nChannels:\n", channel[["sales_channel", "net_revenue", "gross_profit", "gross_margin_pct", "aov", "cancel_rate_pct", "return_rate_pct"]].to_string(index=False))
print(f"\nChecks failed: {checks_failed}/{len(checks)}")
