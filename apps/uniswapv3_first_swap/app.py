import math
import numpy as np
import streamlit as st

Q96 = 2**96

# ----------------------------
# Uniswap V3-ish helper math
# ----------------------------

def sqrtp_x96_to_price(sqrtp_x96: int) -> float:
    s = sqrtp_x96 / Q96
    return s * s

def price_to_sqrtp_x96(price: float) -> int:
    return int(math.sqrt(price) * Q96)

def price_to_tick(price: float) -> int:
    if price <= 0:
        return 0
    return int(math.floor(math.log(price) / math.log(1.0001)))

def tick_to_price(tick: int) -> float:
    return 1.0001 ** tick

def tick_to_sqrtp_x96(tick: int) -> int:
    return price_to_sqrtp_x96(tick_to_price(tick))

def calc_amount1(L: int, sqrtp_b_x96: int, sqrtp_a_x96: int) -> int:
    # amount1 = L * (sqrtP_b - sqrtP_a) / Q96
    if sqrtp_b_x96 < sqrtp_a_x96:
        sqrtp_b_x96, sqrtp_a_x96 = sqrtp_a_x96, sqrtp_b_x96
    return (L * (sqrtp_b_x96 - sqrtp_a_x96)) // Q96

def calc_amount0(L: int, sqrtp_b_x96: int, sqrtp_a_x96: int) -> int:
    # amount0 = L * (sqrtP_b - sqrtP_a) / (sqrtP_b * sqrtP_a) * Q96
    if sqrtp_b_x96 < sqrtp_a_x96:
        sqrtp_b_x96, sqrtp_a_x96 = sqrtp_a_x96, sqrtp_b_x96
    num = L * (sqrtp_b_x96 - sqrtp_a_x96) * Q96
    den = sqrtp_b_x96 * sqrtp_a_x96
    return num // den

def swap_token1_in_for_token0_out_single_range(L: int, sqrtp_cur_x96: int, amount1_in: int):
    """
    Single active range swap: token1 in -> token0 out (price increases)
    ΔsqrtP = (amount1_in * Q96) / L
    sqrtP_next = sqrtP_cur + ΔsqrtP
    amount0_out = calc_amount0(L, sqrtP_next, sqrtP_cur)
    """
    if L <= 0:
        raise ValueError("L must be > 0")
    if sqrtp_cur_x96 <= 0:
        raise ValueError("sqrtP must be > 0")
    if amount1_in < 0:
        raise ValueError("amount1_in must be >= 0")

    d_sqrtp = (amount1_in * Q96) // L
    sqrtp_next = sqrtp_cur_x96 + d_sqrtp
    amount0_out = calc_amount0(L, sqrtp_next, sqrtp_cur_x96)
    return sqrtp_next, amount0_out


# ----------------------------
# UI helpers
# ----------------------------

def to_units(raw: int, decimals: int) -> float:
    return raw / (10 ** decimals)

def fmt_int(n: int) -> str:
    # readable, but safe for copy/paste
    return f"{n:,}".replace(",", "_")

def fmt_price(p: float) -> str:
    if p == 0:
        return "0"
    if p >= 1:
        return f"{p:,.6f}"
    return f"{p:.10f}"


# ----------------------------
# Streamlit App
# ----------------------------

st.set_page_config(page_title="Uniswap V3 First Swap (Interactive)", layout="wide")
st.title("Uniswap V3 “First Swap” — Single Range Simulator")

st.markdown(
    """
This simulator shows the **Milestone 1 / first swap** behavior in a *single active range*:
**liquidity `L` stays constant** while a swap moves **`sqrtP`**, changing **price** and **tick**.
"""
)

