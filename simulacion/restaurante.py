import random

from agentes import Ayudante, Cliente


RECETAS = [
    ("Ensalada fresca", 7),
    ("Sándwich clásico", 8),
    ("Hamburguesa verde", 10),
    ("Hamburguesa completa", 12),
    ("Ensalada proteica", 9),
]


class SimulacionRestaurante:
    """Controla los agentes y los recursos compartidos del restaurante."""

    def __init__(self, duracion=300, semilla=7, mostrar_eventos=True):
        self.duracion = duracion
        self.mostrar_eventos = mostrar_eventos
        self.aleatorio = random.Random(semilla)

        # Parámetros que se pueden cambiar para probar otros escenarios.
        self.tasa_llegada = 0.10
        self.capacidad_cola = 7
        self.total_mesas = 3
        self.platos_limpios = 6

        self.tiempo = 0
        self.proxima_llegada = self.generar_intervalo_llegada()
        self.siguiente_numero = 1
        self.clientes = []
        self.cola_pedidos = []
        self.cola_mesas = []
        self.cliente_en_cocina = None
        self.tiempo_cocina = 0
        self.mesas_ocupadas = 0
        self.platos_sucios = 0
        self.ayudante = Ayudante()

        # Acumuladores para calcular las métricas al final.
        self.area_cola = 0
        self.area_cola_mesas = 0
        self.area_platos_sucios = 0
        self.area_mesas_ocupadas = 0
        self.tiempo_cocina_ocupada = 0
        self.tiempos_espera = []
        self.tiempos_sistema = []

    def generar_intervalo_llegada(self):
        """Genera llegadas tipo Poisson usando tiempos exponenciales."""
        intervalo = self.aleatorio.expovariate(self.tasa_llegada)
        return max(1, round(intervalo))

    def escribir_evento(self, mensaje):
        if self.mostrar_eventos:
            print(f"[{self.tiempo:3d} s] {mensaje}")

    def crear_cliente(self):
        receta, tiempo_base = self.aleatorio.choice(RECETAS)
        tiempo_preparacion = tiempo_base + self.aleatorio.randint(-1, 2)
        tiempo_comida = self.aleatorio.randint(18, 30)

        cliente = Cliente(
            self.siguiente_numero,
            self.tiempo,
            receta,
            tiempo_preparacion,
            tiempo_comida,
        )
        self.siguiente_numero += 1
        self.clientes.append(cliente)

        if len(self.cola_pedidos) >= self.capacidad_cola:
            cliente.cambiar_estado("ABANDONO")
            cliente.salida = self.tiempo
            self.escribir_evento(
                f"Cliente {cliente.numero} llegó, pero la cola estaba llena"
            )
        else:
            self.cola_pedidos.append(cliente)
            self.escribir_evento(
                f"Llegó cliente {cliente.numero}: {cliente.receta}"
            )

    def procesar_llegadas(self):
        self.proxima_llegada -= 1
        if self.proxima_llegada <= 0:
            self.crear_cliente()
            self.proxima_llegada = self.generar_intervalo_llegada()

    def actualizar_clientes(self):
        """Actualiza paciencia, comida y salida de cada cliente."""
        for cliente in self.clientes:
            evento = cliente.actualizar()

            if evento == "abandona_pedido":
                if cliente in self.cola_pedidos:
                    self.cola_pedidos.remove(cliente)
                cliente.salida = self.tiempo
                self.escribir_evento(
                    f"Cliente {cliente.numero} abandonó la cola por demora"
                )

            elif evento == "abandona_mesa":
                if cliente in self.cola_mesas:
                    self.cola_mesas.remove(cliente)
                self.platos_sucios += 1
                cliente.salida = self.tiempo
                self.escribir_evento(
                    f"Cliente {cliente.numero} abandonó esperando una mesa"
                )

            elif evento == "termina_comida":
                self.mesas_ocupadas -= 1
                self.platos_sucios += 1
                self.escribir_evento(
                    f"Cliente {cliente.numero} terminó de comer y dejó un plato sucio"
                )

            elif evento == "sale":
                cliente.salida = self.tiempo
                self.tiempos_sistema.append(cliente.salida - cliente.llegada)

    def actualizar_cocina(self):
        """La cocina es un único servidor que atiende la cola FIFO."""
        if self.cliente_en_cocina is not None:
            self.tiempo_cocina_ocupada += 1
            self.tiempo_cocina -= 1

            if self.tiempo_cocina <= 0:
                cliente = self.cliente_en_cocina
                cliente.cambiar_estado("BUSCANDO_MESA")
                self.cliente_en_cocina = None
                self.escribir_evento(
                    f"Pedido del cliente {cliente.numero} terminado"
                )
                self.enviar_a_mesa(cliente)

        if self.cliente_en_cocina is None and self.cola_pedidos:
            if self.platos_limpios == 0:
                return

            cliente = self.cola_pedidos.pop(0)
            cliente.inicio_atencion = self.tiempo
            cliente.cambiar_estado("ESPERANDO_COMIDA")
            self.tiempos_espera.append(self.tiempo - cliente.llegada)
            self.cliente_en_cocina = cliente
            self.tiempo_cocina = cliente.tiempo_preparacion
            self.platos_limpios -= 1
            self.escribir_evento(
                f"Cocina comenzó el pedido del cliente {cliente.numero}"
            )

    def enviar_a_mesa(self, cliente):
        if self.mesas_ocupadas < self.total_mesas:
            self.mesas_ocupadas += 1
            cliente.cambiar_estado("COMIENDO")
            self.escribir_evento(
                f"Cliente {cliente.numero} ocupó una mesa"
            )
        else:
            cliente.cambiar_estado("ESPERANDO_MESA")
            self.cola_mesas.append(cliente)
            self.escribir_evento(
                f"Cliente {cliente.numero} está esperando una mesa"
            )

    def asignar_mesas_libres(self):
        while self.cola_mesas and self.mesas_ocupadas < self.total_mesas:
            cliente = self.cola_mesas.pop(0)
            self.mesas_ocupadas += 1
            cliente.cambiar_estado("COMIENDO")
            self.escribir_evento(
                f"Cliente {cliente.numero} recibió una mesa libre"
            )

    def actualizar_ayudante(self):
        recogidos, limpios, mensaje = self.ayudante.actualizar(self.platos_sucios)
        self.platos_sucios -= recogidos
        self.platos_limpios += limpios
        if mensaje:
            self.escribir_evento(mensaje)
        self.escribir_evento(
            f"Ayudante [{self.ayudante.estado}] {self.ayudante.barra_energia()}"
        )

    def acumular_metricas(self):
        self.area_cola += len(self.cola_pedidos)
        self.area_cola_mesas += len(self.cola_mesas)
        self.area_platos_sucios += self.platos_sucios
        self.area_mesas_ocupadas += self.mesas_ocupadas

    def ejecutar(self):
        if self.mostrar_eventos:
            print("=" * 58)
            print("SIMULACIÓN AUTOMÁTICA DEL RESTAURANTE")
            print("=" * 58)

        for segundo in range(1, self.duracion + 1):
            self.tiempo = segundo
            self.procesar_llegadas()
            self.acumular_metricas()
            self.actualizar_clientes()
            self.asignar_mesas_libres()
            self.actualizar_cocina()
            self.actualizar_ayudante()

            if self.mostrar_eventos and segundo % 60 == 0:
                self.mostrar_estado_actual()

    def mostrar_estado_actual(self):
        print(
            f"--- Minuto {self.tiempo // 60}: "
            f"cola={len(self.cola_pedidos)}, "
            f"mesas={self.mesas_ocupadas}/{self.total_mesas}, "
            f"platos limpios={self.platos_limpios}, "
            f"platos sucios={self.platos_sucios}, "
            f"ayudante={self.ayudante.estado} ---"
        )
        print(f"    {self.ayudante.barra_energia()}")

    def promedio(self, datos):
        if not datos:
            return 0
        return sum(datos) / len(datos)

    def mostrar_resultados(self):
        llegadas = len(self.clientes)
        completados = len([c for c in self.clientes if c.estado == "FIN"])
        abandonos = len([c for c in self.clientes if c.estado == "ABANDONO"])
        en_sistema = llegadas - completados - abandonos

        lq = self.area_cola / self.duracion
        wq = self.promedio(self.tiempos_espera)
        utilizacion_cocina = self.tiempo_cocina_ocupada / self.duracion
        utilizacion_ayudante = self.ayudante.tiempo_ocupado / self.duracion
        utilizacion_mesas = self.area_mesas_ocupadas / (
            self.total_mesas * self.duracion
        )
        tasa_salida = completados / self.duracion * 60

        print("\n" + "=" * 58)
        print("RESULTADOS")
        print("=" * 58)
        print(f"Tiempo simulado:                 {self.duracion} segundos")
        print(f"Clientes que llegaron:           {llegadas}")
        print(f"Clientes que completaron:        {completados}")
        print(f"Clientes que abandonaron:        {abandonos}")
        print(f"Clientes todavía en el sistema:  {en_sistema}")
        print(f"Platos lavados por el ayudante:  {self.ayudante.platos_lavados}")
        print("-" * 58)
        print(f"Lq - longitud promedio cola:     {lq:.2f} clientes")
        print(f"Wq - espera promedio:            {wq:.2f} segundos")
        print(f"Cola promedio para mesas:        {self.area_cola_mesas / self.duracion:.2f} clientes")
        print(f"Tiempo promedio en el sistema:   {self.promedio(self.tiempos_sistema):.2f} segundos")
        print(f"Utilización de la cocina:        {utilizacion_cocina * 100:.1f}%")
        print(f"Utilización del ayudante:        {utilizacion_ayudante * 100:.1f}%")
        print(f"Utilización de las mesas:        {utilizacion_mesas * 100:.1f}%")
        print(f"Promedio de platos sucios:       {self.area_platos_sucios / self.duracion:.2f}")
        print(f"Tasa de salida:                  {tasa_salida:.2f} clientes/minuto")
        print(f"Probabilidad de abandono:        {abandonos / llegadas * 100 if llegadas else 0:.1f}%")
