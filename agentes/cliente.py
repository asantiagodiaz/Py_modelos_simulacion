import random

from .markov import siguiente_estado, validar_transiciones


# Cadena de Markov del cliente. Es lineal: la mayoría de estados tiene una
# única salida (prob 1.0) para que la tabla quede completa. La única decisión
# real está al terminar de comer: 30% vuelve a hacer fila, 70% se va.
TRANSICIONES_CLIENTE = {
    "ESPERANDO_PEDIDO": [("ESPERANDO_COMIDA", 1.0)],
    "ESPERANDO_COMIDA": [("BUSCANDO_MESA", 1.0)],
    # Si no hay mesa libre, el simulador lo desvía a ESPERANDO_MESA: es una
    # regla de recursos (determinista), no una decisión aleatoria.
    "BUSCANDO_MESA": [("COMIENDO", 1.0)],
    "ESPERANDO_MESA": [("COMIENDO", 1.0)],
    "COMIENDO": [("SALIENDO", 1.0)],
    "SALIENDO": [("HACER_FILA", 0.3), ("FIN", 0.7)],
    "HACER_FILA": [("ESPERANDO_PEDIDO", 1.0)],
}
# ABANDONO no está en la cadena: se produce por agotarse la paciencia
# (regla por tiempo), no por una probabilidad de transición. FIN es terminal.
validar_transiciones(TRANSICIONES_CLIENTE, terminales=("FIN",))

PACIENCIA_PEDIDO = 45
PACIENCIA_MESA = 35


class Cliente:
    """Agente que cambia de estado durante su paso por el restaurante."""

    def __init__(
        self, numero, llegada, receta, tiempo_preparacion, tiempo_comida, rng=None
    ):
        # Generador de la simulación (self.aleatorio) para conservar la
        # reproducibilidad con semilla; si no se da, uno propio (solo pruebas).
        self.rng = rng if rng is not None else random.Random()
        # Callback que la simulación conecta para registrar cada sorteo.
        self.registro_markov = None
        self.numero = numero
        self.visitas = 1
        self._iniciar_visita(llegada, receta, tiempo_preparacion, tiempo_comida)

    def _iniciar_visita(self, llegada, receta, tiempo_preparacion, tiempo_comida):
        """Deja al cliente listo para una visita: todo lo que depende del
        pedido y de los tiempos se reinicia aquí, en un solo lugar."""
        self.llegada = llegada
        self.receta = receta
        self.tiempo_preparacion = tiempo_preparacion
        self.tiempo_comida = tiempo_comida

        self.estado = "ESPERANDO_PEDIDO"
        self.tiempo_en_estado = 0
        self.paciencia_pedido = PACIENCIA_PEDIDO
        self.paciencia_mesa = PACIENCIA_MESA
        self.inicio_atencion = None
        self.salida = None

    def nueva_visita(self, llegada, receta, tiempo_preparacion, tiempo_comida):
        """El cliente vuelve a la fila como una VISITA NUEVA.

        Se reinicia llegada, paciencia y tiempos en vez de acumularlos: así
        Wq y el tiempo en el sistema se miden por visita, sin arrastrar los
        tiempos de la anterior, y no hace falta tratarlo como otro cliente.
        """
        self.visitas += 1
        self._iniciar_visita(llegada, receta, tiempo_preparacion, tiempo_comida)

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
                self.cambiar_estado(
                    siguiente_estado(
                        TRANSICIONES_CLIENTE, "COMIENDO", self.rng, self.registro_markov
                    )
                )
                return "termina_comida"

        elif self.estado == "SALIENDO":
            # Aquí ocurre la decisión probabilística: volver a la fila o irse.
            destino = siguiente_estado(
                TRANSICIONES_CLIENTE, "SALIENDO", self.rng, self.registro_markov
            )
            self.cambiar_estado(destino)
            # Si vuelve, la simulación lo reingresa con nueva_visita().
            return "vuelve_a_fila" if destino == "HACER_FILA" else "sale"

        return None
