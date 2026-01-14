# ===============================
# Cross-Sectional Momentum + Volatility Scaling
# Interactive Brokers Paper Trading
# ===============================

import yfinance as yf
import pandas as pd
import numpy as np
import random
from ib_insync import IB, Stock, MarketOrder

# ===============================
# CONFIG
# ===============================

UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA",
    "JPM","XOM","UNH","JNJ","V","PG","HD","AVGO",
    "KO","PEP","BAC","WMT","DIS"
]

LOOKBACK_MOMENTUM = 126   # 6 months
LOOKBACK_VOL = 20        # 1 month
N_LONG = 5
N_SHORT = 5
CAPITAL = 100_000

# ===============================
# DOWNLOAD DATA
# ===============================

print("Downloading price data...")
prices = yf.download(UNIVERSE, period="1y")["Close"]
prices = prices.dropna()

# ===============================
# MOMENTUM
# ===============================

momentum = prices.iloc[-1] / prices.iloc[-LOOKBACK_MOMENTUM] - 1
momentum = momentum.dropna().sort_values(ascending=False)

longs = momentum.head(N_LONG).index.tolist()
shorts = momentum.tail(N_SHORT).index.tolist()

print("\nTop momentum (LONG):")
print(momentum.loc[longs])

print("\nBottom momentum (SHORT):")
print(momentum.loc[shorts])

# ===============================
# VOLATILITY
# ===============================

returns = prices.pct_change().dropna()
vol_long = returns[longs].tail(LOOKBACK_VOL).std() * np.sqrt(252)
vol_short = returns[shorts].tail(LOOKBACK_VOL).std() * np.sqrt(252)

# ===============================
# VOL-SCALED WEIGHTS
# ===============================

inv_vol_long = 1/vol_long
inv_vol_short = 1/vol_short

den = inv_vol_long.sum() + inv_vol_short.sum()

w_long  = inv_vol_long / den
w_short = inv_vol_short / den

gross_budget = CAPITAL  # total gross you want deployed

target_long_dollars  = w_long  * gross_budget
target_short_dollars = w_short * gross_budget

print("\nTotal long weight:", float(w_long.sum()))
print("Total short weight:", float(w_short.sum()))
print("Implied net exposure (long - short):", float(w_long.sum() - w_short.sum()))

# ===============================
# POSITION SIZES
# ===============================

latest_prices_long = prices.iloc[-1][longs]
latest_prices_short = prices.iloc[-1][shorts]

target_long_shares = (target_long_dollars / latest_prices_long).astype(int)
target_short_shares = (target_short_dollars / latest_prices_short).astype(int)

target_short_shares = -target_short_shares

# Combine into one Series
target_shares = pd.concat([target_long_shares, target_short_shares])

# ===============================
# BUILD ORDERS
# ===============================

orders_df = pd.DataFrame({
    "Ticker": target_shares.index,
    "Qty": target_shares.values
})

orders_df["Action"] = np.where(orders_df["Qty"] > 0, "BUY", "SELL")
orders_df["Qty"] = orders_df["Qty"].abs()
orders_df = orders_df[orders_df["Qty"] > 0]

print("\nOrders to send:")
print(orders_df)

# ===============================
# INTERACTIVE BROKERS
# ===============================

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=1, timeout=30)

print("\nORDRES À ENVOYER (PAPER):")
for _, row in orders_df.iterrows():
    print(row["Action"], row["Qty"], row["Ticker"])

confirm = input("\nTape YES pour envoyer à IB PAPER: ")
if confirm != "YES":
    print("Annulé")
    ib.disconnect()
    raise SystemExit

for _, row in orders_df.iterrows():
    contract = Stock(row["Ticker"], "SMART", "USD")
    ib.qualifyContracts(contract)
    order = MarketOrder(row["Action"], int(row["Qty"]))
    ib.placeOrder(contract, order)

print("\nOrdres envoyés (paper)")
ib.disconnect()
