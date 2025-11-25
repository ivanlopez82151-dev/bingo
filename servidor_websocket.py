# servidor_websocket.py
import asyncio
import websockets
import json
import random
import os

balotas_posibles = [f"{letra}{n}" for letra, r in zip("BINGO", [range(1,16), range(16,31), range(31,46), range(46,61), range(61,76)]) for n in r]
clientes = {}
balotas_llamadas = []
juego_activo = False
intervalo = 3

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
    for fila in range(5):
        if all((carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados) for col in range(5)):
            return True
    for col in range(5):
        if all((carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados) for fila in range(5)):
            return True
    return False

async def hilo_balotas():
    global juego_activo, balotas_llamadas, intervalo
    balotas_disponibles = balotas_posibles.copy()
    random.shuffle(balotas_disponibles)

    while juego_activo and balotas_disponibles:
        balota = balotas_disponibles.pop()
        balotas_llamadas.append(balota)

        desconectados = []
        for ws in list(clientes.keys()):
            try:
                await ws.send(json.dumps({"tipo": "BALOTA", "valor": balota}))
            except:
                desconectados.append(ws)

        for ws in desconectados:
            clientes.pop(ws, None)

        for ws, data in list(clientes.items()):
            if verificar_bingo(data["carton"], balotas_llamadas):
                juego_activo = False
                await ws.send(json.dumps({"tipo": "BINGO", "mensaje": f"¡{data['nombre']} ha ganado!"}))
                for otro_ws in clientes:
                    if otro_ws != ws:
                        try:
                            await otro_ws.send(json.dumps({"tipo": "FIN", "mensaje": f"{data['nombre']} ha ganado el juego."}))
                        except:
                            pass
                return

        await asyncio.sleep(intervalo)

async def manejar_cliente(websocket, path):
    global juego_activo
    try:
        mensaje = await websocket.recv()
        data = json.loads(mensaje)
        nombre = data.get("nombre", "Anónimo").strip() or "Anónimo"

        carton = generar_carton()
        clientes[websocket] = {"nombre": nombre, "carton": carton, "ganador": False}

        await websocket.send(json.dumps({"tipo": "CARTON", "valor": carton}))

        for b in balotas_llamadas:
            await websocket.send(json.dumps({"tipo": "BALOTA", "valor": b}))

        # Iniciar juego si es el primer jugador
        if not juego_activo and len(clientes) >= 1:
            juego_activo = True
            asyncio.create_task(hilo_balotas())

        await websocket.wait_closed()

    except Exception as e:
        pass
    finally:
        clientes.pop(websocket, None)

async def main():
    PORT = int(os.environ.get("PORT", 8765))
    print(f"Servidor WebSocket escuchando en puerto {PORT}")
    async with websockets.serve(manejar_cliente, "0.0.0.0", PORT):
        await asyncio.Future()  # Mantiene el servidor corriendo

if __name__ == "__main__":
    asyncio.run(main())