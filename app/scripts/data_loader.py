import json
import os


def cargar_duenos(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def cargar_informes(dir_path):
    informes = {}
    for file in os.listdir(dir_path):
        if file.endswith(".json"):
            nombre = file.replace(".json", "").lower()
            with open(os.path.join(dir_path, file), "r", encoding="utf-8") as f:
                informes[nombre] = json.load(f)
    return informes