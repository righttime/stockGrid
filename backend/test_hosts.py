import asyncio, httpx, os
from dotenv import load_dotenv

async def test_env():
    load_dotenv()
    k = os.getenv("KIWOOM_API_KEY")
    s = os.getenv("KIWOOM_SECRET_KEY")
    hosts = ["https://api.kiwoom.com", "https://mockapi.kiwoom.com"]
    
    async with httpx.AsyncClient() as c:
        for host in hosts:
            url = host + "/oauth2/token"
            try:
                r = await c.post(url, json={
                    "grant_type": "client_credentials",
                    "appkey": k,
                    "secretkey": s
                })
                print("Host: " + host)
                print("Status: " + str(r.status_code))
                print("Resp: " + r.text)
            except Exception as e:
                print("Error on " + host + ": " + str(e))

if __name__ == "__main__":
    asyncio.run(test_env())
