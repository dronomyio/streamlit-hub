import math
from decimal import Decimal, getcontext
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Uniswap V3 Milestone 1 Explorer", layout="wide")

# ---------- Helpers ----------
Q96_INT = 2**96
Q96_DEC = Decimal(2) ** 96

def tick_from_price(P: float) -> int:
    # tick = floor(log_{1.0001}(P))
    return math.floor(math.log(P) / math.log(1.0001))

def sqrtP_from_tick(tick: int) -> float:
    # sqrtP = sqrt(1.0001^tick) = 1.0001^(tick/2)
    return 1.0001 ** (tick / 2.0)

def sqrtPriceX96_float(P: float) -> int:
    # book-style: int(sqrt(P) * 2^96) using float sqrt
    return int(math.sqrt(P) * Q96_INT)

def sqrtPriceX96_decimal(P: Decimal, prec: int = 80) -> int:
    # true high-precision: floor(sqrt(P) * 2^96)
    getcontext().prec = prec
    return int((P.sqrt() * Q96_DEC))

def sqrtPriceX96_tick_quantized(P: float) -> tuple[int, int, float]:
    # price -> tick -> sqrtP -> sqrtPriceX96
    t = tick_from_price(P)
    sp = sqrtP_from_tick(t)
    return t, int(sp * Q96_INT), sp

def liquidity0(amount0_wei: int, sqrtP_a: int, sqrtP_b: int) -> float:
    # L0 = amount0 * (sqrtPa*sqrtPb/Q96) / (sqrtPb - sqrtPa)
    # This matches typical V3 formulas with Q96 scaling
    if sqrtP_a > sqrtP_b:
        sqrtP_a, sqrtP_b = sqrtP_b, sqrtP_a
    return (amount0_wei * (sqrtP_a * sqrtP_b) / Q96_INT) / (sqrtP_b - sqrtP_a)

def liquidity1(amount1_wei: int, sqrtP_a: int, sqrtP_b: int) -> float:
    # L1 = amount1 * Q96 / (sqrtPb - sqrtPa)
    if sqrtP_a > sqrtP_b:
        sqrtP_a, sqrtP_b = sqrtP_b, sqrtP_a
    return amount1_wei * Q96_INT / (sqrtP_b - sqrtP_a)

def format_int(n: int) -> str:
    return f"{n:,}"

def format_big_diff(a: int, b: int) -> str:
    d = a - b
    sign = "+" if d >= 0 else "-"
    return f"{sign}{abs(d):,}"

# ---------- UI ----------
st.title("Uniswap V3 Milestone 1 — Interactive Price/Tick/SqrtPriceX96 + Liquidity")

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("1) Token orientation (this flips the price)")
    token0 = st.selectbox("token0", ["ETH", "USDC"])
    token1 = "USDC" if token0 == "ETH" else "ETH"
    st.write(f"token1 is **{token1}**.")
    st.caption("Uniswap defines price as P = token1/token0 (not “USD per ETH” unless token0/token1 align).")

    st.subheader("2) Set spot price and range")
    display_mode = st.radio(
        "How are you entering the price?",
        ["Human price (USDC per ETH)", "Raw Uniswap price P = token1/token0"],
        index=0
    )

    # Default values similar to the book
    human_price = st.number_input("Human price (USDC per ETH)", min_value=0.000001, value=5000.0, step=1.0)
    lower_human = st.number_input("Lower bound (USDC per ETH)", min_value=0.000001, value=4545.0, step=1.0)
    upper_human = st.number_input("Upper bound (USDC per ETH)", min_value=0.000001, value=5500.0, step=1.0)

    # Convert to Uniswap P = token1/token0
    # If token0=ETH, token1=USDC => P = USDC/ETH = human_price (matches intuition)
    # If token0=USDC, token1=ETH => P = ETH/USDC = 1/human_price (inverted)
    def human_to_P(h: float) -> float:
        if token0 == "ETH" and token1 == "USDC":
            return h
        else:
            return 1.0 / h

    P_cur = human_to_P(human_price)
    P_low = human_to_P(lower_human)
    P_upp = human_to_P(upper_human)

    if display_mode == "Raw Uniswap price P = token1/token0":
        st.info("You selected Raw Uniswap price mode. The app is still using your human inputs above, but showing raw P below.")
    st.write("Raw Uniswap prices (P = token1/token0):")
    st.write(f"- P_cur = **{P_cur:.12g}**")
    st.write(f"- P_low = **{P_low:.12g}**")
    st.write(f"- P_upp = **{P_upp:.12g}**")

    st.subheader("3) Choose deposit amounts")
    st.caption("This mirrors the milestone’s example. Amounts are in token units; we convert to 18-decimal 'wei-like' for consistency.")
    amount0 = st.number_input(f"Amount of token0 ({token0})", min_value=0.0, value=1.0, step=0.1)
    amount1 = st.number_input(f"Amount of token1 ({token1})", min_value=0.0, value=5000.0, step=100.0)
    decimals = st.number_input("Assume decimals for both tokens (for demo)", min_value=0, max_value=18, value=18, step=1)