with st.sidebar:
    st.header("Preset")

    preset = st.selectbox(
        "Choose a preset",
        [
            "Book-like feel (price ~5000, token1 in = 42, large L)",
            "Tiny pool (big price impact)",
            "Huge pool (tiny price impact)",
            "Custom",
        ],
    )

    # Defaults (human-scale)
    if preset == "Book-like feel (price ~5000, token1 in = 42, large L)":
        price0 = 5000.0
        L_log10 = 24
        token1_in_human_default = 42.0
        lower_price = 4500.0
        upper_price = 5600.0
    elif preset == "Tiny pool (big price impact)":
        price0 = 2000.0
        L_log10 = 18
        token1_in_human_default = 42.0
        lower_price = 1500.0
        upper_price = 2600.0
    elif preset == "Huge pool (tiny price impact)":
        price0 = 5000.0
        L_log10 = 28
        token1_in_human_default = 42.0
        lower_price = 4500.0
        upper_price = 5600.0
    else:
        price0 = 5000.0
        L_log10 = 24
        token1_in_human_default = 42.0
        lower_price = 4500.0
        upper_price = 5600.0

    st.header("Tokens & units")

    token1_symbol = st.text_input("Token1 symbol", value="USDC")
    token0_symbol = st.text_input("Token0 symbol", value="ETH")

    # Common: USDC 6, ETH 18 — but keep editable.
    token1_decimals = st.selectbox("Token1 decimals", [6, 18], index=0)
    token0_decimals = st.selectbox("Token0 decimals", [18, 6], index=0)

    st.header("Pool state (human controls)")

    price_cur_ui = st.number_input(
        f"Current price ({token1_symbol} per {token0_symbol})",
        min_value=1e-12,
        value=float(price0),
        step=1.0,
        format="%.6f",
    )

    L_log10_ui = st.slider("Liquidity scale log10(L)", min_value=6, max_value=32, value=int(L_log10))
    L = 10 ** int(L_log10_ui)

    st.header("Range (single active range)")
    use_price_range = st.checkbox("Set range by price (recommended)", value=True)

    if use_price_range:
        lower_price_ui = st.number_input("Lower price", min_value=1e-12, value=float(lower_price), step=1.0, format="%.6f")
        upper_price_ui = st.number_input("Upper price", min_value=1e-12, value=float(upper_price), step=1.0, format="%.6f")
        if lower_price_ui >= upper_price_ui:
            st.error("Lower price must be < upper price")
        lower_tick = price_to_tick(lower_price_ui)
        upper_tick = price_to_tick(upper_price_ui)
    else:
        lower_tick = st.number_input("Lower tick", value=int(price_to_tick(lower_price)), step=1)
        upper_tick = st.number_input("Upper tick", value=int(price_to_tick(upper_price)), step=1)
        if lower_tick >= upper_tick:
            st.error("Lower tick must be < upper tick")

    st.header("Swap input")
    token1_in_human = st.number_input(
        f"{token1_symbol} in (human units)",
        min_value=0.0,
        value=float(token1_in_human_default),
        step=1.0,
        format="%.6f",
    )

    do_clamp = st.checkbox("Clamp swap to stay inside range (educational)", value=True)

# Convert human inputs to raw ints
sqrtp_cur_x96 = price_to_sqrtp_x96(price_cur_ui)
amount1_in_raw = int(token1_in_human * (10 ** token1_decimals))

sqrtp_lower_x96 = tick_to_sqrtp_x96(int(lower_tick))
sqrtp_upper_x96 = tick_to_sqrtp_x96(int(upper_tick))

# Derived current tick from current price
tick_cur = price_to_tick(price_cur_ui)

# Perform swap
try:
    sqrtp_next_x96, amount0_out_raw = swap_token1_in_for_token0_out_single_range(L, sqrtp_cur_x96, amount1_in_raw)
except Exception as e:
    st.error(f"Swap computation error: {e}")
    st.stop()

clamped = False
if do_clamp:
    if sqrtp_next_x96 < sqrtp_lower_x96:
        sqrtp_next_x96 = sqrtp_lower_x96
        clamped = True
    if sqrtp_next_x96 > sqrtp_upper_x96:
        sqrtp_next_x96 = sqrtp_upper_x96
        clamped = True
    # recompute output for clamped end
    amount0_out_raw = calc_amount0(L, sqrtp_next_x96, sqrtp_cur_x96)

