import math
import streamlit as st
from dataclasses import dataclass
from typing import Dict, Tuple, List

# -----------------------------
# Fixed-point helpers (for display/math consistency)
# -----------------------------
Q96 = 2**96

def price_to_tick(price: float) -> int:
    if price <= 0:
        return 0
    return int(math.floor(math.log(price) / math.log(1.0001)))

def tick_to_price(tick: int) -> float:
    return 1.0001 ** tick

def tick_to_sqrtp_x96(tick: int) -> int:
    return int(math.sqrt(tick_to_price(tick)) * Q96)

def sqrtp_x96_to_price(sqrtp_x96: int) -> float:
    s = sqrtp_x96 / Q96
    return s * s

def fmt_price(p: float) -> str:
    if p >= 1:
        return f"{p:,.6f}"
    return f"{p:.10f}"

# Uniswap-v3-ish single-range deltas
def amount1_delta(L: int, sqrtp_b_x96: int, sqrtp_a_x96: int) -> int:
    # amount1 = L * (sqrtPb - sqrtPa) / Q96
    if sqrtp_b_x96 < sqrtp_a_x96:
        sqrtp_b_x96, sqrtp_a_x96 = sqrtp_a_x96, sqrtp_b_x96
    return (L * (sqrtp_b_x96 - sqrtp_a_x96)) // Q96

def amount0_delta(L: int, sqrtp_b_x96: int, sqrtp_a_x96: int) -> int:
    # amount0 = L * (sqrtPb - sqrtPa) / (sqrtPb * sqrtPa) * Q96
    if sqrtp_b_x96 < sqrtp_a_x96:
        sqrtp_b_x96, sqrtp_a_x96 = sqrtp_a_x96, sqrtp_b_x96
    num = L * (sqrtp_b_x96 - sqrtp_a_x96) * Q96
    den = sqrtp_b_x96 * sqrtp_a_x96
    return num // den


# -----------------------------
# Simple ERC20-like token ledger
# -----------------------------
class Token:
    def __init__(self, symbol: str, decimals: int):
        self.symbol = symbol
        self.decimals = decimals
        self.bal: Dict[str, int] = {}              # address -> raw int
        self.allow: Dict[Tuple[str, str], int] = {} # (owner, spender) -> raw int

    def raw(self, human: float) -> int:
        return int(human * (10 ** self.decimals))

    def human(self, raw_amt: int) -> float:
        return raw_amt / (10 ** self.decimals)

    def balance_of(self, addr: str) -> int:
        return self.bal.get(addr, 0)

    def mint(self, addr: str, raw_amt: int):
        self.bal[addr] = self.balance_of(addr) + raw_amt

    def approve(self, owner: str, spender: str, raw_amt: int):
        self.allow[(owner, spender)] = raw_amt

    def allowance(self, owner: str, spender: str) -> int:
        return self.allow.get((owner, spender), 0)

    def transfer(self, sender: str, to: str, raw_amt: int):
        if raw_amt < 0:
            raise ValueError("transfer amount < 0")
        if self.balance_of(sender) < raw_amt:
            raise ValueError(f"{self.symbol}: insufficient balance")
        self.bal[sender] -= raw_amt
        self.bal[to] = self.balance_of(to) + raw_amt

    def transfer_from(self, spender: str, owner: str, to: str, raw_amt: int):
        """
        spender pulls from owner based on allowance (like ERC20 transferFrom).
        """
        if raw_amt < 0:
            raise ValueError("transferFrom amount < 0")
        allowed = self.allowance(owner, spender)
        if allowed < raw_amt:
            raise ValueError(f"{self.symbol}: allowance too low (allowed={allowed}, need={raw_amt})")
        if self.balance_of(owner) < raw_amt:
            raise ValueError(f"{self.symbol}: owner balance too low")
        # decrement allowance + move funds
        self.allow[(owner, spender)] = allowed - raw_amt
        self.bal[owner] -= raw_amt
        self.bal[to] = self.balance_of(to) + raw_amt


# -----------------------------
# CallbackData (book concept)
# -----------------------------
@dataclass
class CallbackData:
    token0_symbol: str
    token1_symbol: str
    payer: str