with right:
    st.subheader("A) Price → Tick → sqrtP and sqrtPriceX96")
    # Make sure bounds ordered by numeric value of P
    pmin, pmax = sorted([P_low, P_upp])
    if not (pmin <= P_cur <= pmax):
        st.warning("Current price is outside your chosen range (in raw Uniswap P). That’s allowed, but liquidity math changes by region.")

    # Current
    tick_cur = tick_from_price(P_cur)
    tick_low = tick_from_price(pmin)
    tick_upp = tick_from_price(pmax)

    # sqrtPriceX96 by float & decimal
    sqrtX96_cur_float = sqrtPriceX96_float(P_cur)
    sqrtX96_cur_dec = sqrtPriceX96_decimal(Decimal(str(P_cur)))

    # Tick-quantized
    t_q, sqrtX96_cur_tick, sqrtP_cur_tick = sqrtPriceX96_tick_quantized(P_cur)

    # Also show exact (Decimal) vs float difference like the mismatch you observed
    st.markdown("**Current price computations:**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("tick (floor log base 1.0001)", f"{tick_cur}")
        st.caption("tick = floor(log_{1.0001}(P))")
    with c2:
        st.metric("sqrtPriceX96 (float sqrt)", format_int(sqrtX96_cur_float))
        st.caption("int(math.sqrt(P) * 2^96) — matches many tutorials")
    with c3:
        st.metric("sqrtPriceX96 (Decimal sqrt)", format_int(sqrtX96_cur_dec))
        st.caption("floor(sqrt(P) * 2^96) with high precision")

    st.write("Differences:")
    st.write(f"- float − Decimal = **{format_big_diff(sqrtX96_cur_float, sqrtX96_cur_dec)}**")
    st.write(f"- tick-quantized tick = **{t_q}**")
    st.write(f"- sqrtPriceX96(tick) ≈ **{format_int(sqrtX96_cur_tick)}**")
    st.caption("Uniswap core effectively operates on the tick grid; the 'price' you initialize is quantized to that grid.")

    st.divider()

    st.subheader("B) Compute sqrtPriceX96 at range bounds")
    sqrtX96_low = sqrtPriceX96_float(pmin)
    sqrtX96_upp = sqrtPriceX96_float(pmax)

    st.write(f"sqrtPriceX96(low)  = {format_int(sqrtX96_low)}")
    st.write(f"sqrtPriceX96(cur)  = {format_int(sqrtX96_cur_float)}")
    st.write(f"sqrtPriceX96(upp)  = {format_int(sqrtX96_upp)}")

    st.write(f"ticks: low={tick_low}, cur={tick_cur}, upp={tick_upp}")

    st.divider()

    st.subheader("C) Liquidity L0 / L1 (Milestone 1 style)")
    # Convert token amounts to "wei-like"
    scale = 10 ** int(decimals)
    amount0_int = int(amount0 * scale)
    amount1_int = int(amount1 * scale)

    # Use current and bounds (like the milestone)
    # For L0: use [cur, upp]
    # For L1: use [low, cur]
    liq0 = liquidity0(amount0_int, sqrtX96_cur_float, sqrtX96_upp)
    liq1 = liquidity1(amount1_int, sqrtX96_cur_float, sqrtX96_low)

    L = int(min(liq0, liq1))
    limiting = "token0-side (L0)" if liq0 < liq1 else "token1-side (L1)"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("L0 (from token0)", f"{int(liq0):,}")
        st.caption("Uses amount0 and (cur, upper)")
    with c2:
        st.metric("L1 (from token1)", f"{int(liq1):,}")
        st.caption("Uses amount1 and (lower, cur)")
    with c3:
        st.metric("Chosen L = min(L0, L1)", f"{L:,}")
        st.caption(f"Limiting side: {limiting}")

    st.caption("These formulas are simplified and mirror Milestone 1’s approach; production contracts use careful rounding (mulDiv) and tick math.")

# ---------- Plot ----------
#st.subheader("Visualization: Price range & tick quantization")
#fig = plt.figure()
#ax = fig.add_subplot(111)
#
## Use log scale for price axis to mimic tick/log nature
#prices = np.array([pmin, P_cur, pmax])
#labels = ["low", "cur", "upp"]
#
#ax.set_xscale("log")
#ax.hlines(1, pmin, pmax, linewidth=6)
##ax.scatter(prices, np.ones_like(prices), s=80)
#
#for p, lab in zip(prices, labels):
#    ax.text(p, 1.02, f"{lab}\n{p:.6g}", ha="center", va="bottom")
#
## Show quantized current price (via tick)
#p_quant = 1.0001 ** tick_from_price(P_cur)
#ax.scatter([p_quant], [1], marker="x", s=150)
#ax.text(p_quant, 0.98, f"tick price\n{p_quant:.6g}", ha="center", va="top")
#
#ax.set_yticks([])
#ax.set_xlabel("Raw Uniswap price P = token1/token0 (log scale)")
#st.pyplot(fig)

# ---------- Better Plot ----------
import plotly.graph_objects as go

st.subheader("Interactive: Price range & tick quantization (Milestone 1)")

# Ensure valid ordering
pmin, pmax = sorted([P_low, P_upp])

if pmin <= 0:
    st.error("Invalid price for log-scale plot (pmin <= 0).")
else:
    # Slider for current price (this is the interaction)
    P_cur_slider = st.slider(
        "Move current price (raw Uniswap P = token1/token0)",
        min_value=float(pmin),
        max_value=float(pmax),
        value=float(P_cur),
        step=(pmax - pmin) / 500,
        format="%.6g"
    )

    # Tick snapping
    tick_cur = tick_from_price(P_cur_slider)
    P_tick = 1.0001 ** tick_cur

    # Build interactive plot
    fig = go.Figure()

    # Range bounds
    fig.add_vline(x=pmin, line_dash="dash", line_width=2, annotation_text="lower")
    fig.add_vline(x=pmax, line_dash="dash", line_width=2, annotation_text="upper")

    # Current (continuous) price
    fig.add_vline(
        x=P_cur_slider,
        line_width=3,
        annotation_text="current",
        annotation_position="top"
    )

    # Tick-quantized price
    fig.add_vline(
        x=P_tick,
        line_dash="dot",
        line_width=3,
        annotation_text=f"tick {tick_cur}",
        annotation_position="bottom"
    )

    fig.update_layout(
        xaxis_type="log",
        xaxis_title="Price P = token1 / token0 (log scale)",
        yaxis_visible=False,
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        title="Continuous price vs tick-quantized price"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Numeric feedback (VERY important for intuition)
    st.markdown("### Live values")
    st.write({
        "current price (continuous)": P_cur_slider,
        "tick": tick_cur,
        "tick-quantized price": P_tick,
        "tick error (P_tick - P_cur)": P_tick - P_cur_slider
    })


#st.divider()

#st.subheader("What to try (to make Milestone 1 'click')")
#st.markdown(
"""
- Flip **token0/token1** and watch how **P** becomes **1/price** — this is the biggest source of confusion in many tutorials.
- Compare **float sqrtPriceX96** vs **Decimal sqrtPriceX96** to see why the book’s integer can be “off” from exact math.
- Watch **tick quantization**: current price snaps to a tick grid. This is why “exact” price initialization is not truly continuous.
- Change the range width and amounts to see when **L0** or **L1** becomes limiting.
"""
#)

