import socket
import os
import json
import threading
import random
import time
from kafka import KafkaConsumer, KafkaProducer
from Mapa import Mapa  # Ahora puedes importar Mapa
import colorama




HOST_REGISTRY = os.getenv('HOST_REGISTRY')
PORT_REGISTRY = int(os.getenv('PORT_REGISTRY'))

PORT_ENGINE = int(os.getenv('PORT_ENGINE'))
HOST_ENGINE = os.getenv('HOST_ENGINE')

HOST_BROKER = os.getenv('HOST_BROKER')
PORT_BROKER = os.getenv('PORT_BROKER')

PORT_ENGINE2 = int(os.getenv('PORT_ENGINE2'))

# Estados posibles del dron
STATES = ["WAITING", "MOVING", "LANDED"]
COLORS = ["rojo", "verde"]

CONTADOR = 0


class Dron:
    
    def __init__(self):
        # Asigna el siguiente ID disponible al dron y luego incrementa el contador
        self.id = 1
        self.token = None  # Inicialmente, el dron no tiene un token hasta que se registre
        self.state = STATES[0] # Inicialmente, el dron está en estado "waiting"
        self.position = (1,1) # Inicialmente, el dron está en la posición (1,1)
        self.color = COLORS[0] # Inicialmente, el dron está en estado "waiting"
        self.showState = True #Variable para saber si el dron esta en el show o no
        self.autenticated = False #Variable para saber si el dron esta autenticado o no
    
    #Define el destructor del dron (no imprima nada en el destructor)
    def destroy(self):
        pass

    #Definir los getters y setters para los atributos del dron
    def get_id(self):
        return self.id
    
    

    #LISTO
    # Método para registrar el dron en el Registry
    def register(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST_REGISTRY, PORT_REGISTRY))
            reg_msg = {'id': self.id}
            s.sendall(json.dumps(reg_msg).encode())
            
            data = s.recv(1024)
            if not data:  # Si no se recibe respuesta, imprimir un error y retornar False
                print("No se recibió respuesta del Registry.")
                return False
            
            try:
                response = json.loads(data.decode())
                if response['status'] == 'success':
                    self.token = response['token']
                    print(f"Dron {self.id} registrado exitosamente con el token: {self.token}")
                    return True
                else:
                    if response['message'] == 'Ya registrado':
                        self.token = response['token']
                        print(f"Dron {self.id} ya estaba registrado.")
                        
                    else:
                        print(f"Error al registrar el Dron {self.id}.")
                        return False
            except json.JSONDecodeError:  # Si hay un error al decodificar el JSON, manejarlo
                print("Respuesta del Registry no es un JSON válido.")
                return False

    #Metodo para autenticar el dron con el Engine (usar el token) y
    def autenticate(self):
        #Hacemos un input para obtener el IP del Engine y lo guardamos en la variable HOST_ENGINE
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((HOST_ENGINE, PORT_ENGINE))
                reg_msg = {'id': self.id, 'token': self.token}
                s.sendall(json.dumps(reg_msg).encode())
                
                data = s.recv(1024)
                if not data:  # Si no se recibe respuesta, imprimir un error y retornar False
                    print("No se recibió respuesta del Engine.")
                    self.autenticated = True
                    return True
                
                
                try:
                    response = json.loads(data.decode())
                    if response['status'] == 'success':
                        print(f"Autenticado exitosamente")
                        self.autenticated = True
                        return True
                    else:
                        print(f"Error al Autenticar.El token no es valido o ya fue usado.")
                        return True
                        
                    
                except json.JSONDecodeError:  # Si hay un error al decodificar el JSON, manejarlo
                    print("Respuesta del Registry no es un JSON válido.")
                    return True
                    
            except:
                print("Error al conectarse con el Engine o el Engine no esta disponible.")
                return True

    #Envia una pregunta al Engine para saber si esta disponible
    def is_engine_available(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((HOST_ENGINE, PORT_ENGINE2))
                #Enviamos un mensaje al Engine para saber si esta disponible "Estas disponible?"
                reg_msg = {'message': 'Estas disponible?'}
                s.sendall(json.dumps(reg_msg).encode())
                
                data = s.recv(1024)
                if not data:  # Si no se recibe respuesta, imprimir un error y retornar False
                    print("No se recibió respuesta del Engine.")
                    return False
                else:
                    return True
            except:
                print("Error al conectarse con el Engine o el Engine no esta disponible.")
                return False

    #Funcion que verifica si el engiene esta disponible sino lo esta mandamos los drones a base
    #hace el chequeo cada 5 segundos
    def check_engine(self):
        while True:
            time.sleep(5)
            if self.is_engine_available() == False:
                print("El Engine no esta disponible, volviendo a la base...")
                break
        self.backTobase()        


#################################################
#Comunicacion del Engine con el Dron
#################################################

#LISTO
# El dron necesita saber su propio ID para suscribirse al tópico correcto.
    def recive_data(self):
        try:
            # Inicializar el consumidor de Kafka
            consumer = KafkaConsumer(
                'engine_to_drons',
                group_id=f"dron_group_{self.id}",
                bootstrap_servers=f'{HOST_BROKER}:{PORT_BROKER}',
                auto_offset_reset='earliest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            # Consumir mensajes de Kafka
            for message in consumer:
                self.process_message(message)
                consumer.commit()
        except Exception as e:
            print(f"Error en la conexión de Kafka: {e}")
            # Aquí puedes cambiar al estado que hayas decidido para el dron.
    
    # Función que procesa el mensaje y llama al método run
    def process_message(self,message):
        data = message.value
        if data['ID_DRON'] == self.id:
            ID_DRON = data['ID_DRON']
            COORDENADAS = data['COORDENADAS'].split(",")
            COORDENADA_X_OBJETIVO = int(COORDENADAS[0])
            COORDENADA_Y_OBJETIVO = int(COORDENADAS[1])
            # Si el ID del dron en el mensaje coincide con el ID del dron actual, procesar el mensaje
            self.run((COORDENADA_X_OBJETIVO, COORDENADA_Y_OBJETIVO))
    
    # Método para mover el dron un paso hacia el objetivo
    def move_one_step(self, target_position):
        # Descomponer las coordenadas actuales y objetivo
        x_current, y_current = self.position
        x_target, y_target = target_position
        
        # Determinar la dirección del movimiento en el eje X
        if x_current < x_target:
            x_current += 1
        elif x_current > x_target:
            x_current -= 1

        # Determinar la dirección del movimiento en el eje Y
        if y_current < y_target:
            y_current += 1
        elif y_current > y_target:
            y_current -= 1

        # Actualizar la posición del dron
        self.position = (x_current, y_current)

    # Método para mover el dron a las coordenadas objetivo    
    def run(self, target_position):
    # Moverse hacia la posición objetivo un paso a la vez
        self.state = STATES[1]
        self.color = COLORS[0]
        while self.position != target_position:
            time.sleep(2)
            self.move_one_step(target_position)
            print(f"P:{self.position}, S: {self.state}, M: {target_position}")
            
            # Enviar una actualización al engine después de cada movimiento
            self.send_update()

            # Pausa de un segundo
            if self.showState == False:
                break
        
        if self.showState == False:
            return self.backTobase()
        
        self.state = STATES[2]
        self.color = COLORS[1]
        self.send_update()
        self.send_confirmation()
    
    def backTobase(self):
        self.state = STATES[1]
        while self.position != (1,1):
            self.move_one_step((1,1))
            print(f"P:{self.position}, S: {self.state}, M: {(1,1)}")
            time.sleep(2)

        print("Aterrizado en la base...")
        print("Mis parametros de vuelta a la base son: ")
        self.state = STATES[0]
        self.color = COLORS[0]
        self.showState = True
        #Posiciion actual
        print(f"Posicion actual: {self.position}")
        #Estado actual
        print(f"Estado actual: {self.state}")
        #Color actual
        print(f"Color actual: {self.color}")
        print(f"Mi ID es: {self.id}")
        print(f"Mi token es: {self.token}")
        print()
        print()
        #volver al Menu
        return True

        
    
    def endShow(self):
        #Crear consumidor con el topic end_show y el id del dron
        consumer = KafkaConsumer(
            'end_show',
            group_id=f"dron_group_{self.id}",
            bootstrap_servers = f'{HOST_BROKER}:{PORT_BROKER}',
            auto_offset_reset='earliest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        # Consumir mensajes de Kafka
        for message in consumer:
            data = message.value
            # message = {'END_SHOW': 'True'}
            if data['END_SHOW'] == 'True':
                self.showState = False
                print("END SHOW")
                break
            consumer.commit()
        consumer.close()
        print("Show Terminado volviendo a la base...")
        print()
        return self.backTobase()

    

#################################################


        
#LISTO
#################################################
#Comunicacion del Dron con el Engine
#################################################
# Método para enviar una actualización al Engine
    def send_update(self):
        # Crear el productor de Kafka
        producer = KafkaProducer(
            bootstrap_servers = f'{HOST_BROKER}:{PORT_BROKER}',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Preparar el mensaje en formato JSON
        message = {
            'ID_DRON': self.id,
            'COORDENADA_X_ACTUAL': self.position[0],
            'COORDENADA_Y_ACTUAL': self.position[1],
            'ESTADO_ACTUAL': self.state,
            'COLOR': self.color
        }
        
        # Enviar el mensaje al tópico drones_to_engine
        producer.send('drons_to_engine', value=message)
        
        
        # Cerrar el productor
        producer.close()
        
        # Emitir el mensaje en pantalla
        print("SEND_UPDATE ID de Dron: ", self.id)
    
    # Método para enviar una confirmación al Engine
    def send_confirmation(self):
        producer = KafkaProducer(
            bootstrap_servers = f'{HOST_BROKER}:{PORT_BROKER}',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        message = {
            'ID_DRON': self.id,
            'STATUS': self.state,
            'COORDENADAS': f"{self.position[0]},{self.position[1]}",
            'COLOR': self.color       
        }
        producer.send('listen_confirmation', value=message)
        producer.close() # Cerrar el productor
        
        print(f"SEND_CONFIRMATION: {self.state} y color {self.color}")
        print("Esperando más instrucciones...")
####################################################################
    def run_dron(self):
        if self.autenticated:
            # Iniciar los métodos en hilos separados
            thread1 = threading.Thread(target=self.recive_data)
            thread2 = threading.Thread(target=self.send_update)
            thread3 = threading.Thread(target=self.send_confirmation)
            thread4 = threading.Thread(target=self.endShow)
            thread5 = threading.Thread(target=self.check_engine)

            thread1.start()
            thread2.start()
            thread3.start()
            thread4.start()
            thread5.start()
            return True
        else:
            print("Dron no autenticado: Debe autenticar el dron antes de unirse al show.")
            return True



def solicitar_id():
    id = 0
    while True:
        try:
            id = int(input("Ingrese el id del dron: "))
            if id > 0 and id <= 100:
                print()
                return id
            else:
                print("El id debe ser un número entre 1 y 100")
        #Si el id no es un numero entero se seguira pidiendo el id una y otra vez en un ciclo
        except ValueError:
            print("El id debe ser un número entero")
            continue



#llamar al menu con el dron
def menu(dron):
    global CONTADOR
    if CONTADOR == 0:
        id = solicitar_id()
        dron.set_id(id)
        CONTADOR += 1
    
    print("Bienvenido al menu del Dron")   
    while True:
        print("1. Registrar Dron")
        print("2. Autenticar Dron")
        print("3. Unirse al Show")
        print("4. Salir")
        print()
        #esperar por el input del usuario
        opcion = input("Ingrese una opcion: ")


        if opcion == "1":
            dron.register()
        elif opcion == "2":
            dron.autenticate()
        elif opcion == "3":
            dron.run_dron()
        elif opcion == "4":
            print("Saliendo...")
            break
        else:
            print()
            print("Opcion no valida")
            print()

def main():
    
    # Crear un nuevo dron con un id aleatorio entre 1 y 100
    dron = Dron()
    menu(dron)
    print("Fin del programa el dron con id: ", dron.get_id(), " ha terminado su ejecucion.  ")     
    os._exit(0)
    
if __name__ == '__main__':
    #menu()
    main()