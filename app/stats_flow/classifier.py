import json
from pathlib import Path

# Ruta al archivo con modelos EV/PHEV en Colombia
MODELS_FILE = Path(__file__).resolve().parents[1] / "models" / "models_ev_phev.json"

with open(MODELS_FILE, "r", encoding="utf-8") as f:
    models_data = json.load(f)["marcas"]

def normalize(text: str) -> str:
    """Normaliza cadenas a minúsculas, sin espacios extras."""
    return text.lower().strip() if text else ""

def classify_vehicle(brand: str, model: str) -> str:
    """
    Clasifica un vehículo como EV, PHEV o unclassified.
    - Usa comparación flexible (minúsculas + contains).
    """
    if not brand or not model:
        return "unclassified"

    brand_norm = normalize(brand)
    model_norm = normalize(model)

    brand_data = models_data.get(brand)
    if not brand_data:
        # también intentamos buscar ignorando mayúsculas
        for b in models_data.keys():
            if normalize(b) == brand_norm:
                brand_data = models_data[b]
                break

    if not brand_data:
        print(f"⚠️ Marca no encontrada en JSON: {brand}")
        return "unclassified"

    # Buscar coincidencia EV
    for ev_model in brand_data.get("EV", []):
        if normalize(ev_model) in model_norm:
            return "EV"

    # Buscar coincidencia PHEV
    for phev_model in brand_data.get("PHEV", []):
        if normalize(phev_model) in model_norm:
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
