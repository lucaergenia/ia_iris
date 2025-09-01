
import os
import httpx
from dotenv import load_dotenv
import requests 
load_dotenv()

ETECNIC_STATS_URL = os.getenv("ETECNIC_STATS_URL", "https://etecnic.net/api/v1/etecnic/charger/charges")
API_KEY = os.getenv("ETECNIC_BEARER_TOKEN")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

print(f"🔑 API_KEY: {repr(API_KEY)}")
print(f"📡 Headers enviados: {HEADERS}")

async def get_charger_charges(charger_id: int) -> dict:
    """
    Obtiene TODAS las cargas de un cargador (maneja la paginación automáticamente).
    """
    all_charges = []
    page = 1

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                url = f"{ETECNIC_STATS_URL}/{charger_id}?page={page}"
                response = await client.get(url, headers=HEADERS)

                if response.status_code != 200:
                    print(f"Error en la solicitud: {response.status_code} - {response.text}")
                    break

                data = response.json()
                charges = data.get("charges", [])

                if not charges:
                    break

                all_charges.extend(charges)

                # si devuelve menos de 20, ya era la última página
                if len(charges) < 20:
                    break

                page += 1

        return {
            "charger_id": charger_id,
            "charges": all_charges
        }

    except Exception as e:
        print(f"Excepción durante la solicitud: {e}")
    return {"charger_id": charger_id, "charges": []}


BASE_URL = "https://etecnic.net/api/v1/etecnic"

async def get_user_id_from_code(user_code: str):
    url = f"{BASE_URL}/cards/get-user-from-code/{user_code}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        user_obj = data.get("user")
        return user_obj.get("id") if user_obj else None

async def get_user_info(user_id: str):
    url = f"{BASE_URL}/users/show/{user_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        user_obj = data.get("user", {})
        vehicles = user_obj.get("vehicles", [])
        if vehicles:
            v = vehicles[0]
            return {"brand": v.get("vehicle_brand_name"), "model": v.get("vehicle_model_name")}
    return {"brand": None, "model": None}