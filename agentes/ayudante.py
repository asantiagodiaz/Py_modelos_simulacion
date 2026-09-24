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

    def __init__(self, capacidad=3):
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
            if platos_sucios > 0:
                self.cambiar_estado("BUSCANDO_PLATOS", 2)
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

        if self.estado == "BUSCANDO_PLATOS":
            self.cambiar_estado("RECOGIENDO_PLATOS", 1)

        elif self.estado == "RECOGIENDO_PLATOS":
            self.carga = min(self.capacidad, platos_sucios)
            recogidos = self.carga
            if self.carga == 0:
                self.cambiar_estado("DESOCUPADO", 0)
            else:
                self.cambiar_estado("LLEVANDO_AL_LAVAPLATOS", 2)
                mensaje = f"El ayudante recogió {self.carga} plato(s)"

        elif self.estado == "LLEVANDO_AL_LAVAPLATOS":
            self.cambiar_estado("LAVANDO", 3 * self.carga)

        elif self.estado == "LAVANDO":
            self.cambiar_estado("SECANDO", 2 * self.carga)

        elif self.estado == "SECANDO":
            self.cambiar_estado("GUARDANDO", 1)

        elif self.estado == "GUARDANDO":
            limpios = self.carga
            self.platos_lavados += self.carga
            mensaje = f"El ayudante guardó {self.carga} plato(s) limpio(s)"
            self.carga = 0
            self.cambiar_estado("DESOCUPADO", 0)

        self.gastar_energia(estado_completado)

        return recogidos, limpios, mensaje
