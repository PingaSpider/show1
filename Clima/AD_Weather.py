import json
import socket
import sys
import os  # Nuevo
import threading  # Nuevo



class AD_WEATHER:
    def __init__(self, weather_file,host,port):
        # Inicializa la instancia con la ubicación del archivo de clima.
        self.weather_file = weather_file
        self.engine_host = host
        self.engine_port = port

    def load_weather_data(self):
        # Carga los datos del clima desde el archivo JSON especificado.
        try:
            with open(self.weather_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            # Si el archivo no existe, imprime un mensaje de error y retorna None.
            print("Archivo de clima no encontrado.")
            return None

    def get_temperature(self, city):
        # Obtiene la temperatura para la ciudad dada.
        weather_data = self.load_weather_data()
        if weather_data:
            city_weather = next((item for item in weather_data if item["city"].lower() == city.lower()), None)
            if city_weather:
                # Retorna la temperatura si encuentra la ciudad.
                return {"temperature": city_weather["temperature"]}
        # Retorna "Unknown" si no encuentra datos del clima para la ciudad.
        return {"temperature": "Unknown"}
    

    def start_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.bind((self.engine_host, self.engine_port))
                server_socket.listen()
                print(f"Servidor de clima escuchando en {self.engine_host}:{self.engine_port}")

                while True:
                    try:
                        client_socket, addr = server_socket.accept()
                    except socket.error as e:
                        print(f"Error al aceptar conexiones: {e}")
                        continue
            
                    with client_socket:
                        print(f"Conexión desde {addr}")
                        while True:
                            try:
                                city_bytes = client_socket.recv(1024)
                                if not city_bytes:
                                    print(f"Engine desconectado: {addr}")
                                    break
                                city = city_bytes.decode()
                                weather_data = self.get_temperature(city)
                                client_socket.sendall(json.dumps(weather_data).encode())
                            except socket.error as e:
                                print(f"Error al comunicarse con el Engine: {e}")
                                break
                            except json.JSONDecodeError as e:
                                print(f"Error al decodificar datos JSON: {e}")
                                break

        except socket.error as e:
            print(f"No se pudo iniciar el servidor de clima en {self.engine_host}:{self.engine_port}: {e}")
            sys.exit(1)  # Sale del programa si no puede iniciar el servidor.

    def change_temperature(self):
        # Cambia la temperatura de las ciudades en el archivo JSON.
        weather_data = self.load_weather_data()
        if weather_data:
            while True:
                try:
                    city = input("Ingrese la ciudad a la que desea cambiar la temperatura: ")

                    new_temperature = input("Ingrese la nueva temperatura: ")
                    city_weather = next((item for item in weather_data if item["city"].lower() == city.lower()), None)
                    if city_weather:
                        city_weather["temperature"] = new_temperature
                        with open(self.weather_file, 'w') as file:
                            json.dump(weather_data, file, indent=4)
                        print(f"Temperatura de {city} cambiada a {new_temperature}°C.")
                    else:
                        print(f"No se encontraron datos del clima para {city}.")
                except KeyboardInterrupt:
                    print("Cambio de temperatura cancelado.")
                    break
                except Exception as e:
                    print(f"Error al cambiar la temperatura: {e}")
                    break

def main():
    # Crea una instancia de la clase AD_WEATHER y la inicializa.
    weather_engine = AD_WEATHER(
    "weather_conditions.json",
    os.getenv('HOST_WEATHER', 'weather'),
    int(os.getenv('PORT_WEATHER'))
)
    # Iniciamos el servidor de clima desde un hilo
    threadWeather = threading.Thread(target=weather_engine.start_server)
    threadWeather.start()

    # Iniciamos el cambio de temperatura desde un hilo
    threadChangeTemperature = threading.Thread(target=weather_engine.change_temperature)
    threadChangeTemperature.start()


if __name__ == "__main__":
    main()
