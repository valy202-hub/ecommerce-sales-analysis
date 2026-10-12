-- Project: E-commerce sales analysis, Jan-Dec 2025
-- SQL dialect: SQLite
-- IMPORTANT: source data is synthetic. Run against analytics.db built by src/build_database.py.

-- Analytical line-item view. Financial analysis includes delivered orders only.
DROP VIEW IF EXISTS line_item_facts;
CREATE VIEW line_item_facts AS
SELECT
    oi.order_item_id,
    o.order_id,
    o.order_date,
    strftime('%Y-%m', o.order_date) AS month,
    o.customer_id,
    c.region,
    c.city,
    o.sales_channel,
    o.payment_method,
    o.order_status,
    p.product_id,
    p.product_name,
    p.category,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    p.unit_cost,
    oi.quantity * oi.unit_price AS gross_sales,
    oi.quantity * oi.unit_price * oi.discount_pct AS discount_amount,
    oi.quantity * oi.unit_price * (1 - oi.discount_pct) AS net_revenue,
    oi.quantity * p.unit_cost AS cogs,
    oi.quantity * oi.unit_price * (1 - oi.discount_pct) - oi.quantity * p.unit_cost AS gross_profit
FROM order_items AS oi
JOIN orders AS o ON o.order_id = oi.order_id
JOIN products AS p ON p.product_id = oi.product_id
JOIN customers AS c ON c.customer_id = o.customer_id;

-- 1. Monthly revenue, gross profit, margin and average order value.
WITH order_level AS (
    SELECT order_id, month,
           SUM(net_revenue) AS net_revenue,
           SUM(gross_profit) AS gross_profit,
           SUM(quantity) AS units_sold,
           SUM(gross_sales) AS gross_sales,
           SUM(discount_amount) AS discount_amount
    FROM line_item_facts
    WHERE order_status = 'Доставлен'
    GROUP BY order_id, month
)
SELECT month,
       COUNT(*) AS delivered_orders,
       ROUND(SUM(net_revenue), 2) AS net_revenue,
       ROUND(SUM(gross_profit), 2) AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(net_revenue), 2) AS gross_margin_pct,
       ROUND(AVG(net_revenue), 2) AS average_order_value,
       ROUND(100.0 * SUM(discount_amount) / SUM(gross_sales), 2) AS avg_discount_pct
FROM order_level
GROUP BY month
ORDER BY month;

-- 2. Performance by category.
SELECT category,
       SUM(quantity) AS units_sold,
       COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(net_revenue), 2) AS net_revenue,
       ROUND(SUM(gross_profit), 2) AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(net_revenue), 2) AS gross_margin_pct,
       ROUND(100.0 * SUM(net_revenue) / (SELECT SUM(net_revenue) FROM line_item_facts WHERE order_status = 'Доставлен'), 2) AS revenue_share_pct
FROM line_item_facts
WHERE order_status = 'Доставлен'
GROUP BY category
ORDER BY net_revenue DESC;

-- 3. Top 10 products by revenue.
SELECT product_id, product_name, category,
       SUM(quantity) AS units_sold,
       ROUND(SUM(net_revenue), 2) AS net_revenue,
       ROUND(SUM(gross_profit), 2) AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(net_revenue), 2) AS gross_margin_pct
FROM line_item_facts
WHERE order_status = 'Доставлен'
GROUP BY product_id, product_name, category
ORDER BY net_revenue DESC
LIMIT 10;

-- 4. Sales-channel performance + cancellation and return rates.
WITH order_status AS (
    SELECT sales_channel,
           COUNT(*) AS all_orders,
           SUM(CASE WHEN order_status = 'Доставлен' THEN 1 ELSE 0 END) AS delivered_orders,
           SUM(CASE WHEN order_status = 'Отменён' THEN 1 ELSE 0 END) AS cancelled_orders,
           SUM(CASE WHEN order_status = 'Возврат' THEN 1 ELSE 0 END) AS returned_orders
    FROM orders
    GROUP BY sales_channel
), channel_finance AS (
    SELECT sales_channel,
           COUNT(DISTINCT order_id) AS delivered_orders_finance,
           SUM(net_revenue) AS net_revenue,
           SUM(gross_profit) AS gross_profit
    FROM line_item_facts
    WHERE order_status = 'Доставлен'
    GROUP BY sales_channel
)
SELECT s.sales_channel, s.all_orders, s.delivered_orders, s.cancelled_orders, s.returned_orders,
       ROUND(100.0 * s.cancelled_orders / s.all_orders, 2) AS cancel_rate_pct,
       ROUND(100.0 * s.returned_orders / NULLIF(s.returned_orders + s.delivered_orders, 0), 2) AS return_rate_pct,
       ROUND(f.net_revenue, 2) AS net_revenue,
       ROUND(f.gross_profit, 2) AS gross_profit,
       ROUND(100.0 * f.gross_profit / f.net_revenue, 2) AS gross_margin_pct,
       ROUND(f.net_revenue / NULLIF(f.delivered_orders_finance, 0), 2) AS average_order_value
FROM order_status s
LEFT JOIN channel_finance f USING (sales_channel)
ORDER BY f.net_revenue DESC;

-- 5. Regional performance.
SELECT region,
       COUNT(DISTINCT order_id) AS delivered_orders,
       COUNT(DISTINCT customer_id) AS buyers,
       ROUND(SUM(net_revenue), 2) AS net_revenue,
       ROUND(SUM(gross_profit), 2) AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(net_revenue), 2) AS gross_margin_pct,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT customer_id), 2) AS revenue_per_buyer
FROM line_item_facts
WHERE order_status = 'Доставлен'
GROUP BY region
ORDER BY net_revenue DESC;

-- 6. Overall order-status rates (status table has one row per order).
SELECT order_status,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM orders), 2) AS share_pct
FROM orders
GROUP BY order_status
ORDER BY orders DESC;

-- 7. Repeat buyers: customers with at least two delivered orders.
WITH customer_orders AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS delivered_orders
    FROM line_item_facts
    WHERE order_status = 'Доставлен'
    GROUP BY customer_id
)
SELECT COUNT(*) AS buyers,
       SUM(CASE WHEN delivered_orders >= 2 THEN 1 ELSE 0 END) AS repeat_buyers,
       ROUND(100.0 * SUM(CASE WHEN delivered_orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_buyer_pct
FROM customer_orders;

-- 8. Data-quality checks: duplicate primary keys and orphan references should be zero.
SELECT 'duplicate_order_id' AS check_name, COUNT(*) - COUNT(DISTINCT order_id) AS issue_count FROM orders
UNION ALL
SELECT 'duplicate_customer_id', COUNT(*) - COUNT(DISTINCT customer_id) FROM customers
UNION ALL
SELECT 'duplicate_product_id', COUNT(*) - COUNT(DISTINCT product_id) FROM products
UNION ALL
SELECT 'order_without_customer', COUNT(*) FROM orders o LEFT JOIN customers c ON c.customer_id = o.customer_id WHERE c.customer_id IS NULL
UNION ALL
SELECT 'item_without_order', COUNT(*) FROM order_items i LEFT JOIN orders o ON o.order_id = i.order_id WHERE o.order_id IS NULL
UNION ALL
SELECT 'item_without_product', COUNT(*) FROM order_items i LEFT JOIN products p ON p.product_id = i.product_id WHERE p.product_id IS NULL
UNION ALL
SELECT 'non_positive_quantity', COUNT(*) FROM order_items WHERE quantity <= 0
UNION ALL
SELECT 'invalid_discount_pct', COUNT(*) FROM order_items WHERE discount_pct < 0 OR discount_pct > 1;
