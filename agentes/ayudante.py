import random

from .markov import siguiente_estado, validar_transiciones


# Cadena de Markov del ciclo de trabajo. Es lineal (no se salta ninguna
# etapa): las únicas decisiones con azar son repetir una etapa o, tras
# guardar, decidir si seguir con otro ciclo.
TRANSICIONES_AYUDANTE = {
    "DESOCUPADO": [("BUSCANDO_PLATOS", 1.0)],
    "BUSCANDO_PLATOS": [("RECOGIENDO_PLATOS", 1.0)],
    "RECOGIENDO_PLATOS": [("LLEVANDO_AL_LAVAPLATOS", 1.0)],
    "LLEVANDO_AL_LAVAPLATOS": [("LAVANDO", 1.0)],
    "LAVANDO": [("SECANDO", 0.9), ("LAVANDO", 0.1)],  # 10%: quedó sucio
    "SECANDO": [("GUARDANDO", 0.9), ("SECANDO", 0.1)],  # 10%: sigue húmedo
    "GUARDANDO": [("DESOCUPADO", 0.5), ("BUSCANDO_PLATOS", 0.5)],
}
# DESCANSANDO no está en la cadena a propósito: entrar y salir de ese estado
# lo decide la energía (determinista), no el azar. Mezclarlo con las
# probabilidades ocultaría el efecto del sistema de energía.
validar_transiciones(TRANSICIONES_AYUDANTE)

# Duración (en segundos) de cada estado, en función de los platos cargados.
# Vive aparte de la cadena porque la cadena solo dice A DÓNDE ir, no cuánto
# dura; así una etapa repetida vuelve a durar lo mismo que la primera vez.
DURACIONES_AYUDANTE = {
    "DESOCUPADO": lambda carga: 0,
    "BUSCANDO_PLATOS": lambda carga: 2,
    "RECOGIENDO_PLATOS": lambda carga: 1,
    "LLEVANDO_AL_LAVAPLATOS": lambda carga: 2,
    "LAVANDO": lambda carga: 3 * carga,
    "SECANDO": lambda carga: 2 * carga,
    "GUARDANDO": lambda carga: 1,
}


