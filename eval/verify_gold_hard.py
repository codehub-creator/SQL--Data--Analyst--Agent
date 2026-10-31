from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parent.parent / "data"
orders = pd.read_csv(
    D / "olist_orders_dataset.csv",
    parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                 "order_estimated_delivery_date"],
)
customers = pd.read_csv(D / "olist_customers_dataset.csv")
items = pd.read_csv(D / "olist_order_items_dataset.csv")
pay = pd.read_csv(D / "olist_order_payments_dataset.csv")
prods = pd.read_csv(D / "olist_products_dataset.csv")
trans = pd.read_csv(D / "product_category_name_translation.csv")

results = {}  # id -> (pandas value, SQL gold value)

oc = orders[["order_id", "customer_id"]].merge(
    customers[["customer_id", "customer_state", "customer_unique_id"]], on="customer_id")

# X1: highest average total freight per order, by customer state
per_order = items.groupby("order_id").freight_value.sum().rename("f").reset_index().merge(oc, on="order_id")
s = per_order.groupby("customer_state").f.mean().sort_values()
results["X1"] = ((s.index[-1], round(s.iloc[-1], 2)), ("RR", 48.59))

# X2: % of delivered orders (with a delivery date) that were late
d = orders[(orders.order_status == "delivered") & orders.order_delivered_customer_date.notna()]
late = (d.order_delivered_customer_date > d.order_estimated_delivery_date).mean() * 100
results["X2"] = (round(late, 2), 8.11)

# Items joined to English category names
cat0 = items.merge(prods[["product_id", "product_category_name"]], on="product_id").merge(
    trans, on="product_category_name")

# X3: best-selling category among RJ customers
rj = cat0.merge(oc, on="order_id")
rj = rj[rj.customer_state == "RJ"].groupby("product_category_name_english").size().sort_values()
results["X3"] = ((rj.index[-1], int(rj.iloc[-1])), ("bed_bath_table", 1644))

# X4: largest month-over-month increase in orders during 2017
o17 = orders[orders.order_purchase_timestamp.dt.year == 2017]
m = o17.groupby(o17.order_purchase_timestamp.dt.strftime("%Y-%m")).size()
inc = m.diff().dropna()
results["X4"] = ((inc.idxmax(), int(inc.max())), ("2017-11", 2913))

# X5: % of 2017 customers (unique people) who also ordered in 2018
oc2 = orders.merge(customers[["customer_id", "customer_unique_id"]], on="customer_id")
yr = oc2.order_purchase_timestamp.dt.year
a = set(oc2.loc[yr == 2017, "customer_unique_id"])
b = set(oc2.loc[yr == 2018, "customer_unique_id"])
results["X5"] = (round(100 * len(a & b) / len(a), 2), 1.56)

# X6: top category by revenue and its share of all item revenue
rev = cat0.groupby("product_category_name_english").price.sum().sort_values()
results["X6"] = ((rev.index[-1], round(100 * rev.iloc[-1] / items.price.sum(), 2)), ("health_beauty", 9.26))

# X7: items whose product has no category
ip = items.merge(prods[["product_id", "product_category_name"]], on="product_id")
results["X7"] = (int(ip.product_category_name.isna().sum()), 1603)

# X8: orders placed on a weekend (Mon=0 ... Sat=5, Sun=6)
results["X8"] = (int((orders.order_purchase_timestamp.dt.dayofweek >= 5).sum()), 22847)

# X9: % of credit card payments with more than one installment
cc = pay[pay.payment_type == "credit_card"]
results["X9"] = (round(100 * (cc.payment_installments > 1).mean(), 2), 66.85)


def same(x, y):
    if isinstance(x, tuple):
        return all(same(p, q) for p, q in zip(x, y))
    if isinstance(x, (int, float)):
        return abs(float(x) - float(y)) < 0.01
    return x == y


for qid, (pandas_val, sql_val) in results.items():
    print(f"{'MATCH   ' if same(pandas_val, sql_val) else 'MISMATCH'} {qid:<3} pandas={pandas_val}  sql={sql_val}")