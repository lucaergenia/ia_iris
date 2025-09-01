from pymongo import MongoClient
import os
from datetime import datetime
from dotenv import load_dotenv
import certifi
from urllib.parse import quote_plus

# Carga variables desde .env si está presente
load_dotenv()

# URI remota; permitimos construirla desde componentes para manejar passwords con encoding
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    user = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASSWORD")
    host = os.getenv("MONGO_HOST")  # p.ej. ergenia.znavlzp.mongodb.net
    if not (user and password and host):
        raise RuntimeError(
            "MONGO_URI no está configurada y faltan MONGO_USER/MONGO_PASSWORD/MONGO_HOST en .env"
        )
    params = os.getenv("MONGO_OPTIONS", "retryWrites=true&w=majority")
    app_name = os.getenv("MONGO_APP_NAME")
    if app_name:
        params += f"&appName={quote_plus(app_name)}"
    auth_source = os.getenv("MONGO_AUTH_SOURCE")
    if auth_source:
        params += f"&authSource={quote_plus(auth_source)}"
    MONGO_URI = f"mongodb+srv://{quote_plus(user)}:{quote_plus(password)}@{host}/?{params}"

if "localhost" in MONGO_URI or "127.0.0.1" in MONGO_URI:
    raise RuntimeError("MONGO_URI apunta a localhost; use la URI remota de MongoDB Atlas.")

DB_NAME = os.getenv("DB_NAME", "iris_ev")

# Crea cliente y valida la conexión
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    tlsCAFile=certifi.where(),  # asegura cadena de certificados válida para Atlas
)
try:
    client.admin.command("ping")
except Exception as e:
    raise RuntimeError(f"No se pudo conectar a MongoDB con la URI proporcionada: {e}")

db = client[DB_NAME]

# Colecciones por estación
sessions_Portobelo = db["sessions_Portobelo"]
sessions_Salvio = db["sessions_Salvio"]
stats_by_station = db["stats_by_station"]



def get_collection(name: str):
    """Devuelve una colección de MongoDB por nombre"""
    return db[name]

def insert_document(collection: str, document: dict):
    """Inserta un documento en la colección especificada"""
    return db[collection].insert_one(document)

def find_documents(collection: str, query: dict = {}, projection: dict = None):
    """Encuentra documentos con query opcional"""
    return db[collection].find(query, projection)

def update_document(collection: str, query: dict, update: dict):
    """Actualiza documentos"""
    return db[collection].update_one(query, {"$set": update})

# ==========================================
# Funciones específicas para estadísticas
# ==========================================

def get_sessions():
    """
    Devuelve todas las sesiones guardadas en la colección `sessions`.
    """
    return db.sessions.find()

def insert_stats(ev_count, phev_count, unclassified_count, details,
                 total_cargas=0, total_usuarios=0, total_energy_Wh=0):
    """
    Inserta un documento de estadísticas en la colección `stats`.
    Incluye EV, PHEV, unclassified, y opcionalmente cargas/usuarios/energía.
    """
    doc = {
        "timestamp": datetime.utcnow(),
        "ev_count": ev_count,
        "phev_count": phev_count,
        "unclassified_count": unclassified_count,
        "details": details,
        "total_cargas": total_cargas,
        "total_usuarios": total_usuarios,
        "total_energy_Wh": total_energy_Wh,
    }
    result = db.stats.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc

def insert_station_stats(station: str, ev_count: int, phev_count: int, unclassified_count: int,
                         details: list,
                         total_cargas: int = 0, total_usuarios: int = 0, total_energy_Wh: int = 0,
                         filter: str = "total"):
    """
    Inserta un documento de estadísticas por estación en `stats_by_station`.
    """
    doc = {
        "timestamp": datetime.utcnow(),
        "station": station,
        "filter": filter,
        "ev_count": ev_count,
        "phev_count": phev_count,
        "unclassified_count": unclassified_count,
        "details": details,
        "total_cargas": total_cargas,
        "total_usuarios": total_usuarios,
        "total_energy_Wh": total_energy_Wh,
    }
    result = stats_by_station.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc

def get_last_station_stats(station: str, filter: str | None = None):
    """Devuelve el último documento de estadísticas para una estación (opcional por filtro)."""
    query = {"station": station}
    if filter:
        query["filter"] = filter
    doc = stats_by_station.find_one(query, sort=[("timestamp", -1)])
    return doc