class Ayudante:
    """Agente que recoge, lava, seca y guarda los platos.

    Incluye un sistema dinámico de energía: cada acción del ciclo
    (buscar, recoger, llevar, lavar, secar, guardar) consume energía y,
    si esta se agota, el ayudante entra en reposo (DESCANSANDO) hasta
    recuperar lo suficiente para seguir trabajando.

    Ecuación del sistema (integrador discreto, un paso = 1 segundo):

        E(t+1) = clamp(E(t) - gasto(estado_completado) + r * [estado == DESCANSANDO],
                        0, E_max)

    donde `gasto(estado)` es el costo fijo de completar esa etapa del
    ciclo (tabla ``COSTOS_ENERGIA``) y ``r`` es ``TASA_RECUPERACION``
    (energía recuperada por segundo en reposo).
    """

    ENERGIA_MAXIMA = 100
    ENERGIA_MINIMA_PARA_TRABAJAR = 20
    TASA_RECUPERACION = 8

    # Costo de energía al completar cada etapa del ciclo.
    COSTOS_ENERGIA = {
        "BUSCANDO_PLATOS": 3,
        "RECOGIENDO_PLATOS": 4,
        "LLEVANDO_AL_LAVAPLATOS": 3,
        "LAVANDO": 6,
        "SECANDO": 4,
        "GUARDANDO": 3,
    }

    def __init__(self, capacidad=3, rng=None):
        # La simulación pasa su propio generador (self.aleatorio) para que
        # las decisiones de la cadena dependan de la semilla global.
        self.rng = rng if rng is not None else random.Random()
        # Callback que la simulación conecta para registrar cada sorteo.
        self.registro_markov = None
        self.estado = "DESOCUPADO"
        self.capacidad = capacidad
        self.carga = 0
        self.tiempo_restante = 0
        self.tiempo_ocupado = 0
        self.platos_lavados = 0

        self.energia = self.ENERGIA_MAXIMA
        self.estado_antes_descanso = None
        self.tiempo_restante_antes_descanso = 0

    def cambiar_estado(self, nuevo_estado, duracion):
        self.estado = nuevo_estado
        self.tiempo_restante = duracion

    def gastar_energia(self, estado_completado):
        costo = self.COSTOS_ENERGIA.get(estado_completado, 0)
        self.energia = max(0, self.energia - costo)

    def recuperar_energia(self):
        self.energia = min(self.ENERGIA_MAXIMA, self.energia + self.TASA_RECUPERACION)

    def barra_energia(self):
        ancho = 20
        llenos = round(self.energia / self.ENERGIA_MAXIMA * ancho)
        barra = "█" * llenos + "░" * (ancho - llenos)
        return f"[ENERGÍA] |{barra}| {self.energia}/{self.ENERGIA_MAXIMA}"

    def actualizar(self, platos_sucios):
        """Devuelve (platos_recogidos, platos_limpios, mensaje)."""
        recogidos = 0
        limpios = 0
        mensaje = None

        if self.estado == "DESCANSANDO":
            self.recuperar_energia()
            if self.energia >= self.ENERGIA_MINIMA_PARA_TRABAJAR:
                self.estado = self.estado_antes_descanso
                self.tiempo_restante = self.tiempo_restante_antes_descanso
                mensaje = "El ayudante recuperó energía y retoma su labor"
            return recogidos, limpios, mensaje

        if self.estado == "DESOCUPADO":
            # Arrancar depende de que haya platos sucios (recurso), no del
            # azar; por eso esta salida se decide aquí y no se sortea.
            if platos_sucios > 0:
                self.cambiar_estado(
                    "BUSCANDO_PLATOS", DURACIONES_AYUDANTE["BUSCANDO_PLATOS"](0)
                )
                mensaje = "El ayudante comenzó a buscar platos sucios"
            return recogidos, limpios, mensaje

        if self.energia <= 0:
            self.estado_antes_descanso = self.estado
            self.tiempo_restante_antes_descanso = self.tiempo_restante
            self.estado = "DESCANSANDO"
            mensaje = "El ayudante se quedó sin energía y va a descansar"
            return recogidos, limpios, mensaje

        self.tiempo_ocupado += 1
        self.tiempo_restante -= 1

        if self.tiempo_restante > 0:
            return recogidos, limpios, mensaje

        estado_completado = self.estado

        # Efectos sobre los platos: dependen de los recursos, no del azar,
        # así que se aplican antes de sortear el siguiente estado.
        sin_platos = False
        if estado_completado == "RECOGIENDO_PLATOS":
            self.carga = min(self.capacidad, platos_sucios)
            recogidos = self.carga
            if self.carga == 0:
                # No había nada que recoger: se vuelve a DESOCUPADO sin
                # sortear (la cadena solo modela el ciclo con platos).
                sin_platos = True
            else:
                mensaje = f"El ayudante recogió {self.carga} plato(s)"

        elif estado_completado == "GUARDANDO":
            limpios = self.carga
            self.platos_lavados += self.carga
            mensaje = f"El ayudante guardó {self.carga} plato(s) limpio(s)"
            self.carga = 0

        if sin_platos:
            siguiente = "DESOCUPADO"
        else:
            siguiente = siguiente_estado(
                TRANSICIONES_AYUDANTE,
                estado_completado,
                self.rng,
                self.registro_markov,
            )
        self.cambiar_estado(siguiente, DURACIONES_AYUDANTE[siguiente](self.carga))

        if siguiente == estado_completado:
            mensaje = f"El ayudante repite la etapa {estado_completado}"

        # Se gasta energía por la etapa que se acaba de completar, también
        # cuando se repite: repetir es volver a hacer el esfuerzo completo.
        self.gastar_energia(estado_completado)

        return recogidos, limpios, mensaje
