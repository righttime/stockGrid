import asyncio, httpx, os, json
from dotenv import load_dotenv

async def test():
    load_dotenv()
    k, s = os.getenv("KIWOOM_API_KEY"), os.getenv("KIWOOM_SECRET_KEY")
    h = "https://api.kiwoom.com"
    async with httpx.AsyncClient() as c:
        # Token
        r = await c.post(h + "/oauth2/token", json={"grant_type": "client_credentials", "appkey": k, "secretkey": s})
        tk = r.json().get("token")
        
        # Test Weekly (ka10082)
        u = h + "/api/dostk/chart"
        hd = {'Content-Type': 'application/json', 'authorization': 'Bearer ' + tk, 'api-id': 'ka10082'}
        p = {'stk_cd': '005930', 'base_dt': '20250214', 'upd_stkpc_tp': '1'}
        r = await c.post(u, headers=hd, json=p)
        print("WEEKLY_RESULT:" + r.text[:500])

if __name__ == "__main__":
    asyncio.run(test())
