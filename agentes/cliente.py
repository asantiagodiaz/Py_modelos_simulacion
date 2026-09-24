class Cliente:
    """Agente que cambia de estado durante su paso por el restaurante."""

    def __init__(self, numero, llegada, receta, tiempo_preparacion, tiempo_comida):
        self.numero = numero
        self.llegada = llegada
        self.receta = receta
        self.tiempo_preparacion = tiempo_preparacion
        self.tiempo_comida = tiempo_comida

        self.estado = "ESPERANDO_PEDIDO"
        self.tiempo_en_estado = 0
        self.paciencia_pedido = 45
        self.paciencia_mesa = 35
        self.inicio_atencion = None
        self.salida = None

    def cambiar_estado(self, nuevo_estado):
        self.estado = nuevo_estado
        self.tiempo_en_estado = 0

    def actualizar(self):
        """Avanza un segundo y devuelve un evento si ocurre algo importante."""
        self.tiempo_en_estado += 1

        if self.estado == "ESPERANDO_PEDIDO":
            self.paciencia_pedido -= 1
            if self.paciencia_pedido <= 0:
                self.cambiar_estado("ABANDONO")
                return "abandona_pedido"

        elif self.estado == "ESPERANDO_MESA":
            self.paciencia_mesa -= 1
            if self.paciencia_mesa <= 0:
                self.cambiar_estado("ABANDONO")
                return "abandona_mesa"

        elif self.estado == "COMIENDO":
            self.tiempo_comida -= 1
            if self.tiempo_comida <= 0:
                self.cambiar_estado("SALIENDO")
                return "termina_comida"

        elif self.estado == "SALIENDO":
            self.cambiar_estado("FIN")
            return "sale"

        return None
