from app.core.database import stations_collection, charges_collection

def init_db():
    stations_collection.create_index("id", unique=True)
    charges_collection.create_index("id", unique=True)
    print("✅ Índices creados correctamente")

if __name__ == "__main__":
    init_db()
