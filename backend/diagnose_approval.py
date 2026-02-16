import asyncio, httpx, os
from dotenv import load_dotenv

async def test():
    load_dotenv()
    k, s = os.getenv("KIWOOM_API_KEY"), os.getenv("KIWOOM_SECRET_KEY")
    u = "https://api.kiwoom.com/oauth2/Approval"
    h = {'Content-Type': 'application/json'}
    async with httpx.AsyncClient() as c:
        for f in ["secretkey", "appsecret"]:
            p = {"grant_type": "client_credentials", "appkey": k, f: s}
            r = await c.post(u, headers=h, json=p)
            print(f"Field {f}: {r.status_code} - {r.text}")

if __name__ == "__main__":
    asyncio.run(test())
