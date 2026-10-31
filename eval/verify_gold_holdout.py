from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parent.parent / "data"
orders = pd.read_csv(
    D / "olist_orders_dataset.csv",
    parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                 "order_estimated_delivery_date"],
)
customers = pd.read_csv(D / "olist_customers_dataset.csv")

# Z1: largest month-over-month drop in 2018
o18 = orders[orders.order_purchase_timestamp.dt.year == 2018]
m = o18.groupby(o18.order_purchase_timestamp.dt.strftime("%Y-%m")).size()
drop = (-m.diff()).dropna()
print("Z1 pandas:", (drop.idxmax(), int(drop.max())))

# Z2: state with the highest late-delivery percentage (min 500 delivered orders)
d = orders[(orders.order_status == "delivered") & orders.order_delivered_customer_date.notna()]
d = d.merge(customers[["customer_id", "customer_state"]], on="customer_id")
d["late"] = d.order_delivered_customer_date > d.order_estimated_delivery_date
g = d.groupby("customer_state").late.agg(["mean", "size"])
g = g[g["size"] >= 500].sort_values("mean")
print("Z2 pandas:", (g.index[-1], round(100 * g["mean"].iloc[-1], 2)))