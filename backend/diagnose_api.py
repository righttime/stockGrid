import asyncio
import httpx
import os
from dotenv import load_dotenv

async def diagnose():
    load_dotenv()
    api_key = os.getenv("KIWOOM_API_KEY")
    secret_key = os.getenv("KIWOOM_SECRET_KEY")
    
    # 가이드 기반 도메인 수정
    api_url = "https://api.kiwoom.com"
    
    print(f"--- Diagnosis Start (Target: {api_url}) ---")
    async with httpx.AsyncClient() as client:
        # Auth Token
        print("Testing Access Token...")
        url_auth = f"{api_url}/oauth2/token"
        try:
            r = await client.post(url_auth, json={
                "grant_type": "client_credentials",
                "appkey": api_key,
                "appsecret": secret_key
            })
            print(f"Auth Status: {r.status_code}")
            print(f"Auth Resp: {r.text[:200]}")
        except Exception as e:
            print(f"Auth Error: {e}")

        # Approval Key
        print("\nTesting Approval Key...")
        url_app = f"{api_url}/oauth2/Approval"
        try:
            r = await client.post(url_app, json={
                "grant_type": "client_credentials",
                "appkey": api_key,
                "secretkey": secret_key
            })
            print(f"App Status: {r.status_code}")
            print(f"App Resp: {r.text[:200]}")
        except Exception as e:
            print(f"App Error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose())
