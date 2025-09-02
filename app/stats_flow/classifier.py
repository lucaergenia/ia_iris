import json
import re
import unicodedata
from pathlib import Path

# Ruta al archivo con modelos EV/PHEV en Colombia
MODELS_FILE = Path(__file__).resolve().parents[1] / "models" / "models_ev_phev.json"

with open(MODELS_FILE, "r", encoding="utf-8") as f:
    models_data = json.load(f)["marcas"]

def normalize(text: str) -> str:
    """Normaliza cadenas para comparar modelos/marcas de forma flexible.

    - Convierte a minúsculas
    - Elimina acentos/diacríticos
    - Sustituye separadores comunes (- _ /) por espacio
    - Elimina caracteres no alfanuméricos (excepto espacios)
    - Colapsa espacios múltiples
    """
    if not text:
        return ""
    # a) quitar acentos
    txt = unicodedata.normalize("NFKD", str(text))
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    # b) minúsculas
    txt = txt.lower()
    # c) separadores a espacio
    txt = re.sub(r"[-_/]+", " ", txt)
    # d) quitar todo lo no alfanumérico/espacio
    txt = re.sub(r"[^a-z0-9 ]+", "", txt)
    # e) colapsar espacios
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _contains_either(a: str, b: str) -> bool:
    """Compara normalizando y permitiendo que A contenga B o viceversa.
    También compara sin espacios para evitar diferencias como "e tron" vs "etron".
    """
    if not a or not b:
        return False
    a_n = normalize(a)
    b_n = normalize(b)
    if not a_n or not b_n:
        return False
    if a_n in b_n or b_n in a_n:
        return True
    a_c = a_n.replace(" ", "")
    b_c = b_n.replace(" ", "")
    return a_c in b_c or b_c in a_c

def classify_vehicle(brand: str, model: str) -> str:
    """
    Clasifica un vehículo como EV, PHEV o unclassified.
    - Usa comparación flexible (minúsculas + contains).
    """
    if not brand or not model:
        return "unclassified"

    brand_norm = normalize(brand)
    model_norm = normalize(model)

    # Buscar por coincidencia exacta de clave o por versión normalizada
    brand_data = models_data.get(brand)
    if not brand_data:
        # también intentamos buscar ignorando mayúsculas/acentos
        for b in models_data.keys():
            if normalize(b) == brand_norm:
                brand_data = models_data[b]
                break

    if not brand_data:
        print(f"⚠️ Marca no encontrada en JSON: {brand}")
        return "unclassified"

    # Buscar coincidencia EV (flexible)
    for ev_model in brand_data.get("EV", []):
        if _contains_either(ev_model, model_norm):
            return "EV"

    # Buscar coincidencia PHEV (flexible)
    for phev_model in brand_data.get("PHEV", []):
        if _contains_either(phev_model, model_norm):
            return "PHEV"

    print(f"❓ Modelo no clasificado: {brand} {model}")
    return "unclassified"


# 🔹 Nueva función: clasifica un solo vehículo
def classify_single_vehicle(brand: str, model: str) -> str:
    return classify_vehicle(brand, model)


# Mantengo tu compute_statistics original para listas
def compute_statistics(vehicles):
    """
    Procesa lista de vehículos y devuelve un resumen estadístico.
    """
    ev_count = phev_count = unclassified_count = 0
    details = []

    for v in vehicles:
        category = classify_vehicle(v["brand"], v["model"])
        details.append({**v, "category": category})
        if category == "EV":
            ev_count += 1
        elif category == "PHEV":
            phev_count += 1
        else:
            unclassified_count += 1

    return ev_count, phev_count, unclassified_count, details