# -----------------------------
# Pool + Manager simulation
# -----------------------------
class Pool:
    """
    Single pool with:
      - token0/token1
      - current sqrtP
      - one active range (lowerTick/upperTick) and liquidity L (we treat as constant for swaps)
    """
    def __init__(self, address: str, token0: Token, token1: Token, price_init: float):
        self.address = address
        self.token0 = token0
        self.token1 = token1
        self.sqrtp_x96 = int(math.sqrt(price_init) * Q96)
        self.lower_tick = price_to_tick(price_init * 0.91)  # default-ish
        self.upper_tick = price_to_tick(price_init * 1.10)
        self.L = 0  # active liquidity

    def info(self):
        return {
            "price": sqrtp_x96_to_price(self.sqrtp_x96),
            "tick": price_to_tick(sqrtp_x96_to_price(self.sqrtp_x96)),
            "lower_tick": self.lower_tick,
            "upper_tick": self.upper_tick,
            "L": self.L,
        }

    def set_range(self, lower_tick: int, upper_tick: int):
        if lower_tick >= upper_tick:
            raise ValueError("lower_tick must be < upper_tick")
        self.lower_tick = lower_tick
        self.upper_tick = upper_tick

    def _required_amounts_for_liquidity(self, L_add: int) -> Tuple[int, int]:
        """
        Standard single-range amounts when current price is inside [lower, upper]:
          amount0 = L * (sqrtU - sqrtC) / (sqrtU * sqrtC) * Q96
          amount1 = L * (sqrtC - sqrtL) / Q96
        """
        sqrtL = tick_to_sqrtp_x96(self.lower_tick)
        sqrtU = tick_to_sqrtp_x96(self.upper_tick)
        sqrtC = self.sqrtp_x96

        if not (sqrtL <= sqrtC <= sqrtU):
            # For this milestone-style demo, keep it simple:
            raise ValueError("Current price must be inside the range for this simplified mint.")

        amt0 = amount0_delta(L_add, sqrtU, sqrtC)
        amt1 = amount1_delta(L_add, sqrtC, sqrtL)
        return amt0, amt1

    def mint(self, owner: str, lower_tick: int, upper_tick: int, liquidity: int, data: CallbackData, manager):
        """
        Pool.mint(...) calls back into manager.uniswapV3MintCallback(amount0, amount1, data).
        """
        self.set_range(lower_tick, upper_tick)
        amt0, amt1 = self._required_amounts_for_liquidity(liquidity)

        # callback: pool asks manager to pay amt0/amt1 in
        manager.uniswapV3MintCallback(
            pool=self,
            amount0=amt0,
            amount1=amt1,
            data=data
        )

        # if callback succeeded, liquidity becomes active
        self.L += liquidity
        return amt0, amt1

    def swap_token1_in_for_token0_out(self, recipient: str, amount1_in_raw: int, data: CallbackData, manager):
        """
        Simplified: token1 in -> token0 out, stays in range if possible (clamped).
        """
        if self.L <= 0:
            raise ValueError("Pool has no liquidity. Mint first.")

        sqrtC = self.sqrtp_x96
        sqrtL = tick_to_sqrtp_x96(self.lower_tick)
        sqrtU = tick_to_sqrtp_x96(self.upper_tick)

        # Move sqrtP by ΔsqrtP = amount1_in * Q96 / L
        d_sqrtp = (amount1_in_raw * Q96) // self.L
        sqrtN = sqrtC + d_sqrtp

        # clamp to range (milestone-style single range)
        if sqrtN > sqrtU:
            sqrtN = sqrtU
        if sqrtN < sqrtL:
            sqrtN = sqrtL

        # compute actual token deltas for movement sqrtC -> sqrtN
        # pool receives amount1_in_used, and pays amount0_out
        amt1_used = amount1_delta(self.L, sqrtN, sqrtC)
        amt0_out  = amount0_delta(self.L, sqrtN, sqrtC)

        # callback: pool requests token1 payment
        # Use Uniswap sign convention: positive means "pool wants this token IN"
        # token1 in => amount1 positive; token0 out => amount0 negative
        manager.uniswapV3SwapCallback(
            pool=self,
            amount0=-amt0_out,
            amount1=amt1_used,
            data=data
        )

        # pay token0 out to recipient from pool balance
        if self.token0.balance_of(self.address) < amt0_out:
            raise ValueError("Pool token0 balance too low (mint provides balances; check mint step).")
        self.token0.transfer(self.address, recipient, amt0_out)

        # update price
        self.sqrtp_x96 = sqrtN
        return amt1_used, amt0_out


class Manager:
    def __init__(self, address: str, tokens: Dict[str, Token], event_log: List[str]):
        self.address = address
        self.tokens = tokens
        self.log = event_log

    def mint(self, pool: Pool, caller: str, lower_tick: int, upper_tick: int, liquidity: int):
        # Create callback data that includes payer + token addresses/symbols (book concept) :contentReference[oaicite:3]{index=3}
        data = CallbackData(token0_symbol=pool.token0.symbol, token1_symbol=pool.token1.symbol, payer=caller)
        self.log.append(f"Manager.mint(pool={pool.address}, caller={caller}, L={liquidity}, ticks=[{lower_tick},{upper_tick}])")
        amt0, amt1 = pool.mint(owner=caller, lower_tick=lower_tick, upper_tick=upper_tick, liquidity=liquidity, data=data, manager=self)
        self.log.append(f"Pool.mint computed required: amount0={amt0} ({pool.token0.symbol}), amount1={amt1} ({pool.token1.symbol})")
        return amt0, amt1

    def swap(self, pool: Pool, caller: str, recipient: str, token1_in_raw: int):
        data = CallbackData(token0_symbol=pool.token0.symbol, token1_symbol=pool.token1.symbol, payer=caller)
        self.log.append(f"Manager.swap(pool={pool.address}, caller={caller}, recipient={recipient}, token1_in={token1_in_raw})")
        amt1_used, amt0_out = pool.swap_token1_in_for_token0_out(recipient=recipient, amount1_in_raw=token1_in_raw, data=data, manager=self)
        self.log.append(f"Pool.swap result: token1_used={amt1_used} ({pool.token1.symbol}), token0_out={amt0_out} ({pool.token0.symbol})")
        return amt1_used, amt0_out

    # Callbacks
    def uniswapV3MintCallback(self, pool: Pool, amount0: int, amount1: int, data: CallbackData):
        # Manager pulls tokens from payer using transferFrom-like logic :contentReference[oaicite:4]{index=4}
        t0 = self.tokens[data.token0_symbol]
        t1 = self.tokens[data.token1_symbol]

        if amount0 > 0:
            t0.transfer_from(spender=self.address, owner=data.payer, to=pool.address, raw_amt=amount0)
            self.log.append(f"MintCallback: transferFrom payer->{pool.address}: {amount0} {t0.symbol}")

        if amount1 > 0:
            t1.transfer_from(spender=self.address, owner=data.payer, to=pool.address, raw_amt=amount1)
            self.log.append(f"MintCallback: transferFrom payer->{pool.address}: {amount1} {t1.symbol}")

    def uniswapV3SwapCallback(self, pool: Pool, amount0: int, amount1: int, data: CallbackData):
        # Only pay the positive side(s) to pool, like Uniswap: if amountX > 0, pool expects input token :contentReference[oaicite:5]{index=5}
        t0 = self.tokens[data.token0_symbol]
        t1 = self.tokens[data.token1_symbol]

        if amount0 > 0:
            t0.transfer_from(spender=self.address, owner=data.payer, to=pool.address, raw_amt=amount0)
            self.log.append(f"SwapCallback: transferFrom payer->{pool.address}: {amount0} {t0.symbol}")

        if amount1 > 0:
            t1.transfer_from(spender=self.address, owner=data.payer, to=pool.address, raw_amt=amount1)
            self.log.append(f"SwapCallback: transferFrom payer->{pool.address}: {amount1} {t1.symbol}")


# -----------------------------
# Streamlit app
# -----------------------------
st.set_page_config(page_title="Uniswap V3 Manager Contract Simulator", layout="wide")
st.title("Manager Contract Simulator (Mint + Swap + Callbacks)")

st.markdown(
    """
This sim models the **periphery “manager”** as an intermediary that forwards `mint`/`swap` to a pool and
**pays the pool via callbacks** (using `transferFrom` semantics), so EOAs can interact with a core pool. :contentReference[oaicite:6]{index=6}
"""
)

# ---- session state init
def init_state():
    if "log" not in st.session_state:
        st.session_state.log = []
    if "tokens" not in st.session_state:
        # Token0: ETH(18), Token1: USDC(6) — purely for simulation
        eth = Token("ETH", 18)
        usdc = Token("USDC", 6)
        st.session_state.tokens = {"ETH": eth, "USDC": usdc}
    if "manager" not in st.session_state:
        st.session_state.manager = Manager(address="Manager", tokens=st.session_state.tokens, event_log=st.session_state.log)
    if "pool" not in st.session_state:
        pool = Pool(address="Pool1", token0=st.session_state.tokens["ETH"], token1=st.session_state.tokens["USDC"], price_init=5000.0)
        st.session_state.pool = pool
    if "user" not in st.session_state:
        st.session_state.user = "Alice"
    if "initialized_balances" not in st.session_state:
        # give user balances
        t0 = st.session_state.tokens["ETH"]
        t1 = st.session_state.tokens["USDC"]
        t0.mint("Alice", t0.raw(10.0))        # 10 ETH
        t1.mint("Alice", t1.raw(200_000.0))   # 200k USDC
        # pool starts empty; will receive funds during mint callback
        st.session_state.initialized_balances = True

init_state()

tokens: Dict[str, Token] = st.session_state.tokens
pool: Pool = st.session_state.pool
manager: Manager = st.session_state.manager
user = st.session_state.user

