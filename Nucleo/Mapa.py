import colorama

class Mapa:

    def __init__(self, size=20):
        self.size = size
        # Asegura espacios de ancho fijo para cada celda, incluidos los bordes
        self.grid = [[' ' * 2 for _ in range(size)] for _ in range(size)]
        
        # Establece los bordes con un punto y de fondo azul
        for i in range(size):
            self.grid[i][0] = colorama.Back.BLUE + '  ' + colorama.Style.RESET_ALL
            self.grid[i][size-1] = colorama.Back.BLUE + '  ' + colorama.Style.RESET_ALL
            self.grid[0][i] = colorama.Back.BLUE + '  ' + colorama.Style.RESET_ALL
            self.grid[size-1][i] = colorama.Back.BLUE + '  ' + colorama.Style.RESET_ALL
        
        
        self.drones_positions = {}
        self.dron_solapado = {}
    def update_position(self, new_x, new_y, id, color):
        # Verifica si la posición está dentro del mapa
        if new_x < 0 or new_x >= self.size or new_y < 0 or new_y >= self.size:
            raise ValueError("Posición inválida")

        # Verifica si el dron ya está en el mapa y obtiene su posición anterior
        old_position = self.drones_positions.get(id)
        if old_position:
            old_x, old_y, _ = old_position
            # Revisa si había otros drones en la posición anterior y los actualiza
            overlapped_drones = self.dron_solapado.get((old_y, old_x), [])
            if id in overlapped_drones:
                overlapped_drones.remove(id)
                if overlapped_drones:
                    # Coloca el siguiente dron en la lista si hay alguno
                    next_drone_id = overlapped_drones[0]
                    # Obtiene la información del siguiente dron
                    next_drone_color = self.drones_positions[next_drone_id][2]
                    # Coloca el siguiente dron en la posición anterior
                    self.place_drone(old_x, old_y, next_drone_id, next_drone_color)
                    #
                    self.dron_solapado[(old_y, old_x)] = overlapped_drones
                else:
                    # Si no hay más drones, elimina la entrada del diccionario y limpia la posición
                    self.dron_solapado.pop((old_y, old_x), None)
                    self.grid[old_y][old_x] = '  '  # Limpia con espacios de ancho fijo

        # Mueve el dron a la nueva posición
        overlapped_drones = self.dron_solapado.get((new_y, new_x), [])
        # Verifica si hay otros drones en la nueva posición
        if overlapped_drones:
            # Si ya hay drones en la posición, agrega el dron a la lista y coloca el nuevo dron con color de solapamiento
            overlapped_drones.append(id)
            self.dron_solapado[(new_y, new_x)] = overlapped_drones
            self.place_drone(new_x, new_y, id, "amarillo")  # Usa el color amarillo para indicar solapamiento
        else:
            # Si no hay drones, coloca el dron y actualiza las posiciones
            self.dron_solapado[(new_y, new_x)] = [id]
            self.place_drone(new_x, new_y, id, color)

        # Actualiza el diccionario de posiciones de drones con la nueva posición y color
        self.drones_positions[id] = (new_x, new_y, color)
        

    def place_drone(self, x, y, id, color):
        # Asegúrate de que el id es una cadena de dos caracteres, añadiendo un cero si es necesario
        id_str = f"{id:02d}"

        # Aplicar los códigos de color de colorama
        color_code = colorama.Back.RED if color == "rojo" else colorama.Back.GREEN if color == "verde" else colorama.Back.YELLOW


        #text_color = colorama.Fore.WHITE if color == "rojo" else colorama.Fore.BLACK
        text_color = colorama.Fore.BLACK if color in ["amarillo", "verde"] else colorama.Fore.WHITE

        # Representación del dron con el color de fondo y el color del texto
        drone_representation = color_code + text_color + id_str + colorama.Style.RESET_ALL

        # Colocar la representación formateada del dron en la cuadrícula
        self.grid[y][x] = drone_representation

    
    def display(self):
        # Imprimir la cuadrícula línea por línea
        for row in self.grid:
            print(''.join(row))


