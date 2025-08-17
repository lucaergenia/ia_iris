import os 
import httpx
from dotenv import load_dotenv

load_dotenv()

ETECNIC_API_URL = "https://etecnic.net/api/v1/etecnic/users/charges-by-plate/"
ETECNIC_TOKEN  = os.getenv("ETECNIC_BEARER_TOKEN")


HEADERS = {
    "Authorization": f"Bearer {ETECNIC_TOKEN}"
}


async def obtener_dueno(plate:str) -> dict:
    url = f"{ETECNIC_API_URL}{plate}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
                print(response.json())
                return response.json()
            else: 
                print(f"Error en la solicitud: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Excepción durante la solicitud: {e}")
    return None