price_next = sqrtp_x96_to_price(sqrtp_next_x96)
tick_next = price_to_tick(price_next)

# If clamped, compute implied token1 used to reach boundary; otherwise = input.
if clamped:
    amount1_used_raw = calc_amount1(L, sqrtp_next_x96, sqrtp_cur_x96)
else:
    amount1_used_raw = amount1_in_raw

# Human outputs
amount0_out_human = to_units(amount0_out_raw, token0_decimals)
amount1_used_human = to_units(amount1_used_raw, token1_decimals)

# ----------------------------
# Layout: state + results
# ----------------------------

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Pool state (computed)")
    st.write(f"**Current price:** {fmt_price(price_cur_ui)} {token1_symbol}/{token0_symbol}")
    st.write(f"**Current tick (approx):** {tick_cur:,}")
    st.write(f"**Liquidity L:** 10^{L_log10_ui}  (raw: `{fmt_int(L)}`)")
    st.write(f"**Current sqrtP (X96):** `{fmt_int(sqrtp_cur_x96)}`")

    st.markdown("---")
    st.subheader("Range")
    st.write(f"**Lower tick:** {int(lower_tick):,}  → price ≈ {fmt_price(tick_to_price(int(lower_tick)))}")
    st.write(f"**Upper tick:** {int(upper_tick):,}  → price ≈ {fmt_price(tick_to_price(int(upper_tick)))}")
    if not (sqrtp_lower_x96 <= sqrtp_cur_x96 <= sqrtp_upper_x96):
        st.warning("Current price is outside the selected range; a single-range demo typically assumes current is inside.")

with col2:
    st.subheader("Swap result (token1 in → token0 out)")
    if clamped:
        st.info("Swap was **clamped** to the range boundary. Shown amounts reflect the boundary move.")

    st.write(f"**New price:** {fmt_price(price_next)} {token1_symbol}/{token0_symbol}")
    st.write(f"**New tick (approx):** {tick_next:,}")
    st.write(f"**New sqrtP (X96):** `{fmt_int(sqrtp_next_x96)}`")

    st.markdown("### Amounts")
    st.write(f"**{token1_symbol} in (used):** {amount1_used_human:,.12f}  (raw: `{fmt_int(amount1_used_raw)}`)")
    st.write(f"**{token0_symbol} out:** {amount0_out_human:,.12f}  (raw: `{fmt_int(amount0_out_raw)}`)")

    st.caption("Single-range model: L constant; sqrtP increases by ΔsqrtP ≈ amount1_in·Q96 / L (token1-in direction).")

st.markdown("---")

# ----------------------------
# Visualization
# ----------------------------

st.subheader("Visualization: price over the chosen tick range")

ticks = np.linspace(int(lower_tick), int(upper_tick), num=240, dtype=int)
prices = np.array([tick_to_price(int(t)) for t in ticks], dtype=float)

# Simple line chart (index vs price)
st.line_chart(prices)

def nearest_index(arr, value):
    return int(np.argmin(np.abs(arr - value)))

i_cur = nearest_index(prices, price_cur_ui)
i_next = nearest_index(prices, price_next)

st.write(
    f"Approx markers: **current** index {i_cur} (~tick {ticks[i_cur]}), "
    f"**next** index {i_next} (~tick {ticks[i_next]})."
)

st.markdown(
    """
### Try these interactive experiments
- **Increase Token1 in** (e.g., 42 → 420): you should see a larger tick jump and higher price impact.
- **Increase log10(L)**: price impact should shrink dramatically.
- **Narrow the range** (bring lower/upper closer): you’ll hit the boundary more easily (clamping shows it clearly).

### What this demo intentionally does NOT include (yet)
- Multi-range / crossing ticks (where L changes as you move across ranges)
- Fees (0.05%/0.3%/1%) and exact rounding behavior
- Exact Uniswap v3 TickMath / SqrtPriceMath solidity-equivalent rounding
"""
)

