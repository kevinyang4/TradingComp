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
LOOKBACK_TAIL = 60 # 3 months (skewness & kurtosis)
TOP_N = 5
CAPITAL = 100_000

# ===============================
# DOWNLOAD DATA
# ===============================

print("Downloading price data...")
prices = yf.download(UNIVERSE, period="1y")["Adj Close"]
prices = prices.dropna()

# ===============================
# MOMENTUM
# ===============================

momentum = prices.iloc[-1] / prices.iloc[-LOOKBACK_MOMENTUM] - 1
momentum = momentum.sort_values(ascending=False)

winners = momentum.head(TOP_N).index.tolist()

print("\nTop momentum stocks:")
print(momentum.head(TOP_N))

# ===============================
# VOLATILITY / SKEWNESS / KURTOSIS
# ===============================

returns = prices.pct_change().dropna()
vol = returns[winners].tail(LOOKBACK_VOL).std() * np.sqrt(252)
tail_window = returns[winners]. tail(LOOKBACK_TAIL)
skew = tail_window.skew()
kurt = tail_window.kurt()

neg_skew = (-skew).clip(lower=0) #penalizing
pos_kurt = kurt.clip(lower=0)

k90 = pos_kurt.quantile(0.90)
k90 = neg_skew.quantile(0.90)

#target each tail component to contribute ~0.5 at the 90th percentile
alpha_kurt = 0.5 / k90 if k90 > 0 else 0.0
alpha_skew = 0.5 / s90 if s90 > 0 else 0.0

print("Suggested ALPHA_KURT:", alpha_kurt)
print("Suggested ALPHA_SKEW:", alpha_skew)

penalty = 1 + alpha_skew * pos_kurt + alpha_kurt * neg_skew

effective_risk = vol * penalty

# ===============================
# VOL-SCALED WEIGHTS
# ===============================

inv_vol = 1 / effective_risk
weights = inv_vol / inv_vol.sum()

print("\nVolatility-scaled weights:")
print(weights)

# ===============================
# POSITION SIZES
# ===============================

latest_prices = prices.iloc[-1][winners]
target_dollars = weights * CAPITAL
target_shares = (target_dollars / latest_prices).astype(int)

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
