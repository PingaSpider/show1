import json
import socket
import time
import threading
import os
from kafka import KafkaProducer, KafkaConsumer
from Mapa import Mapa  # Ahora puedes importar Mapa







# Direcciones y puertos
HOST = os.getenv('HOST_ENGINE')  # Usando 'engine' como valor predeterminado
PORT = int(os.getenv('PORT_ENGINE'))  # Usando 5555 como valor predeterminado
HOST_BROKER = os.getenv('HOST_BROKER')  # Usando 'kafka' como valor predeterminado
PORT_BROKER = int(os.getenv('PORT_BROKER'))  # Usando 19092 como valor predeterminado
CLIMATE_SERVICE_HOST = os.getenv('HOST_WEATHER')  # Usando 'weather' como valor predeterminado
CLIMATE_SERVICE_PORT = int(os.getenv('PORT_WEATHER'))  # Usando 4444 como valor predeterminado
PORT_ALIVE = int(os.getenv('PORT_ENGINE2'))


# Constantes
TEMPERATURE_COMFORTABLE_LOW = 17
TEMPERATURE_COMFORTABLE_HIGH = 25
TEMPERATURE_COLD_LIMIT = 5
TEMPERATURE_HOT_LIMIT = 38  
END_SHOW_TOPIC = 'end_show'
FILENAME_DRONES = 'data/drones_registry.json'
FILENAME_FIGURAS= 'file/figures.json'
FILENAME_ACTUALIZACIONES = 'file/last_updates.json'


