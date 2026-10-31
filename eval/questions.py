# id, difficulty, question, gold_sql (None for unanswerable questions)
# Rules: one checkable answer, state the rounding in the question,
# and run every gold_sql yourself before trusting it.

QUESTIONS = [
    # ---------- EASY (single table) ----------
    {"id": "E1", "difficulty": "easy",
     "question": "How many orders are in the database?",
     "gold_sql": "SELECT COUNT(*) FROM orders"},
    {"id": "E2", "difficulty": "easy",
     "question": "How many orders were canceled?",
     "gold_sql": "SELECT COUNT(*) FROM orders WHERE order_status = 'canceled'"},
    {"id": "E3", "difficulty": "easy",
     "question": "What is the most common payment type, and how many payments used it?",
     "gold_sql": "SELECT payment_type, COUNT(*) FROM order_payments GROUP BY payment_type ORDER BY COUNT(*) DESC LIMIT 1"},
    {"id": "E4", "difficulty": "easy",
     "question": "What is the average price of an order item, rounded to 2 decimals?",
     "gold_sql": "SELECT ROUND(AVG(price), 2) FROM order_items"},
    {"id": "E5", "difficulty": "easy",
     "question": "What is the highest price of any single order item?",
     "gold_sql": "SELECT MAX(price) FROM order_items"},
    {"id": "E6", "difficulty": "easy",
     "question": "How many distinct customer states appear in the customers table?",
     "gold_sql": "SELECT COUNT(DISTINCT customer_state) FROM customers"},
    {"id": "E7", "difficulty": "easy",
     "question": "How many orders have the status 'shipped'?",
     "gold_sql": "SELECT COUNT(*) FROM orders WHERE order_status = 'shipped'"},
    {"id": "E8", "difficulty": "easy",
     "question": "What is the highest number of payment installments used in any single payment?",
     "gold_sql": "SELECT MAX(payment_installments) FROM order_payments"},
    {"id": "E9", "difficulty": "easy",
     "question": "How many products are in the products table?",
     "gold_sql": "SELECT COUNT(*) FROM products"},
    {"id": "E10", "difficulty": "easy",
     "question": "What is the total freight_value across all order items, rounded to 2 decimals?",
     "gold_sql": "SELECT ROUND(SUM(freight_value), 2) FROM order_items"},

    # ---------- MEDIUM (joins, grouping) ----------
    {"id": "M1", "difficulty": "medium",
     "question": "Which 3 customer states have the most orders, and how many orders does each have?",
     "gold_sql": """SELECT c.customer_state, COUNT(*) AS n
                    FROM orders o JOIN customers c ON o.customer_id = c.customer_id
                    GROUP BY c.customer_state ORDER BY n DESC LIMIT 3"""},
    {"id": "M2", "difficulty": "medium",
     "question": "What are the top 5 product categories by number of items sold? Use the English category names and include the counts.",
     "gold_sql": """SELECT t.product_category_name_english, COUNT(*) AS n
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    JOIN category_translation t ON p.product_category_name = t.product_category_name
                    GROUP BY t.product_category_name_english ORDER BY n DESC LIMIT 5"""},
    {"id": "M3", "difficulty": "medium",
     "question": "What is the total payment value of all credit card payments, rounded to 2 decimals?",
     "gold_sql": "SELECT ROUND(SUM(payment_value), 2) FROM order_payments WHERE payment_type = 'credit_card'"},
    {"id": "M4", "difficulty": "medium",
     "question": "What is the average freight_value per order item for customers located in the state SP, rounded to 2 decimals?",
     "gold_sql": """SELECT ROUND(AVG(oi.freight_value), 2)
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    JOIN customers c ON o.customer_id = c.customer_id
                    WHERE c.customer_state = 'SP'"""},
    {"id": "M5", "difficulty": "medium",
     "question": "How many orders were placed in 2017?",
     "gold_sql": "SELECT COUNT(*) FROM orders WHERE strftime('%Y', order_purchase_timestamp) = '2017'"},
    {"id": "M6", "difficulty": "medium",
     "question": "Which payment type has the highest average payment_value, and what is that average, rounded to 2 decimals?",
     "gold_sql": "SELECT payment_type, ROUND(AVG(payment_value), 2) FROM order_payments GROUP BY payment_type ORDER BY AVG(payment_value) DESC LIMIT 1"},
    {"id": "M7", "difficulty": "medium",
     "question": "How many order items were sold in the product category whose English name is 'health_beauty'?",
     "gold_sql": """SELECT COUNT(*)
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    JOIN category_translation t ON p.product_category_name = t.product_category_name
                    WHERE t.product_category_name_english = 'health_beauty'"""},
    {"id": "M8", "difficulty": "medium",
     "question": "How many orders contain more than one item?",
     "gold_sql": """SELECT COUNT(*) FROM (
                      SELECT order_id FROM order_items
                      GROUP BY order_id HAVING COUNT(*) > 1)"""},
    {"id": "M9", "difficulty": "medium",
     "question": "What is the total revenue from item prices (excluding freight) for orders with status 'delivered', rounded to 2 decimals?",
     "gold_sql": """SELECT ROUND(SUM(oi.price), 2)
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.order_status = 'delivered'"""},
    {"id": "M10", "difficulty": "medium",
     "question": "Which customer state has the highest average payment_value per payment record, and what is that average, rounded to 2 decimals?",
     "gold_sql": """SELECT c.customer_state, ROUND(AVG(p.payment_value), 2)
                    FROM order_payments p
                    JOIN orders o ON p.order_id = o.order_id
                    JOIN customers c ON o.customer_id = c.customer_id
                    GROUP BY c.customer_state
                    ORDER BY AVG(p.payment_value) DESC LIMIT 1"""},

    # ---------- HARD (dates, percentages, traps) ----------
    {"id": "H1", "difficulty": "hard",
     "question": "What percentage of all orders have the status 'delivered'? Round to 2 decimals.",
     "gold_sql": "SELECT ROUND(100.0 * SUM(order_status = 'delivered') / COUNT(*), 2) FROM orders"},
    {"id": "H2", "difficulty": "hard",
     "question": "How many delivered orders arrived after their estimated delivery date?",
     "gold_sql": """SELECT COUNT(*) FROM orders
                    WHERE order_status = 'delivered'
                      AND order_delivered_customer_date > order_estimated_delivery_date"""},
    {"id": "H3", "difficulty": "hard",
     "question": "For delivered orders, what is the average number of days from purchase to delivery to the customer? Round to 1 decimal.",
     "gold_sql": """SELECT ROUND(AVG(julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)), 1)
                    FROM orders
                    WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL"""},
    {"id": "H4", "difficulty": "hard",
     "question": "Which month (format YYYY-MM, based on the order purchase date) had the highest total payment value, and what was that total, rounded to 2 decimals?",
     "gold_sql": """SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month, ROUND(SUM(p.payment_value), 2)
                    FROM orders o JOIN order_payments p ON o.order_id = p.order_id
                    GROUP BY month ORDER BY SUM(p.payment_value) DESC LIMIT 1"""},
    {"id": "H5", "difficulty": "hard",
     "question": "How many unique customers (real people, identified by customer_unique_id) placed more than one order?",
     "gold_sql": """SELECT COUNT(*) FROM (
                      SELECT c.customer_unique_id FROM orders o
                      JOIN customers c ON o.customer_id = c.customer_id
                      GROUP BY c.customer_unique_id
                      HAVING COUNT(DISTINCT o.order_id) > 1)"""},
    {"id": "H6", "difficulty": "hard",
     "question": "Among product categories with at least 100 items sold, which has the highest average item price? Give the English name and the average, rounded to 2 decimals.",
     "gold_sql": """SELECT t.product_category_name_english, ROUND(AVG(oi.price), 2) AS avg_price
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    JOIN category_translation t ON p.product_category_name = t.product_category_name
                    GROUP BY t.product_category_name_english
                    HAVING COUNT(*) >= 100
                    ORDER BY AVG(oi.price) DESC LIMIT 1"""},
    {"id": "H7", "difficulty": "hard",
     "question": "How many orders were paid using more than one distinct payment type (for example, credit card plus voucher)?",
     "gold_sql": """SELECT COUNT(*) FROM (
                      SELECT order_id FROM order_payments
                      GROUP BY order_id HAVING COUNT(DISTINCT payment_type) > 1)"""},

    # ---------- UNANSWERABLE (data does not contain the answer) ----------
    {"id": "U1", "difficulty": "unanswerable",
     "question": "What is the average age of our customers?", "gold_sql": None},
    {"id": "U2", "difficulty": "unanswerable",
     "question": "What was the profit margin on orders placed in 2017?", "gold_sql": None},
    {"id": "U3", "difficulty": "unanswerable",
     "question": "Which marketing channel brought in the most customers?", "gold_sql": None},
]