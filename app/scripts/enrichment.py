from datetime import datetime, timedelta

def buscar_info_marca(informes, marca):
    for info in informes.values():
        for fila in info:
            if "MARCA" in fila and fila["MARCA"].lower() == marca.lower():
                return fila
    return None
def buscar_info_modelo(informes, modelo):
    for info in informes.values():
        for fila in info:
            if ('LINEA' in fila or 'MODELO' in fila) and (
                fila.get('LINEA','').lower() == modelo.lower() or
                fila.get('MODELO','').lower() == modelo.lower()):
                return fila
    return None   

def buscar_info_tecnologia(informes, tipo):
    for info in informes.values():
        for fila in info:
            if 'TIPO DE TECNOLOGIA' in fila and fila['TIPO DE TECNOLOGIA'].lower() == tipo.lower():
                return fila
    return None

def enriquecer_datos(informes, vehiculo):
    info = {}
    marca = vehiculo.get("marca", "")
    modelo = vehiculo.get("modelo", "")
    tipo_vehiculo = vehiculo.get("tipo_vehiculo", "")
    info["marca_stats"] = buscar_info_marca(informes, marca)
    info["modelo_stats"] = buscar_info_modelo(informes, modelo)
    info["tecnologia_stats"] = buscar_info_tecnologia(informes, tipo_vehiculo)
    return info


def procesar_info(json_data):
    if not json_data or "info" not in json_data or not json_data["info"]:
        return None
    
    usuario = json_data["info"][0]
    
    user = usuario.get("user_info", {})
    vehicle = usuario.get("vehicle_info", {})
    charges = usuario.get("charges_info", [])

    total_cargas = len(charges)
    total_tiempo = sum(int(c.get("time_total", 0)) for c in charges if c.get("time_total"))
    promedio_tiempo = round(total_tiempo / total_cargas, 2) if total_cargas else 0
    
    # Promedio frecuencia horas
    fechas = sorted([c["session_start_at"] for c in charges if "session_start_at" in c])
    frecuencias = []
    formatos = ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"]
    dt_fechas = []
    for fecha in fechas:
        for fmt in formatos:
            try:
                dt_fechas.append(datetime.strptime(fecha, fmt))
                break
            except:
                continue
    if len(dt_fechas) > 1:
        frecuencias = [
            (dt_fechas[i] - dt_fechas[i-1]).total_seconds() / 3600
            for i in range(1, len(dt_fechas))
        ]
    promedio_frecuencia_horas = round(sum(frecuencias) / len(frecuencias), 2) if frecuencias else 0

    # -------------------------
    # NUEVOS DATOS ADICIONALES
    # -------------------------
    # 1. Conteo por estación
    cargas_por_estacion = {}
    for c in charges:
        nombre = c.get("charger_name", "Desconocido")
        cargas_por_estacion[nombre] = cargas_por_estacion.get(nombre, 0) + 1

    # 2. Energía total cargada (en Wh si viene así)
    energia_total = sum(float(c.get("energy", 0)) for c in charges if c.get("energy"))

    # 3. Gasto total
    gasto_total = sum(float(c.get("amount", 0)) for c in charges if c.get("amount"))

    # 4. Cargas en el último mes
    ahora = datetime.now(tz=dt_fechas[0].tzinfo if dt_fechas else None)
    hace_un_mes = ahora - timedelta(days=30)
    cargas_ultimo_mes = sum(1 for fecha in dt_fechas if fecha >= hace_un_mes)

    # 5. Velocidad promedio de carga (Wh/min o kW)
    velocidades = []
    for c in charges:
        try:
            energia = float(c.get("energy", 0))
            tiempo = float(c.get("time_charging", 0))
            if energia > 0 and tiempo > 0:
                velocidades.append(energia / tiempo)
        except:
            continue
    velocidad_promedio = round(sum(velocidades) / len(velocidades), 2) if velocidades else 0

    # -------------------------
    return {
        "nombre": user.get("name", "Desconocido"),
        "marca": vehicle.get("vehicle_brand", "Desconocida"),
        "modelo": vehicle.get("vehicle_model", "Desconocido"),
        "patente": vehicle.get("plate", "Desconocida"),
        "total_cargas": total_cargas,
        "promedio_tiempo_carga": promedio_tiempo,
        "promedio_frecuencia_horas": promedio_frecuencia_horas,
        # Nuevos datos
        "cargas_por_estacion": cargas_por_estacion,
        "energia_total": energia_total,
        "gasto_total": gasto_total,
        "cargas_ultimo_mes": cargas_ultimo_mes,
        "velocidad_promedio": velocidad_promedio
    }