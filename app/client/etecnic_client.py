
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
import logging
from urllib.parse import quote
load_dotenv()

ETECNIC_STATS_URL = os.getenv("ETECNIC_STATS_URL", "https://etecnic.net/api/v1/etecnic/charger/charges")
API_KEY = os.getenv("ETECNIC_BEARER_TOKEN")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
logger = logging.getLogger(__name__)

BASE_URL = "https://etecnic.net/api/v1/etecnic"
ETECNIC_PLATE_URL = os.getenv("ETECNIC_PLATE_URL", f"{BASE_URL}/users/charges-by-plate")
ETECNIC_TIMEOUT = float(os.getenv("ETECNIC_TIMEOUT", "10"))

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
                    # se suprime log en consola en producción; usar nivel debug para troubleshooting
                    logger.debug("ETECNIC charges request failed: %s - %s", response.status_code, response.text)
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
        logger.debug("Excepción durante la solicitud ETECNIC: %s", e)
    return {"charger_id": charger_id, "charges": []}

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


class EtecnicClient:
    """Cliente simple para interactuar con la API de Etecnic.

    - ``ETECNIC_PLATE_URL`` debe apuntar al endpoint que expone la
      búsqueda de matrículas, e.g. ``https://.../vehicles/get-by-plate``.
    - Se reutiliza el *Bearer token* configurado en ``ETECNIC_BEARER_TOKEN``.
    """

    def __init__(self, *, timeout: Optional[float] = None):
        self.headers = HEADERS
        self.timeout = timeout or ETECNIC_TIMEOUT
        self.plate_url = ETECNIC_PLATE_URL.rstrip("/") if ETECNIC_PLATE_URL else None

    async def obtener_dueno(self, plate: str) -> Optional[dict]:
        """Busca información asociada a una matrícula de forma asíncrona."""
        if not plate:
            return None
        if not self.plate_url:
            logger.debug("ETECNIC_PLATE_URL no configurada; se omite consulta de matrícula")
            return None
        encoded_plate = quote(plate.strip().upper())
        url = f"{self.plate_url}/{encoded_plate}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.debug("Etecnic matrícula %s → HTTP %s", plate, exc.response.status_code)
        except Exception as exc:  # pragma: no cover - red de terceros
            logger.debug("Fallo consultando matrícula %s en Etecnic: %s", plate, exc)
        return None

    def obtener_dueno_sync(self, plate: str) -> Optional[dict]:
        """Variante síncrona para uso en hilos (vision service)."""
        if not plate:
            return None
        if not self.plate_url:
            logger.debug("ETECNIC_PLATE_URL no configurada; se omite consulta de matrícula")
            return None
        encoded_plate = quote(plate.strip().upper())
        url = f"{self.plate_url}/{encoded_plate}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self.headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.debug("Etecnic matrícula %s → HTTP %s", plate, exc.response.status_code)
        except Exception as exc:  # pragma: no cover - red de terceros
            logger.debug("Fallo consultando matrícula %s en Etecnic (sync): %s", plate, exc)
        return None


__all__ = [
    "get_charger_charges",
    "get_user_id_from_code",
    "get_user_info",
    "EtecnicClient",
]