#################################################
# Funciones para el Engine AUTHENTICATION
#################################################
# Leer drones desde JSON
class Engine:

    def __init__(self):
        self.confirmed_drones = set()
        self.mapa = Mapa()
        self.city = None
        self.weather = False
        #diccionario para guardar los drones bloqueados
        self.bloked_id_token = []
       

    def restart(self):
        self.mapa = None
        self.city = None
        self.weather = False
        print("Recursos liberados.")


    
    def update_map(self, message):
        # Extraer los datos del mensaje
        drone_id = message['ID_DRON']
        x = message['COORDENADA_X_ACTUAL']
        y = message['COORDENADA_Y_ACTUAL']
        color = message['COLOR']
        # Actualizar la posición en el mapa con los datos del dron
        self.mapa.update_position(x, y, drone_id, color)



    def display_map(self):
        while self.weather == True: 
            self.mapa.display()
            time.sleep(0.5)
            print()
            
    
    def load_blocked_tokens(self):
        try:
            with open('FILENAME_BLOCKED_TOKENS', 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return []
    
    def load_drones(self):
        try:
            with open(FILENAME_DRONES, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return []
    

    def wrap_coordinates(self, x, y):
        """Envuelve las coordenadas según la geometría esférica del mapa."""
        #Si la coordenada x es 0 se envuelve a la derecha
        # Si la coordenada x es 20 se envuelve a la izquierda
        # Si la coordenada y es 0 se envuelve hacia abajo
        # Si la coordenada y es 20 se envuelve hacia arriba
        if x == 0:
            x = self.mapa.size - 2
        elif x == self.mapa.size - 1:
            x = 1
        if y == 0:
            y = self.mapa.size - 2
        elif y == self.mapa.size - 1:
            y = 1
        return x, y
    

    def handle_connection(self,conn, addr):
        print("Conectado por", addr)
        try:
            data = conn.recv(1024).decode()
            drone_data = json.loads(data)
            id_dron = drone_data["id"]
            token = drone_data["token"]
            drones_registered = self.load_drones()

            response = {"status": "error", "message": "Dron no autenticado"}

            if self.bloked_id_token != []:
                for dron in self.bloked_id_token:
                    if id_dron == dron["id"] and token == dron["token"]:
                        print(f"Dron {id_dron} con token: {token} bloqueado.")
                        response = {"status": "error", "message": "Dron bloqueado"}
                        break
            else:
                for dron in drones_registered:
                    if str(dron["id"]) == str(id_dron):
                        if dron["token"] == token:
                            print(f"Dron {id_dron} autenticado exitosamente.")
                            response = {"status": "success", "message": "Autenticado"}
                            #añadir al diccionario el dron y el token para bloquearlos
                            self.bloked_id_token.append({"id":id_dron,"token":token})
                            break       
                        else:
                            print(f"Token incorrecto.")
                            response = {"status": "error", "message": "Token incorrecto"}

            
            conn.sendall(json.dumps(response).encode())
        except Exception as e:
            print(f"Error: {e}")
    
    def autenticate(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print("Engine escuchando en", PORT)
            
            while True:  # Mantener el Registry escuchando indefinidamente
                conn, addr = s.accept()
                with conn:
                    self.handle_connection(conn, addr)

    #Definimos funcion que envia por sockets una señal de vida a los drones 
    #para que estos sepan que el motor sigue activo
    def send_alive_signal(self):
        # Escuchar por socket indefinidamente para enviar señales de vida a los drones
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT_ALIVE))
            s.listen()
            print("Engine escuchando en", PORT)
            while True:
                conn, addr = s.accept()
                with conn:
                    #El mensaje del dron es "Estas disponible?"
                    data = conn.recv(1024).decode()
                    data2 = json.loads(data)
                    mensaje = data2["message"]
                    #La respuesta del motor es "Si"
                    if mensaje == "Estas disponible?":
                        conn.sendall("Si".encode())

    #LISTO
    #################################################
    #Funciones para el Engine SHOW
    #################################################
    # Inicializar el producer de Kafka
    def start_show(self):
        producer = KafkaProducer(
            bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}', 
            value_serializer=lambda v: json.dumps(v).encode('utf-8'))

        try:

            # Cargar el archivo JSON
            with open(FILENAME_FIGURAS, 'r') as file:
                data = json.load(file)
            
            # Iterar sobre las figuras en el JSON y enviar información al dron
            for figure in data['figuras']:
                #saber la cantidad de drones que se necesitan para la figura y guardarla en una variable
                drones_needed = len(figure['Drones'])
                for drone_info in figure['Drones']:
                    x_str, y_str = drone_info['POS'].split(',')
                    x = int(x_str)
                    y = int(y_str)
                    
                    # Usando wrap_coordinates para ajustar las coordenadas
                    x, y = self.wrap_coordinates(x, y)
                    
                    # Actualizar la posición en el drone_info
                    drone_info['POS'] = f"{x},{y}"
                    message = {
                        'ID_DRON': drone_info['ID'],
                        'COORDENADAS': drone_info['POS']
                    }
                    producer.send('engine_to_drons', value=message)
                    #asegurarse del que el productor solo mande el mensaje una vez
                    producer.flush()
                while not self.all_drones_confirmed(drones_needed):
                    time.sleep(1)  # espera un segundo y vuelve a verificar
                    if self.weather == False:
                        print("Show terminado por condiciones climáticas.")
                        self.backToBase()
                # Una vez que todos los drones han confirmado, limpia el conjunto para la siguiente figura
                self.confirmed_drones.clear()
                if self.weather == False:
                    print("Show terminado por condiciones climáticas.")
                    self.backToBase()
                print("Todos los drones han confirmado.")
                time.sleep(5)  # Espera un segundo antes de enviar la siguiente figura
            time.sleep(10)  # Espera un segundo antes de terminar el show
            if self.weather == True:
                print("Todas las figuras han sido enviadas.")
                print("Show terminado exitosamente.")
                self.backToBase()

        except Exception as e:
            print(f"Error: {e}")
            # Aquí puedes manejar errores adicionales o emitir un mensaje según lo necesites.
        
        # Asegurarse de que todos los mensajes se envían
        producer.flush()
        producer.close()

    def all_drones_confirmed(self,drones_needed):
            print(f"CONFIRMED DRONES: {len(self.confirmed_drones)} - DRONES NEEDED: {drones_needed}")
            return len(self.confirmed_drones) == drones_needed

    def listen_for_confirmations(self):
        consumer = KafkaConsumer('listen_confirmation',
                                    bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
                                    value_deserializer=lambda m: json.loads(m.decode('utf-8')))
        for message in consumer:
                if message.value['STATUS'] == 'LANDED':
                    drone_id = message.value['ID_DRON']
                    self.confirmed_drones.add(drone_id)
                    #actualizar el mapa

        consumer.commit()
        consumer.close()

        self.update_map(message.value)
                  
            

    #LISTO
    #################################################
    def backToBase(self):
        #Contar todos los drones que estan en el show
        self.end_show()
        print("Todos los drones están volviendo a base.")
        print()
        print()

        #terminar el show
        print("El motor se apagará en breves instantes.")
        os._exit(0)
    #################################################
        
        

    #LISTO    
    #################################################
    #Funciones para escuhar los Drones
    #################################################
    def start_listening(self):
        consumer = KafkaConsumer('drons_to_engine',
                                    group_id='engine',
                                    bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
                                    auto_offset_reset='earliest',
                                    value_deserializer=lambda x: json.loads(x.decode('utf-8')))

        for message in consumer:
            self.process_message(message.value)

        consumer.commit()
        consumer.close()

    #LISTO
    def load_last_updates(self):
        try:
            os.makedirs(os.path.dirname(FILENAME_ACTUALIZACIONES), exist_ok=True)
            with open(FILENAME_ACTUALIZACIONES, 'r') as file:
                data = json.load(file)
                if isinstance(data, dict):  # Si es un diccionario, lo convierte en una lista
                    return [data]
                else:
                    return data
        except FileNotFoundError:
            return []

    #LISTO
    def save_drones(self,drones):
        with open(FILENAME_ACTUALIZACIONES, 'w') as file:
            json.dump(drones, file, indent=4)

    #LISTO
    def process_message(self,message):
        # Extraer datos del mensaje
        #print(f"Received message structure: {message}")
        ID_DRON = message['ID_DRON']
        COORDENADA_X_ACTUAL = message['COORDENADA_X_ACTUAL']
        COORDENADA_Y_ACTUAL = message['COORDENADA_Y_ACTUAL']
        ESTADO_ACTUAL = message['ESTADO_ACTUAL']
        
        drones = self.load_last_updates()
        dron_found = False

        # Buscar si el dron ya está registrado y actualizar sus datos si es necesario
        for dron in drones:
            if dron["ID_DRON"] == ID_DRON:
                dron["COORDENADA_X_ACTUAL"] = COORDENADA_X_ACTUAL
                dron["COORDENADA_Y_ACTUAL"] = COORDENADA_Y_ACTUAL
                dron["ESTADO_ACTUAL"] = ESTADO_ACTUAL
                dron_found = True
                #Terminar el bucle una vez que se actualiza el dron
                break

        # Si el dron no fue encontrado en la lista, añadirlo
        if not dron_found:
            drones.append({
                "ID_DRON": ID_DRON,
                "COORDENADA_X_ACTUAL": COORDENADA_X_ACTUAL,
                "COORDENADA_Y_ACTUAL": COORDENADA_Y_ACTUAL,
                "ESTADO_ACTUAL": ESTADO_ACTUAL
            })
            print(f"Nuevo dron registrado en el archivo de actualizaciones. ID: {ID_DRON}")


        #Si el estado actual del dron es LANDED O FLYING, actualizar el mapa
        #if ESTADO_ACTUAL == "MOVING" or ESTADO_ACTUAL == "LANDED":
        self.update_map(message)


        self.save_drones(drones)  # Guardar la lista actualizada de drones

    #LISTO
    #################################################
    #Comunicacion con el Servidor de Clima
    #################################################
    def get_weather(self, city):
        # Comunicarse con el servicio de clima y obtener la temperatura
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((CLIMATE_SERVICE_HOST, CLIMATE_SERVICE_PORT))
            s.sendall(city.encode())
            data = s.recv(1024)
            weather_data = json.loads(data.decode())
            return weather_data

    def perform_action_based_on_weather(self, city):
        weather_data = self.get_weather(city)
        temperature = int(weather_data["temperature"])
        
        if temperature != "Unknown":
            print(f"La temperatura en {city} es de {temperature} grados.")
            
            # Si la temperatura está en el rango agradable, el show continúa.
            if TEMPERATURE_COMFORTABLE_LOW <= temperature <= TEMPERATURE_COMFORTABLE_HIGH:
                print("Las condiciones climáticas son agradables, el show continúa.")
            # Si la temperatura es demasiado fría o demasiado caliente, se recomienda terminar el show.
            elif temperature < TEMPERATURE_COLD_LIMIT or temperature > TEMPERATURE_HOT_LIMIT:
                print("Advertencia: condiciones climáticas extremas detectadas.")
                self.send_weather_alert(city, temperature)
            else:
                print("Las condiciones climáticas están fuera de lo ideal, pero no son extremas.")
        else:
            print("Datos del clima desconocidos.")

    def send_weather_alert(self, city, temperature):
        # Envía una alerta a un sistema o componente que maneja las operaciones del show
        print(f"Alerta: Condiciones climáticas no adecuadas en {city}. Temperatura: {temperature} grados.")
        print("Enviando alerta al sistema de operaciones del show...")
        self.end_show()
        self.weather = False

    def check_weather_periodically(self, city):
        
        while self.weather == True and self.city != None:
            print(f"Chequeando el clima para la ciudad: {city}")
            self.perform_action_based_on_weather(city)
            time.sleep(10)

    #Produce mensaje en el topic end_show para que los drones sepan que deben terminar el show
    #El mensaje es enviado a todos los drones
    def end_show(self):
        producer = KafkaProducer(
            bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}', 
            value_serializer=lambda v: json.dumps(v).encode('utf-8'))

        message = {
                'END_SHOW': 'True'
            }
        producer.send('end_show', value=message)
        producer.flush()
        producer.close()
        
    
    #LISTO
    def start_engine(self):
        # Iniciar los métodos en hilos separados

            # Asegúrate de obtener la ciudad antes de iniciar el hilo meter en self.ciudad
            self.city = input("Ingrese la ciudad: ")
            self.weather = True

            # Inicializar los hilos con banderas de detención
            self.auth_thread = threading.Thread(target=self.autenticate)
            self.show_thread = threading.Thread(target=self.start_show)
            self.dron_update_thread = threading.Thread(target=self.start_listening)
            self.map_display_thread = threading.Thread(target=self.display_map)
            self.dron_landed_confirmation_thread = threading.Thread(target=self.listen_for_confirmations)
            self.weather_thread = threading.Thread(target=self.check_weather_periodically, args=(self.city,))
            self.send_alive_signal = threading.Thread(target=self.send_alive_signal)


            # ... Iniciar los hilos
            self.auth_thread.start()
            self.show_thread.start()
            self.dron_update_thread.start()
            self.map_display_thread.start()
            self.dron_landed_confirmation_thread.start()
            self.weather_thread.start()
            self.send_alive_signal.start()


    #LISTO        
    def menu(self):

        print("Bienvenido al motor de la aplicación de drones.")
        print("Seleccione una opción: ")
        print("1. Iniciar el motor")
        print("2. Salir")
        option = input("Ingrese la opción: ")
        if option == "1":
            self.start_engine()
        elif option == "2":
            print("Saliendo del motor...")
            os._exit(0)
            
        else:
            print("Opción inválida")
            self.menu()

#main de prueba
def main():  
    try:
        engine = Engine()
        #vaciar el archivo de actualizacion "FILENAME_ACTUALIZACIONES"
        with open(FILENAME_ACTUALIZACIONES, 'w') as file:
            json.dump([], file, indent=4)
        engine.menu()
    #Si se presiona la letra q se detiene el motor y se limpia
    except KeyboardInterrupt:
        engine.restart()
        print("Programa terminado por el usuario.")    


if __name__ == "__main__":
    main()


    




