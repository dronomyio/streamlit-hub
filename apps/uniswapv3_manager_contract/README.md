complete Streamlit app (app.py) that simulates the “Manager Contract” concept from the page you linked:
User approves token spending to the Manager
User calls Manager.mint(pool, …) → Manager forwards to Pool.mint(…) and implements uniswapV3MintCallback to pull funds from the payer via transferFrom-style logic
uniswapv3book.com
User calls Manager.swap(pool, …) → Manager forwards to Pool.swap(…) and implements uniswapV3SwapCallback to pull the input token from payer, then Pool sends output to recipient
uniswapv3book.com
Uses the “pass extra data to callbacks” idea (token0/token1/payer) based on the book’s CallbackData struct concept 
uniswapv3book.com
It’s interactive (balances, approvals, mint, swap, event log) and avoids Streamlit’s JS int limit by using human-scale inputs.

What you can click to “see the concept”
Approve USDC (and ETH if you want mint to succeed) to Manager
Click Mint → watch the log show Manager.mint → Pool.mint → MintCallback transferFrom
Click Swap → watch the log show Manager.swap → Pool.swap → SwapCallback transferFrom → pool transfers ETH out to user
If you want, I can also add:
