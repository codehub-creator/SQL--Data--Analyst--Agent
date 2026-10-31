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

results["E10"] = (round(items.freight_value.sum(), 2), 2251909.54)

oc = orders[["order_id", "customer_id"]].merge(customers[["customer_id", "customer_state"]], on="customer_id")

sp = items.merge(oc, on="order_id")
results["M4"] = (round(sp[sp.customer_state == "SP"].freight_value.mean(), 2), 15.15)

delivered_ids = orders.loc[orders.order_status == "delivered", "order_id"]
results["M9"] = (round(items[items.order_id.isin(delivered_ids)].price.sum(), 2), 13221498.11)

ps = pay.merge(oc, on="order_id").groupby("customer_state").payment_value.mean().round(2).sort_values()
results["M10"] = ((ps.index[-1], ps.iloc[-1]), ("PB", 248.33))

results["H7"] = (int((pay.groupby("order_id").payment_type.nunique() > 1).sum()), 2246)

d = orders[orders.order_status == "delivered"]
results["H2"] = (int((d.order_delivered_customer_date > d.order_estimated_delivery_date).sum()), 7826)
days = (d.order_delivered_customer_date - d.order_purchase_timestamp).dt.total_seconds() / 86400
results["H3"] = (round(days.mean(), 1), 12.6)

pm = pay.merge(orders[["order_id", "order_purchase_timestamp"]], on="order_id")
pm["month"] = pm.order_purchase_timestamp.dt.strftime("%Y-%m")
mt = pm.groupby("month").payment_value.sum()
results["H4"] = ((mt.idxmax(), round(mt.max(), 2)), ("2017-11", 1194882.8))

cat = items.merge(prods[["product_id", "product_category_name"]], on="product_id").merge(
    trans, on="product_category_name")
g = cat.groupby("product_category_name_english").price.agg(["count", "mean"])
g = g[g["count"] >= 100].sort_values("mean")
results["H6"] = ((g.index[-1], round(g["mean"].iloc[-1], 2)), ("computers", 1098.34))

oc2 = orders.merge(customers, on="customer_id")
results["H5"] = (int((oc2.groupby("customer_unique_id").order_id.nunique() > 1).sum()), 2997)
results["M8"] = (int((items.groupby("order_id").size() > 1).sum()), 9803)
results["M5"] = (int((orders.order_purchase_timestamp.dt.year == 2017).sum()), 45101)


def same(a, b):
    if isinstance(a, tuple):
        return all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)):
        return abs(float(a) - float(b)) < 0.01
    return a == b


for qid, (pandas_val, sql_val) in results.items():
    print(f"{'MATCH   ' if same(pandas_val, sql_val) else 'MISMATCH'} {qid:<4} pandas={pandas_val}  sql={sql_val}")