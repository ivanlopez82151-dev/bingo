# servidor_bingo_gui.py
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import random

HOST = '127.0.0.1'
PORT = 65432

balotas_posibles = [f"{letra}{n}" for letra, r in zip("BINGO", [range(1,16), range(16,31), range(31,46), range(46,61), range(61,76)]) for n in r]
balotas_disponibles = balotas_posibles.copy()
balotas_llamadas = []
clientes = []  # [(conn, carton, nombre), ...]
lock = threading.Lock()
intervalo = 3.0
juego_activo = True

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
        if all(
            (carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados)
            for col in range(5)
        ):
            return True
    # Columnas
    for col in range(5):
        if all(
            (carton[col][fila] == "FREE") or (int(carton[col][fila]) in numeros_llamados)
            for fila in range(5)
        ):
            return True
    return False

def enviar_a_todos(mensaje):
    global clientes
    with lock:
        vivos = []
        for conn, carton, nombre in clientes:
            try:
                conn.sendall(mensaje.encode())
                vivos.append((conn, carton, nombre))
            except:
                conn.close()
        clientes[:] = vivos

def hilo_balotas(app):
    global balotas_disponibles, balotas_llamadas, intervalo, juego_activo
    while juego_activo and balotas_disponibles:
        balota = random.choice(balotas_disponibles)
        with lock:
            balotas_disponibles.remove(balota)
            balotas_llamadas.append(balota)

        app.root.after(0, lambda b=balota: app.actualizar_balota_actual(b))
        app.root.after(0, lambda: app.actualizar_lista_balotas(balotas_llamadas))
        enviar_a_todos(f"BALOTA:{balota}")

        # Verificar BINGO
        with lock:
            for conn, carton, nombre in clientes:
                if verificar_bingo(carton, balotas_llamadas):
                    juego_activo = False
                    app.root.after(0, lambda n=nombre, c=carton: app.mostrar_ganador(n, c))
                    conn.sendall(b"BINGO")
                    enviar_a_todos("FIN")
                    return

        for _ in range(int(intervalo * 10)):
            if not juego_activo:
                return
            threading.Event().wait(0.1)

class ServidorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Servidor Bingo - Con nombres y velocidad")
        self.root.geometry("600x650")

        tk.Label(root, text=".Intervalo entre balotas (segundos):", font=("Arial", 12)).pack(pady=5)
        self.velocidad = tk.DoubleVar(value=3.0)
        self.slider = tk.Scale(root, from_=1, to=10, resolution=0.5, orient=tk.HORIZONTAL,
                               variable=self.velocidad, command=self.cambiar_velocidad)
        self.slider.pack(pady=5)

        self.btn_iniciar = tk.Button(root, text="Iniciar Juego", command=self.iniciar_juego, bg="green", fg="white")
        self.btn_iniciar.pack(pady=10)

        tk.Label(root, text="Balota actual:", font=("Arial", 12, "bold")).pack()
        self.label_actual = tk.Label(root, text="--", font=("Arial", 16), fg="blue")
        self.label_actual.pack(pady=5)

        tk.Label(root, text="Balotas llamadas:").pack(pady=(10,0))
        self.text_balotas = tk.Text(root, height=6, width=60)
        self.text_balotas.pack(padx=20, pady=5)

        tk.Label(root, text="GANADOR:", font=("Arial", 14, "bold"), fg="red").pack(pady=(10,5))
        self.label_ganador = tk.Label(root, text="Ninguno aún", font=("Arial", 12))
        self.label_ganador.pack()

        tk.Label(root, text="Cartilla ganadora:", font=("Arial", 12, "bold")).pack(pady=(10,5))
        self.text_ganador = tk.Text(root, height=6, width=60, bg="#f0f8ff")
        self.text_ganador.pack(padx=20)

        threading.Thread(target=self.iniciar_servidor, daemon=True).start()

    def cambiar_velocidad(self, val):
        global intervalo
        intervalo = float(val)

    def iniciar_juego(self):
        global juego_activo
        juego_activo = True
        self.btn_iniciar.config(state="disabled", text="Juego en curso...")
        threading.Thread(target=hilo_balotas, args=(self,), daemon=True).start()

    def actualizar_balota_actual(self, balota):
        self.label_actual.config(text=balota)

    def actualizar_lista_balotas(self, lista):
        self.text_balotas.delete(1.0, tk.END)
        self.text_balotas.insert(tk.END, ", ".join(lista))

    def mostrar_ganador(self, nombre, carton):
        self.label_ganador.config(text=f"¡{nombre} ha ganado!")
        self.text_ganador.delete(1.0, tk.END)
        for fila in range(5):
            linea = []
            for col in range(5):
                val = carton[col][fila]
                linea.append(str(val).rjust(5))
            self.text_ganador.insert(tk.END, " ".join(linea) + "\n")

    def iniciar_servidor(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            print("Servidor esperando conexiones...")
            while True:
                try:
                    conn, addr = s.accept()
                    nombre = conn.recv(1024).decode().strip()
                    carton = generar_carton()
                    with lock:
                        if juego_activo:
                            clientes.append((conn, carton, nombre))
                    conn.sendall(str(carton).encode())
                    print(f"Nuevo jugador: {nombre}")
                except Exception as e:
                    print("Error al aceptar cliente:", e)

if __name__ == "__main__":
    root = tk.Tk()
    app = ServidorGUI(root)
    root.mainloop()