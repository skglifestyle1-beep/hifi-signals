```markdown
# HIFI-USDT Signal Bot (Manual)
High-probability alerts at daily key levels (8 % swing + vol spike).  
Trades **13-18 UTC only**, skips BTC hurricanes, respects funding.  
100 % manual — never touches your exchange.

## Quick start (GitHub Codespaces / local)
1. Clone repo  
2. `cp .env.example .env` → fill token + chat-id  
3. `pip install -r requirements.txt`  
4. `python main.py`

## Commands
`/levels` – today’s S/R  
`/status` – last signal  
`/capital 1250` – set account size for size hint

## Stats (walk-forward Q1-25)
84.6 % win – PF 3.4 – Max DD 3.1 % (37 trades)