# ---- sidebar controls
with st.sidebar:
    st.header("Actors")
    user = st.text_input("User address", value=user)
    st.session_state.user = user

    st.caption("Manager address is fixed: `Manager`. Pool address is fixed: `Pool1`.")

    st.divider()
    st.header("1) Approvals (User → Manager)")

    approve_token = st.selectbox("Token to approve", ["USDC", "ETH"])
    approve_amount_human = st.number_input("Approve amount (human)", min_value=0.0, value=100000.0, step=1000.0)

    if st.button("Approve"):
        t = tokens[approve_token]
        t.approve(owner=user, spender=manager.address, raw_amt=t.raw(approve_amount_human))
        st.session_state.log.append(f"Approve: {user} approved {approve_amount_human} {t.symbol} to Manager")
        st.success("Approved.")

    st.divider()
    st.header("2) Mint via Manager")

    cur_price = pool.info()["price"]
    st.caption(f"Pool current price: {fmt_price(cur_price)} USDC/ETH")

    lower_price = st.number_input("Lower price (USDC/ETH)", min_value=1.0, value=4545.0, step=1.0)
    upper_price = st.number_input("Upper price (USDC/ETH)", min_value=1.0, value=5500.0, step=1.0)

    lower_tick = price_to_tick(lower_price)
    upper_tick = price_to_tick(upper_price)
    st.write(f"Ticks ≈ [{lower_tick}, {upper_tick}]")

    L_log10 = st.slider("Liquidity scale log10(L)", min_value=6, max_value=30, value=20)
    liquidity = 10 ** int(L_log10)

    if st.button("Mint (Manager → Pool.mint + callback)"):
        try:
            amt0, amt1 = manager.mint(pool=pool, caller=user, lower_tick=lower_tick, upper_tick=upper_tick, liquidity=liquidity)
            st.success("Mint successful (callback paid the pool).")
        except Exception as e:
            st.error(f"Mint failed: {e}")

    st.divider()
    st.header("3) Swap via Manager")

    token1_in_usdc = st.number_input("USDC in (human)", min_value=0.0, value=42.0, step=1.0)

    if st.button("Swap (USDC in → ETH out)"):
        try:
            usdc = tokens["USDC"]
            amt1_used, amt0_out = manager.swap(pool=pool, caller=user, recipient=user, token1_in_raw=usdc.raw(token1_in_usdc))
            st.success("Swap successful.")
        except Exception as e:
            st.error(f"Swap failed: {e}")

    st.divider()
    if st.button("Reset demo state"):
        # wipe and re-init
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ---- main panels
colA, colB = st.columns([1, 1])

def balances_table(addrs: List[str]):
    rows = []
    for a in addrs:
        rows.append({
            "address": a,
            "ETH": f"{tokens['ETH'].human(tokens['ETH'].balance_of(a)):.6f}",
            "USDC": f"{tokens['USDC'].human(tokens['USDC'].balance_of(a)):.2f}",
        })
    return rows

def allowances_table(owner: str, spender: str):
    return [{
        "owner": owner,
        "spender": spender,
        "ETH_allowance": f"{tokens['ETH'].human(tokens['ETH'].allowance(owner, spender)):.6f}",
        "USDC_allowance": f"{tokens['USDC'].human(tokens['USDC'].allowance(owner, spender)):.2f}",
    }]

with colA:
    st.subheader("Balances")
    st.dataframe(balances_table([user, manager.address, pool.address]), use_container_width=True)

    st.subheader("Allowances (User → Manager)")
    st.dataframe(allowances_table(user, manager.address), use_container_width=True)

    st.subheader("Pool State")
    info = pool.info()
    st.write(f"**Price:** {fmt_price(info['price'])} USDC/ETH")
    st.write(f"**Tick (approx):** {info['tick']}")
    st.write(f"**Range ticks:** [{info['lower_tick']}, {info['upper_tick']}]")
    st.write(f"**Active liquidity L:** {info['L']}")

with colB:
    st.subheader("Event Log (what happened)")
    if st.session_state.log:
        st.code("\n".join(st.session_state.log[-80:]))
    else:
        st.info("No events yet. Start with approvals, then mint, then swap.")

st.markdown("---")
st.markdown(
    """
### How this maps to the book page
- The manager is a **periphery intermediary** that forwards calls to a pool and implements callbacks, so EOAs can interact. :contentReference[oaicite:7]{index=7}  
- The callbacks receive extra data (token0/token1/payer) conceptually like the book’s `CallbackData` and decoding pattern. :contentReference[oaicite:8]{index=8}  
- Mint/swap require prior **approvals**, and the manager uses `transferFrom` behavior to pull funds from the payer during callbacks. :contentReference[oaicite:9]{index=9}  
"""
)

