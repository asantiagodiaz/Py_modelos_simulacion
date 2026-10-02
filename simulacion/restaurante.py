import json
import os
import random

from agentes import Ayudante, Cliente
from agentes.ayudante import (
    TRANSICIONES_AYUDANTE,
    TRANSICION_OCULTA_RENDIMIENTO,
    EMISION_RENDIMIENTO,
    PI_RENDIMIENTO,
)
from agentes.cliente import TRANSICIONES_CLIENTE
from agentes.hmm import viterbi
from agentes.juegos import (
    PAYOFFS_COCINERO,
    PROB_ERROR_RAPIDO,
    FACTOR_RAPIDO,
    PENALIZACION_ERROR,
    clasificar_cola,
    elegir_estrategia,
    ocurre_error,
)


RECETAS = [
    ("Ensalada fresca", 7),
    ("Sándwich clásico", 8),
    ("Hamburguesa verde", 10),
    ("Hamburguesa completa", 12),
    ("Ensalada proteica", 9),
]


class SimulacionRestaurante:
    """Controla los agentes y los recursos compartidos del restaurante."""

    def __init__(
        self,
        duracion=300,
        semilla=7,
        mostrar_eventos=True,
        mostrar_markov=False,
        resumen_markov=False,
        resumen_hmm=False,
        resumen_juegos=False,
        carpeta_salida=None,
    ):
        self.duracion = duracion
        self.semilla = semilla
        self.mostrar_eventos = mostrar_eventos
        # Cada sorteo de Markov en consola (ruidoso; siempre va al archivo).
        self.mostrar_markov = mostrar_markov
        # Tablas al inicio y frecuencias observadas al final, en consola.
        self.resumen_markov = resumen_markov
        # Inferencia Viterbi del rendimiento oculto del ayudante, al final.
        self.resumen_hmm = resumen_hmm
        # Decisiones del cocinero y tasa de error, al final.
        self.resumen_juegos = resumen_juegos
        # Si se da una carpeta, guardar_salida() escribe ahí el detalle.
        self.carpeta_salida = carpeta_salida
        # Bitácora completa: se llena siempre (aunque no se imprima) para
        # poder volcarla a archivo sin saturar la consola.
        self.bitacora = []
        # Veces que ocurrió cada sorteo: (agente, origen, destino) -> conteo.
        self.conteo_markov = {}
        # Veces que el cocinero eligió cada estrategia por condición de
        # cola: (condicion, estrategia) -> conteo.
        self.conteo_estrategias = {}
        self.errores_cocina = 0
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
        self.ayudante = Ayudante(rng=self.aleatorio)
        self.ayudante.registro_markov = self.crear_registro_markov("Ayudante")
        self.ayudante.registro_hmm_transicion = self.crear_registro_markov(
            "Ayudante-Rendimiento"
        )
        self.ayudante.registro_hmm_emision = self.crear_registro_markov(
            "Ayudante-Observacion"
        )
        self.registro_juegos = self.crear_registro_estrategia()
        self.ultimo_estado_ayudante = self.ayudante.estado
        self.reingresos = 0

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

    def escribir_evento(self, mensaje, consola=None):
        """Guarda el evento en la bitácora y, si toca, lo imprime.

        `consola` permite decidir por evento si va a pantalla; por defecto
        sigue a `mostrar_eventos`.
        """
        linea = f"[{self.tiempo:3d} s] {mensaje}"
        self.bitacora.append(linea)
        if self.mostrar_eventos if consola is None else consola:
            print(linea)

    def crear_registro_markov(self, agente):
        """Devuelve el callback que un agente llama en cada sorteo real."""

        def registrar(origen, destino, probabilidad):
            clave = (agente.split()[0], origen, destino)
            self.conteo_markov[clave] = self.conteo_markov.get(clave, 0) + 1
            self.escribir_evento(
                f"[MARKOV] {agente}: {origen} -> {destino} (p={probabilidad})",
                consola=self.mostrar_markov,
            )

        return registrar

    def crear_registro_estrategia(self):
        """Callback que elegir_estrategia() llama en cada decisión del
        cocinero. Vive aparte de crear_registro_markov porque no es una
        transición de Markov (no hay "probabilidad de salida", hay un
        payoff esperado), aunque comparte el mismo espíritu de
        desacoplar el sorteo/decisión de cómo se registra.
        """

        def registrar(condicion, estrategia, payoff):
            clave = (condicion, estrategia)
            self.conteo_estrategias[clave] = self.conteo_estrategias.get(clave, 0) + 1
            self.escribir_evento(
                f"[JUEGO] Cocinero: cola={condicion} -> {estrategia} (payoff={payoff})",
                consola=self.mostrar_markov,
            )

        return registrar

    def sortear_pedido(self):
        """Sortea receta y tiempos de una visita (nueva o de reingreso)."""
        receta, tiempo_base = self.aleatorio.choice(RECETAS)
        tiempo_preparacion = tiempo_base + self.aleatorio.randint(-1, 2)
        tiempo_comida = self.aleatorio.randint(18, 30)
        return receta, tiempo_preparacion, tiempo_comida

    def crear_cliente(self):
        receta, tiempo_preparacion, tiempo_comida = self.sortear_pedido()

        cliente = Cliente(
            self.siguiente_numero,
            self.tiempo,
            receta,
            tiempo_preparacion,
            tiempo_comida,
            rng=self.aleatorio,
        )
        cliente.registro_markov = self.crear_registro_markov(
            f"Cliente {cliente.numero}"
        )
        self.siguiente_numero += 1
        self.clientes.append(cliente)
        self.encolar_cliente(cliente)

    def encolar_cliente(self, cliente, reingreso=False):
        """Mete al cliente en la cola de pedidos o lo pierde si está llena.

        Se comparte entre llegadas nuevas y reingresos para que ambos sigan
        exactamente la misma regla de capacidad.
        """
        origen = "volvió a la fila" if reingreso else "llegó"

        if len(self.cola_pedidos) >= self.capacidad_cola:
            cliente.cambiar_estado("ABANDONO")
            cliente.salida = self.tiempo
            self.escribir_evento(
                f"Cliente {cliente.numero} {origen}, pero la cola estaba llena"
            )
        else:
            self.cola_pedidos.append(cliente)
            self.escribir_evento(
                f"Cliente {cliente.numero} {origen}: {cliente.receta}"
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

            elif evento == "vuelve_a_fila":
                # Se cierra la visita actual (su tiempo en el sistema se
                # registra ahora) y empieza otra con receta y tiempos nuevos.
                # Contar por visita mantiene Lq y Wq coherentes: cada vez que
                # entra a la cola es una llegada más, sin tiempos acumulados.
                self.tiempos_sistema.append(self.tiempo - cliente.llegada)
                receta, preparacion, comida = self.sortear_pedido()
                cliente.nueva_visita(self.tiempo, receta, preparacion, comida)
                self.reingresos += 1
                self.escribir_evento(
                    f"Cliente {cliente.numero} decidió pedir otra vez"
                )
                self.encolar_cliente(cliente, reingreso=True)

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
            self.platos_limpios -= 1

            # El cocinero decide RAPIDO o CUIDADOSO según la presión que
            # queda en la cola (ya sin este cliente): un juego contra el
            # sistema, no un sorteo de Markov. La decisión maximiza el
            # payoff esperado; solo las consecuencias de RAPIDO (el error)
            # son estocásticas.
            condicion = clasificar_cola(len(self.cola_pedidos))
            estrategia = elegir_estrategia(
                PAYOFFS_COCINERO,
                condicion,
                {"RAPIDO": PROB_ERROR_RAPIDO, "CUIDADOSO": 0.0},
                registro=self.registro_juegos,
            )
            if estrategia == "RAPIDO":
                tiempo = max(1, round(cliente.tiempo_preparacion * FACTOR_RAPIDO))
                if ocurre_error(PROB_ERROR_RAPIDO, self.aleatorio):
                    tiempo += PENALIZACION_ERROR
                    self.platos_sucios += 1
                    self.errores_cocina += 1
                    self.escribir_evento(
                        f"Cocina cometió un error con el pedido del cliente "
                        f"{cliente.numero} (RAPIDO)"
                    )
                self.tiempo_cocina = tiempo
            else:
                self.tiempo_cocina = cliente.tiempo_preparacion

            self.escribir_evento(
                f"Cocina comenzó el pedido del cliente {cliente.numero} "
                f"[{estrategia}, cola={condicion}]"
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

        # La barra solo se muestra cuando cambia el estado (incluye entrar y
        # salir de DESCANSANDO). Imprimirla cada segundo llenaba la consola
        # con líneas casi idénticas; el resumen por minuto ya la incluye.
        if self.ayudante.estado != self.ultimo_estado_ayudante:
            self.escribir_evento(
                f"Ayudante [{self.ayudante.estado}] {self.ayudante.barra_energia()}"
            )
            self.ultimo_estado_ayudante = self.ayudante.estado

    def acumular_metricas(self):
        self.area_cola += len(self.cola_pedidos)
        self.area_cola_mesas += len(self.cola_mesas)
        self.area_platos_sucios += self.platos_sucios
        self.area_mesas_ocupadas += self.mesas_ocupadas

    def ejecutar(self):
        if self.mostrar_eventos or self.resumen_markov:
            print("=" * 58)
            print("SIMULACIÓN AUTOMÁTICA DEL RESTAURANTE")
            print("=" * 58)
        if self.resumen_markov:
            self.mostrar_tablas_markov()

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

    def tablas_markov(self):
        """Las dos cadenas tal como están guardadas: dict de listas."""
        return {
            "Cliente": TRANSICIONES_CLIENTE,
            "Ayudante": TRANSICIONES_AYUDANTE,
        }

    def mostrar_tablas_markov(self):
        # Si los agentes se importaron, ya pasaron validar_transiciones();
        # por eso se puede afirmar que están validadas.
        print("AGENTES: Cliente, Ayudante (cocina = servidor FIFO)")
        print("CADENAS DE MARKOV (validadas: cada estado suma 1.0)")
        for agente, tabla in self.tablas_markov().items():
            print(f"  {agente}:")
            for estado, salidas in tabla.items():
                opciones = ", ".join(f"({d}, {p})" for d, p in salidas)
                print(f"    {estado}: [{opciones}]")
        print("=" * 58)

    def frecuencias_markov(self):
        """Teórico vs observado, solo para estados con decisión real.

        Los estados con una única salida no se sortean, así que no tienen
        conteo. La frecuencia observada es veces_destino / veces_origen.
        """
        resultado = {}
        for agente, tabla in self.tablas_markov().items():
            for estado, salidas in tabla.items():
                if len(salidas) < 2:
                    continue
                veces = {
                    d: self.conteo_markov.get((agente, estado, d), 0)
                    for d, _ in salidas
                }
                total = sum(veces.values())
                resultado.setdefault(agente, {})[estado] = [
                    {
                        "destino": destino,
                        "teorica": prob,
                        "veces": veces[destino],
                        "observada": (
                            round(veces[destino] / total, 4) if total else None
                        ),
                    }
                    for destino, prob in salidas
                ]
        return resultado

    def mostrar_frecuencias_markov(self):
        print("-" * 58)
        print("MARKOV: probabilidad teórica vs frecuencia observada")
        for agente, estados in self.frecuencias_markov().items():
            for estado, filas in estados.items():
                for fila in filas:
                    obs = fila["observada"]
                    obs_txt = "sin datos" if obs is None else f"{obs:.2f}"
                    print(
                        f"  {agente} {estado} -> {fila['destino']}: "
                        f"teórica {fila['teorica']:.2f} | observada {obs_txt} "
                        f"({fila['veces']} veces)"
                    )

    def inferencia_hmm_ayudante(self):
        """Corre Viterbi sobre toda la secuencia de observaciones del
        ayudante y la compara contra los estados ocultos reales que la
        simulación generó (los conoce porque ella misma los sorteó).
        Mismo espíritu "teórico/generado vs. observado" que
        frecuencias_markov(), aplicado a inferencia de estados ocultos.
        """
        observaciones = self.ayudante.historial_observaciones
        reales = self.ayudante.historial_estados_ocultos
        if not observaciones:
            return None

        inferida = viterbi(
            observaciones,
            TRANSICION_OCULTA_RENDIMIENTO,
            EMISION_RENDIMIENTO,
            PI_RENDIMIENTO,
        )
        aciertos = sum(1 for r, i in zip(reales, inferida) if r == i)
        return {
            "longitud": len(observaciones),
            "aciertos": aciertos,
            "precision": round(aciertos / len(observaciones), 4),
            "secuencia_real": reales,
            "secuencia_inferida": inferida,
            "observaciones": observaciones,
        }

    def mostrar_inferencia_hmm(self):
        resultado = self.inferencia_hmm_ayudante()
        print("-" * 58)
        print("HMM: inferencia Viterbi del rendimiento oculto del ayudante")
        if resultado is None:
            print("  (el ayudante no completó ninguna etapa con observación)")
            return
        print(f"  Observaciones: {resultado['longitud']}")
        print(
            f"  Aciertos: {resultado['aciertos']}/{resultado['longitud']} "
            f"({resultado['precision'] * 100:.1f}%)"
        )

    def resumen_estrategias_cocina(self):
        """Cuántas veces se eligió cada estrategia por condición de cola,
        y la tasa de error observada sobre los RAPIDO elegidos. Mismo
        espíritu "teórico vs. observado" que frecuencias_markov() e
        inferencia_hmm_ayudante(), aplicado a las decisiones del cocinero.
        """
        por_condicion = {}
        for (condicion, estrategia), veces in self.conteo_estrategias.items():
            por_condicion.setdefault(condicion, {})[estrategia] = veces
        total_rapido = sum(v.get("RAPIDO", 0) for v in por_condicion.values())
        return {
            "decisiones": por_condicion,
            "errores": self.errores_cocina,
            "tasa_error_observada": (
                round(self.errores_cocina / total_rapido, 4) if total_rapido else None
            ),
            "prob_error_teorica": PROB_ERROR_RAPIDO,
        }

    def mostrar_resumen_estrategias_cocina(self):
        print("-" * 58)
        print("JUEGOS: estrategia del cocinero por condición de cola")
        resumen = self.resumen_estrategias_cocina()
        for condicion, estrategias in resumen["decisiones"].items():
            detalle = ", ".join(f"{e}={v}" for e, v in estrategias.items())
            print(f"  {condicion}: {detalle}")
        obs = resumen["tasa_error_observada"]
        obs_txt = "sin datos" if obs is None else f"{obs:.2f}"
        print(
            f"  Errores en RAPIDO: {resumen['errores']} "
            f"(teórica {resumen['prob_error_teorica']:.2f} | observada {obs_txt})"
        )

    def guardar_salida(self):
        """Escribe el detalle en `carpeta_salida` (si se configuró).

        - eventos.txt: bitácora completa, incluidos todos los sorteos.
        - markov.json: tablas (dict de listas) y frecuencias teórico/observado.
        - resultados.json: las métricas finales.
        Así la consola queda corta y no se pierde información.
        """
        if not self.carpeta_salida:
            return
        os.makedirs(self.carpeta_salida, exist_ok=True)

        def ruta(nombre):
            return os.path.join(self.carpeta_salida, nombre)

        with open(ruta("eventos.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(self.bitacora) + "\n")

        markov = {
            "semilla": self.semilla,
            "validado": True,
            "tablas": {
                agente: {e: [[d, p] for d, p in salidas] for e, salidas in t.items()}
                for agente, t in self.tablas_markov().items()
            },
            "frecuencias": self.frecuencias_markov(),
        }
        with open(ruta("markov.json"), "w", encoding="utf-8") as f:
            json.dump(markov, f, ensure_ascii=False, indent=2)

        with open(ruta("resultados.json"), "w", encoding="utf-8") as f:
            json.dump(self.calcular_resultados(), f, ensure_ascii=False, indent=2)

        hmm = {
            "modelo": {
                "A": {
                    e: [[d, p] for d, p in s]
                    for e, s in TRANSICION_OCULTA_RENDIMIENTO.items()
                },
                "B": {
                    e: [[d, p] for d, p in s]
                    for e, s in EMISION_RENDIMIENTO.items()
                },
                "pi": PI_RENDIMIENTO,
            },
            "inferencia": self.inferencia_hmm_ayudante(),
        }
        with open(ruta("hmm.json"), "w", encoding="utf-8") as f:
            json.dump(hmm, f, ensure_ascii=False, indent=2)

        juegos = {
            "payoffs": PAYOFFS_COCINERO,
            "prob_error_rapido": PROB_ERROR_RAPIDO,
            "factor_rapido": FACTOR_RAPIDO,
            "penalizacion_error": PENALIZACION_ERROR,
            "resumen": self.resumen_estrategias_cocina(),
        }
        with open(ruta("juegos.json"), "w", encoding="utf-8") as f:
            json.dump(juegos, f, ensure_ascii=False, indent=2)

        print(f"\nDetalle guardado en: {os.path.abspath(self.carpeta_salida)}")
        print("  eventos.txt, markov.json, hmm.json, juegos.json, resultados.json")

    def promedio(self, datos):
        if not datos:
            return 0
        return sum(datos) / len(datos)

    def calcular_resultados(self):
        llegadas = len(self.clientes)
        completados = len([c for c in self.clientes if c.estado == "FIN"])
        abandonos = len([c for c in self.clientes if c.estado == "ABANDONO"])
        utilizacion_mesas = self.area_mesas_ocupadas / (
            self.total_mesas * self.duracion
        )
        return {
            "duracion": self.duracion,
            "llegadas": llegadas,
            "completados": completados,
            "abandonos": abandonos,
            "en_sistema": llegadas - completados - abandonos,
            "reingresos": self.reingresos,
            "platos_lavados": self.ayudante.platos_lavados,
            "lq": self.area_cola / self.duracion,
            "wq": self.promedio(self.tiempos_espera),
            "cola_mesas": self.area_cola_mesas / self.duracion,
            "tiempo_sistema": self.promedio(self.tiempos_sistema),
            "utilizacion_cocina": self.tiempo_cocina_ocupada / self.duracion,
            "utilizacion_ayudante": self.ayudante.tiempo_ocupado / self.duracion,
            "utilizacion_mesas": utilizacion_mesas,
            "platos_sucios_promedio": self.area_platos_sucios / self.duracion,
            "tasa_salida_por_minuto": completados / self.duracion * 60,
            "probabilidad_abandono": abandonos / llegadas if llegadas else 0,
        }

    def mostrar_resultados(self):
        r = self.calcular_resultados()

        print("\n" + "=" * 58)
        print("RESULTADOS")
        print("=" * 58)
        print(f"Tiempo simulado:                 {r['duracion']} segundos")
        print(f"Clientes que llegaron:           {r['llegadas']}")
        print(f"Clientes que completaron:        {r['completados']}")
        print(f"Clientes que abandonaron:        {r['abandonos']}")
        print(f"Clientes todavía en el sistema:  {r['en_sistema']}")
        print(f"Reingresos a la fila (visitas):  {r['reingresos']}")
        print(f"Platos lavados por el ayudante:  {r['platos_lavados']}")
        print("-" * 58)
        print(f"Lq - longitud promedio cola:     {r['lq']:.2f} clientes")
        print(f"Wq - espera promedio:            {r['wq']:.2f} segundos")
        print(f"Cola promedio para mesas:        {r['cola_mesas']:.2f} clientes")
        print(f"Tiempo promedio en el sistema:   {r['tiempo_sistema']:.2f} segundos")
        print(f"Utilización de la cocina:        {r['utilizacion_cocina'] * 100:.1f}%")
        print(f"Utilización del ayudante:        {r['utilizacion_ayudante'] * 100:.1f}%")
        print(f"Utilización de las mesas:        {r['utilizacion_mesas'] * 100:.1f}%")
        print(f"Promedio de platos sucios:       {r['platos_sucios_promedio']:.2f}")
        print(f"Tasa de salida:                  {r['tasa_salida_por_minuto']:.2f} clientes/minuto")
        print(f"Probabilidad de abandono:        {r['probabilidad_abandono'] * 100:.1f}%")

        if self.resumen_markov:
            self.mostrar_frecuencias_markov()
        if self.resumen_hmm:
            self.mostrar_inferencia_hmm()
        if self.resumen_juegos:
            self.mostrar_resumen_estrategias_cocina()
