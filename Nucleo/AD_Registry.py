import json
import socket
import uuid
import os  # Nuevo



# Después
HOST = os.getenv('HOST_REGISTRY', 'registry')  # Usando 'registry' como valor predeterminado
PORT = int(os.getenv('PORT_REGISTRY'))  # Puerto para el servidor de registro

FILENAME = 'data/drones_registry.json'

# Cargar drones desde el archivo JSON
def load_drones():
    try:
        with open(FILENAME, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

# Guardar lista de drones en el archivo JSON
def save_drones(drones):
    os.makedirs('data', exist_ok=True)
    with open(FILENAME, 'w') as file:
        json.dump(drones, file)

# Registrar un nuevo dron
def register_dron(token):
    drones = load_drones()
    if token not in drones:
        drones.append(token)
        save_drones(drones)
        return True
    return False

def get_token_for_dron(dron_id):
    drones = load_drones()
    
    # Buscar si el dron ya está registrado
    for dron in drones:
        if dron["id"] == dron_id:
            return dron["token"]
    
    # Si no está registrado, generar un nuevo token único
    existing_tokens = [dron["token"] for dron in drones]
    new_token = str(uuid.uuid4())
    while new_token in existing_tokens:
        new_token = str(uuid.uuid4())

    # Añadir el nuevo dron y su token al registro
    drones.append({"id": dron_id, "token": new_token})
    save_drones(drones)
    
    return new_token

def non_register_dron(dron_id):
    drones = load_drones()
    for dron in drones:
        if dron["id"] == dron_id:
            return False
    return True

def handle_connection(conn, addr):
    print("Conectado por", addr)
    
    # Recibe el ID del dron desde la conexión
    data = conn.recv(1024).decode()
    drone_data = json.loads(data)
    id_dron = drone_data["id"]
    
    # Verifica si el dron ya está registrado
    if non_register_dron(id_dron):
        new_token = get_token_for_dron(id_dron)
        print(f"Dron {new_token} registrado exitosamente.")
        response = {"status": "success", "token": new_token, "message": "Registrado"}
    else:
        new_token = get_token_for_dron(id_dron)
        print(f"Dron {id_dron} ya estaba registrado.")
        response = {"status": "error","token": new_token ,"message": "Ya registrado"}
    
    # Envía la respuesta al dron
    conn.sendall(json.dumps(response).encode())



# Creación de socket y vinculación
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print("Registry escuchando en", PORT)
    
    while True:  # Mantener el Registry escuchando indefinidamente
        conn, addr = s.accept()
        with conn:
            handle_connection(conn, addr)

