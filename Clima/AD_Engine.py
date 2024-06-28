import json
import socket
import time
import threading
import os
from Mapa import Mapa
from kafka import KafkaProducer, KafkaConsumer
import curses
import textwrap




# Direcciones y puertos
HOST = os.getenv('HOST_ENGINE')  # Usando 'engine' como valor predeterminado
PORT = int(os.getenv('PORT_ENGINE'))  # Usando 5555 como valor predeterminado
HOST_BROKER = os.getenv('HOST_BROKER')  # Usando 'kafka' como valor predeterminado
PORT_BROKER = int(os.getenv('PORT_BROKER'))  # Usando 19092 como valor predeterminado
CLIMATE_SERVICE_HOST = os.getenv('HOST_WEATHER')  # Usando 'weather' como valor predeterminado
CLIMATE_SERVICE_PORT = int(os.getenv('PORT_WEATHER'))  # Usando 4444 como valor predeterminado


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
        self.info_win = None
        self.map_win = None
       

    def restart(self, info_win):
        self.mapa = None
        self.city = None
        self.weather = False
        # Añadir mensaje a info_win
        info_win.addstr("Recursos liberados.\n")
        # Refrescar info_win para mostrar el mensaje
        info_win.refresh()



    
    def update_map(self, message, map_win):
        # Extraer los datos del mensaje
        drone_id = message['ID_DRON']
        x = message['COORDENADA_X_ACTUAL']
        y = message['COORDENADA_Y_ACTUAL']
        color = message['COLOR']
        # Actualizar la posición en el mapa con los datos del dron
        self.mapa.update_position(x, y, drone_id, color, map_win)
        map_win.refresh()  # Asegurarse de refrescar después de actualizar el mapa

    
    def display_map(self, map_win):
        while self.weather:
            self.mapa.display(map_win)  # Pasando map_win a la función display
            time.sleep(2)  # Pausa para la visualización del mapa (ajusta según sea necesario)

            
    
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

    
    def handle_connection(self, conn, addr, info_win):
        # Mensaje de conexión
        connect_message = f"Conectado por {addr}"
        
        # Ajustar y añadir el mensaje de conexión
        width = info_win.getmaxyx()[1]  # Ancho de info_win
        wrapped_text = textwrap.wrap(connect_message, width)
        for line in wrapped_text:
            info_win.addstr(line + '\n')
        
        data = conn.recv(1024).decode()
        drone_data = json.loads(data)
        id_dron = drone_data["id"]
        token = drone_data["token"]
        drones_registered = self.load_drones()

        # Inicializar la variable response por adelantado
        response = {"status": "error", "message": "Dron no autenticado"}
        
        for dron in drones_registered:
            if dron["id"] == id_dron:
                if dron["token"] == token:
                    auth_message = f"Dron {id_dron} autenticado exitosamente."
                    response = {"status": "success", "message": "Autenticado"}
                else:
                    auth_message = f"Token incorrecto para el dron {id_dron}."
                    response = {"status": "error", "message": "Token incorrecto"}
                
                # Ajustar y añadir el mensaje de autenticación
                wrapped_text = textwrap.wrap(auth_message, width)
                for line in wrapped_text:
                    info_win.addstr(line + '\n')
                break  # Termina el bucle después de manejar la autenticación

        # Refrescar info_win para mostrar los últimos mensajes
        info_win.refresh()
        
        # Envía la respuesta después de recorrer la lista de drones
        conn.sendall(json.dumps(response).encode())       

    
    def autenticate(self, info_win):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            
            # Mensaje de inicio de escucha
            listen_message = f"Engine escuchando en {PORT}"
            
            # Ajustar el mensaje al ancho de info_win y añadirlo
            width = info_win.getmaxyx()[1]
            wrapped_text = textwrap.wrap(listen_message, width)
            for line in wrapped_text:
                info_win.addstr(line + '\n')
            info_win.refresh()
            
            while True:  # Bucle infinito para aceptar conexiones
                conn, addr = s.accept()
                with conn:
                    self.handle_connection(conn, addr, info_win)  # Pasar info_win a handle_connection

    #LISTO
    #################################################
    #Funciones para el Engine SHOW
    #################################################
    # Inicializar el producer de Kafka
    def start_show(self, info_win, map_win):
        producer = KafkaProducer(
            bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'))

        try:
            with open(FILENAME_FIGURAS, 'r') as file:
                data = json.load(file)

            for figure in data['figuras']:
                drones_needed = len(figure['Drones'])   
                for drone_info in figure['Drones']:
                    x_str, y_str = drone_info['POS'].split(',')
                    x = int(x_str)
                    y = int(y_str)

                    x, y = self.wrap_coordinates(x, y)
                    drone_info['POS'] = f"{x},{y}"
                    message = {
                        'ID_DRON': drone_info['ID'],
                        'COORDENADAS': drone_info['POS']
                    }
                    producer.send('engine_to_drons', value=message)
                    producer.flush()

                while not self.all_drones_confirmed(drones_needed, info_win):
                    time.sleep(1)
                    if self.weather == False:
                        self.addstr_wrap(info_win, "Show terminado por condiciones climáticas.")
                        self.backToBase(info_win)
                        break
                    self.addstr_wrap(info_win, "Esperando confirmaciones...")

                self.confirmed_drones.clear()
                self.addstr_wrap(info_win, "Todos los drones han confirmado.")
                time.sleep(5)
            time.sleep(10)

            if self.weather == True:
                self.addstr_wrap(info_win, "Show terminado exitosamente.")
                self.backToBase(info_win)

        except Exception as e:
            self.addstr_wrap(info_win, f"Error: {e}")

        producer.flush()
        producer.close()

    def addstr_wrap(self, info_win, text):
        width = info_win.getmaxyx()[1] - 1  # Ajustar el ancho para el wrapping
        wrapped_text = textwrap.wrap(text, width)
        for line in wrapped_text:
            info_win.addstr(line + '\n')
        info_win.refresh()

    #################################################
    def all_drones_confirmed(self,drones_needed,info_win):
            message = f"CONFIRMED DRONES: {len(self.confirmed_drones)} - DRONES NEEDED: {drones_needed}"
            width = info_win.getmaxyx()[1]# Ajustar el ancho para el wrapping
            wrapped_text = textwrap.wrap(message, width)
            for line in wrapped_text:
                info_win.addstr(line + '\n')
            info_win.refresh()

            return len(self.confirmed_drones) == drones_needed

    def listen_for_confirmations(self):
        consumer = KafkaConsumer('listen_confirmation',
                                    bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
                                    value_deserializer=lambda m: json.loads(m.decode('utf-8')))
        for message in consumer:
                if message.value['STATUS'] == 'LANDED':
                    drone_id = message.value['ID_DRON']
                    self.confirmed_drones.add(drone_id)
        consumer.commit()
        consumer.close()                        
            

    #LISTO
    #################################################
    def backToBase(self, info_win):
        # Contar todos los drones que están en el show
        self.end_show(info_win)

        # Mensaje de retorno a la base
        message = "Todos los drones están volviendo a base."
        
        # Ajustar el mensaje al ancho de info_win
        width = info_win.getmaxyx()[1]  # Ancho de la ventana de info_win
        wrapped_text = textwrap.wrap(message, width)

        # Imprimir cada línea del mensaje ajustado en info_win
        for line in wrapped_text:
            info_win.addstr(line + '\n')
        
        # Refrescar info_win para mostrar el mensaje
        info_win.refresh()

        # Reiniciar el juego y mostrar el menú
        self.restart()
        os._exit(0)
    #################################################
        
        

    #LISTO    
    #################################################
    #Funciones para escuhar los Drones
    #################################################
    def start_listening(self, map_win):
        consumer = KafkaConsumer('drons_to_engine',
                                    group_id='engine',
                                    bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
                                    auto_offset_reset='earliest',
                                    value_deserializer=lambda x: json.loads(x.decode('utf-8')))

        for message in consumer:
            self.process_message(message.value,map_win)

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


    
    def process_message(self, message, map_win):
        ID_DRON = message['ID_DRON']
        COORDENADA_X_ACTUAL = message['COORDENADA_X_ACTUAL']
        COORDENADA_Y_ACTUAL = message['COORDENADA_Y_ACTUAL']
        ESTADO_ACTUAL = message['ESTADO_ACTUAL']
        
        drones = self.load_last_updates()
        dron_found = False

        for dron in drones:
            if dron["ID_DRON"] == ID_DRON:
                dron["COORDENADA_X_ACTUAL"] = COORDENADA_X_ACTUAL
                dron["COORDENADA_Y_ACTUAL"] = COORDENADA_Y_ACTUAL
                dron["ESTADO_ACTUAL"] = ESTADO_ACTUAL
                dron_found = True
                break

        if not dron_found:
            drones.append({
                "ID_DRON": ID_DRON,
                "COORDENADA_X_ACTUAL": COORDENADA_X_ACTUAL,
                "COORDENADA_Y_ACTUAL": COORDENADA_Y_ACTUAL,
                "ESTADO_ACTUAL": ESTADO_ACTUAL
            })
            self.addstr_wrap(self.info_win, f"Nuevo dron registrado en el archivo de actualizaciones. ID: {ID_DRON}")

        if ESTADO_ACTUAL == "MOVING" or ESTADO_ACTUAL == "LANDED":
            self.update_map(message, map_win)
            #refrescar el mapa
            #map_win.refresh()

        self.save_drones(drones)

    #################################################
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
    
    def perform_action_based_on_weather(self, city, info_win):
        weather_data = self.get_weather(city)
        temperature = weather_data["temperature"]
        
        if temperature != "Unknown":
            self.addstr_wrap(info_win, f"La temperatura en {city} es de {temperature} grados.")
            
            if TEMPERATURE_COMFORTABLE_LOW <= temperature <= TEMPERATURE_COMFORTABLE_HIGH:
                self.addstr_wrap(info_win, "Las condiciones climáticas son agradables, el show continúa.")
            elif temperature < TEMPERATURE_COLD_LIMIT or temperature > TEMPERATURE_HOT_LIMIT:
                self.addstr_wrap(info_win, "Advertencia: condiciones climáticas extremas detectadas.")
                self.send_weather_alert(city, temperature, info_win)
            else:
                self.addstr_wrap(info_win, "Las condiciones climáticas están fuera de lo ideal, pero no son extremas.")
        else:
            self.addstr_wrap(info_win, "Datos del clima desconocidos.")
    
    def check_weather_periodically(self, city, info_win):
        while self.weather == True and self.city != None:
            self.addstr_wrap(info_win, f"Chequeando el clima para la ciudad: {city}")
            self.perform_action_based_on_weather(city, info_win)
            time.sleep(10)

    def send_weather_alert(self, city, temperature, info_win):
        alert_message = f"Alerta: Condiciones climáticas no adecuadas en {city}. Temperatura: {temperature} grados. Enviando alerta al sistema de operaciones del show..."
        self.addstr_wrap(info_win, alert_message)
        self.backToBase(info_win)# Asegúrate de que end_show ahora acepte info_win como argumento


    #################################################
    #Produce mensaje en el topic end_show para que los drones sepan que deben terminar el show
    #El mensaje es enviado a todos los drones
    def end_show(self,info_win):
        producer = KafkaProducer(
            bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}', 
            value_serializer=lambda v: json.dumps(v).encode('utf-8'))

        message = {
            'END_SHOW': 'True'
        }
        producer.send('end_show', value=message)
        producer.flush()
        producer.close()
        
        # Añadir mensaje a info_win
        self.info_win.addstr("Show terminado.\n")
        # Refrescar info_win para mostrar el mensaje
        self.info_win.refresh()

        return

    #################################################
    #LISTO
    def start_engine(self, info_win, map_win):
        # Iniciar los métodos en hilos separados

        # Pedir la ciudad al usuario usando curses
        info_win.addstr("Ingrese la ciudad: ")
        info_win.refresh()
        curses.echo()  # Habilita la visualización de la entrada del usuario
        info_win.nodelay(False)  # Hace que getstr espere por la entrada del usuario
        self.city = info_win.getstr().decode()  # Obtener la cadena de entrada y decodificar a str
        curses.noecho()  # Deshabilita la visualización de la entrada del usuario para otras partes de la app
        self.weather = True

       
        # Inicializar los hilos con banderas de detención
        self.dron_update_thread = threading.Thread(target=self.start_listening, args=(map_win,))
        self.map_display_thread = threading.Thread(target=self.display_map, args=(map_win,))
        self.dron_landed_confirmation_thread = threading.Thread(target=self.listen_for_confirmations)
        self.weather_thread = threading.Thread(target=self.check_weather_periodically, args=(self.city, info_win,))
        self.show_thread = threading.Thread(target=self.start_show, args=(info_win,map_win,))
        self.auth_thread = threading.Thread(target=self.autenticate, args=(info_win,))
        #
   

        # ... Iniciar los hilos
        self.show_thread.start()
        self.dron_update_thread.start()
        self.map_display_thread.start()
        self.dron_landed_confirmation_thread.start()
        self.weather_thread.start()
        self.auth_thread.start()


    #LISTO        
    def menu(self, info_win, map_win):
        info_win.clear()
        info_win.addstr("Bienvenido al motor de la aplicación de drones.\n")
        info_win.addstr("Seleccione una opción:\n\n")
        info_win.addstr("1. Iniciar el motor\n")
        info_win.addstr("2. Salir\n")
        info_win.refresh()
        curses.echo()  # Habilita la visualización de la entrada del usuario
        info_win.nodelay(False)  # Hace que getstr espere por la entrada del usuario
        option = info_win.getstr().decode()  # Asegúrate de decodificar correctamente la entrada
        curses.noecho()  # Deshabilita la visualización de la entrada del usuario para otras partes de la app
        curses.curs_set(1)  # Restaurar el cursor

        if option == "1":
            curses.curs_set(0)  # Ocultar el cursor
            self.start_engine(info_win, map_win)
        elif option == "2":
            self.addstr_wrap(info_win, "Saliendo del motor...")
            os._exit(0)
        else:
            self.addstr_wrap(info_win, "Opción inválida")
            self.menu(info_win,map_win)  # Volver a mostrar el menú si la opción es inválida

#################################################
#main de prueba
def main(stdscr):
    # Configurar curses
    # Definir pares de colores
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.start_color()  # Si vas a usar colores
    stdscr.clear()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED)   # Fondo rojo letras negras
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN) # Fondo verde letras negras
    

    try:
        height, width = stdscr.getmaxyx()

        info_width = width // 2
        map_width = width - info_width

        info_win = curses.newwin(height, info_width, 0, 0)
        map_win = curses.newwin(height, map_width, 0, info_width)
        
        info_win.scrollok(True)  # Habilitar el desplazamiento en info_win
        map_win.scrollok(True)  # Habilitar el desplazamiento en map_win si es necesario

        # Iniciar el motor con las ventanas de curses
        engine = Engine()
        engine.menu(info_win,map_win)  # Asegúrate de que menu acepte info_win como argumento

    finally:
        # Restaurar el terminal a su estado original
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()

#################################################
if __name__ == "__main__":
    # Envolver el punto de entrada principal para que curses maneje la inicialización/limpieza
    curses.wrapper(main)    



