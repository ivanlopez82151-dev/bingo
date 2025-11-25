# servidor_websocket.py
import asyncio
import websockets
import json
import random
import threading
import time

# Configuración
balotas_posibles = [f"{letra}{n}" for letra, r in zip("BINGO", [range(1,16), range(16,31), range(31,46), range(46,61), range(61,76)]) for n in r]
clientes = {}  # {websocket: {"nombre": str, "carton": [...], "ganador": bool}}
balotas_llamadas = []
juego_activo = False
intervalo = 3  # segundos

def generar_carton():
    carton = []
    rangos = [range(1,16), range(16,31), range(31,46), range(46,61), range(61,76)]
    for i, rango in enumerate(rangos):
        col = random.sample(rango, 5)
        if i == 2:
            col[2] = "FREE"
        carton.append(col)
    return carton

def verificar_bingo(carton, balotas_llamadas):
    numeros_llamados = {int(b[1:]) for b in balotas_llamadas if b[0] in "BINGO"}
    # Filas
    for fila in range(5):
        if all((carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados) for col in range(5)):
            return True
    # Columnas
    for col in range(5):
        if all((carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados) for fila in range(5)):
            return True
    return False

async def notificar_balota(ws, balota):
    await ws.send(json.dumps({"tipo": "BALOTA", "valor": balota}))

async def notificar_ganador(ganador_ws, nombre, carton):
    await ganador_ws.send(json.dumps({"tipo": "BINGO", "mensaje": f"¡{nombre} ha ganado!"}))
    for ws in clientes:
        if ws != ganador_ws:
            try:
                await ws.send(json.dumps({"tipo": "FIN", "mensaje": f"{nombre} ha ganado el juego."}))
            except:
                pass

async def hilo_balotas():
    global juego_activo, balotas_llamadas, intervalo
    balotas_disponibles = balotas_posibles.copy()
    random.shuffle(balotas_disponibles)

    while juego_activo and balotas_disponibles:
        balota = balotas_disponibles.pop()
        balotas_llamadas.append(balota)

        # Enviar a todos
        desconectados = []
        for ws in list(clientes.keys()):
            try:
                await notificar_balota(ws, balota)
            except:
                desconectados.append(ws)

        for ws in desconectados:
            clientes.pop(ws, None)

        # Verificar ganador
        for ws, data in list(clientes.items()):
            if verificar_bingo(data["carton"], balotas_llamadas):
                juego_activo = False
                clientes[ws]["ganador"] = True
                await notificar_ganador(ws, data["nombre"], data["carton"])
                return

        await asyncio.sleep(intervalo)

async def manejar_cliente(websocket, path):
    global juego_activo
    try:
        # Recibir nombre
        mensaje = await websocket.recv()
        data = json.loads(mensaje)
        nombre = data.get("nombre", "Anónimo")

        # Generar cartón
        carton = generar_carton()
        clientes[websocket] = {"nombre": nombre, "carton": carton, "ganador": False}

        # Enviar cartón
        await websocket.send(json.dumps({"tipo": "CARTON", "valor": carton}))

        # Si el juego ya empezó, enviar balotas previas
        if balotas_llamadas:
            for b in balotas_llamadas:
                await notificar_balota(websocket, b)

        # Mantener conexión
        await websocket.wait_closed()

    except Exception as e:
        print("Cliente desconectado:", e)
    finally:
        clientes.pop(websocket, None)

async def iniciar_juego():
    global juego_activo
    if not juego_activo and clientes:
        juego_activo = True
        asyncio.create_task(hilo_balotas())

# Punto de entrada
if __name__ == "__main__":
    import os
    PORT = int(os.environ.get("PORT", 8765))
    print(f"Servidor WebSocket escuchando en puerto {PORT}")
    start_server = websockets.serve(manejar_cliente, "0.0.0.0", PORT)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()