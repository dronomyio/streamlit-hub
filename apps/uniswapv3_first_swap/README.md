# Uniswap V3 "First Swap" Interactive (Streamlit)

This app demonstrates the Uniswap V3 "first swap" concept (single-range swap):
- Liquidity L remains constant during the swap (as long as you stay within the range)
- sqrtP moves by ΔsqrtP = (amount1_in * Q96) / L (for token1-in, token0-out direction)
- Output amount0_out is computed from L and the sqrt price change

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

streamlit run app.py

