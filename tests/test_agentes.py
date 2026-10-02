import random
import unittest

from agentes import Ayudante, Cliente
from agentes.ayudante import (
    TRANSICIONES_AYUDANTE,
    TRANSICION_OCULTA_RENDIMIENTO,
    EMISION_RENDIMIENTO,
    FACTOR_DURACION_POR_OBSERVACION,
    DURACIONES_AYUDANTE,
)
from agentes.cliente import TRANSICIONES_CLIENTE
from agentes.markov import siguiente_estado, validar_transiciones
from agentes.hmm import (
    validar_pi,
    estado_inicial,
    emitir_observacion,
    viterbi,
)
from agentes.juegos import (
    PAYOFFS_COCINERO,
    validar_payoffs,
    clasificar_cola,
    elegir_estrategia,
    ocurre_error,
)
from simulacion import SimulacionRestaurante


class RngFijo:
    """Generador falso: random() siempre devuelve `valor`.

    Con 0.0 se elige siempre la primera opción de cada estado (avanzar en
    el ciclo), lo que hace determinista una prueba que de otro modo dependería
    del azar.
    """

    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor


class RngProhibido:
    """Falla si se le pide un número: prueba que no se sortea sin necesidad."""

    def random(self):
        raise AssertionError("No debía sortearse con probabilidad 1.0")


# Saltos permitidos, escritos a mano e independientes de las tablas, para que
# la prueba detecte si alguien introduce un salto prohibido en ellas.
PERMITIDAS_AYUDANTE = {
    "DESOCUPADO": {"BUSCANDO_PLATOS"},
    "BUSCANDO_PLATOS": {"RECOGIENDO_PLATOS"},
    "RECOGIENDO_PLATOS": {"LLEVANDO_AL_LAVAPLATOS"},
    "LLEVANDO_AL_LAVAPLATOS": {"LAVANDO"},
    "LAVANDO": {"LAVANDO", "SECANDO"},
    "SECANDO": {"SECANDO", "GUARDANDO"},
    "GUARDANDO": {"DESOCUPADO", "BUSCANDO_PLATOS"},
}
PERMITIDAS_CLIENTE = {
    "ESPERANDO_PEDIDO": {"ESPERANDO_COMIDA"},
    "ESPERANDO_COMIDA": {"BUSCANDO_MESA"},
    "BUSCANDO_MESA": {"COMIENDO"},
    "ESPERANDO_MESA": {"COMIENDO"},
    "COMIENDO": {"SALIENDO"},
    "SALIENDO": {"HACER_FILA", "FIN"},
    "HACER_FILA": {"ESPERANDO_PEDIDO"},
}


class PruebasMarkov(unittest.TestCase):
    def test_probabilidades_suman_uno(self):
        for tabla in (TRANSICIONES_AYUDANTE, TRANSICIONES_CLIENTE):
            for estado, salidas in tabla.items():
                self.assertAlmostEqual(
                    sum(p for _, p in salidas), 1.0, msg=f"estado {estado}"
                )

    def test_no_hay_saltos_prohibidos(self):
        for tabla, permitidas in (
            (TRANSICIONES_AYUDANTE, PERMITIDAS_AYUDANTE),
            (TRANSICIONES_CLIENTE, PERMITIDAS_CLIENTE),
        ):
            self.assertEqual(set(tabla), set(permitidas))
            for estado, salidas in tabla.items():
                destinos = {d for d, _ in salidas}
                self.assertTrue(
                    destinos <= permitidas[estado], msg=f"estado {estado}"
                )

    def test_validar_rechaza_tablas_mal_formadas(self):
        with self.assertRaises(ValueError):
            validar_transiciones({"A": [("A", 0.5), ("B", 0.4)], "B": [("A", 1.0)]})
        with self.assertRaises(ValueError):
            validar_transiciones({"A": [("Z", 1.0)]})

    def test_probabilidad_uno_es_determinista_y_no_sortea(self):
        tabla = {"A": [("B", 1.0)], "B": [("A", 1.0)]}
        self.assertEqual(siguiente_estado(tabla, "A", RngProhibido()), "B")

    def test_frecuencias_con_semilla_fija(self):
        rng = random.Random(7)
        n = 20000
        vueltas = sum(
            siguiente_estado(TRANSICIONES_CLIENTE, "SALIENDO", rng) == "HACER_FILA"
            for _ in range(n)
        )
        self.assertAlmostEqual(vueltas / n, 0.3, delta=0.02)

        repeticiones = sum(
            siguiente_estado(TRANSICIONES_AYUDANTE, "LAVANDO", rng) == "LAVANDO"
            for _ in range(n)
        )
        self.assertAlmostEqual(repeticiones / n, 0.1, delta=0.02)

    def test_misma_semilla_misma_secuencia(self):
        def secuencia():
            rng = random.Random(7)
            return [
                siguiente_estado(TRANSICIONES_CLIENTE, "SALIENDO", rng)
                for _ in range(50)
            ]

        self.assertEqual(secuencia(), secuencia())


class PruebasAgentes(unittest.TestCase):
    def test_cliente_vuelve_a_la_fila(self):
        # random() = 0.0 elige la primera opción de SALIENDO: HACER_FILA.
        cliente = Cliente(1, 0, "Ensalada", 5, 1, rng=RngFijo(0.0))
        cliente.cambiar_estado("SALIENDO")
        self.assertEqual(cliente.actualizar(), "vuelve_a_fila")
        cliente.nueva_visita(50, "Sándwich", 8, 20)
        self.assertEqual(cliente.estado, "ESPERANDO_PEDIDO")
        self.assertEqual(cliente.llegada, 50)
        self.assertEqual(cliente.paciencia_pedido, 45)
        self.assertEqual(cliente.visitas, 2)

    def test_cliente_sale_del_restaurante(self):
        # random() = 0.99 cae en la segunda opción de SALIENDO: FIN.
        cliente = Cliente(1, 0, "Ensalada", 5, 1, rng=RngFijo(0.99))
        cliente.cambiar_estado("SALIENDO")
        self.assertEqual(cliente.actualizar(), "sale")
        self.assertEqual(cliente.estado, "FIN")

    def test_ayudante_repite_lavado(self):
        # random() = 0.99 en LAVANDO cae en la segunda opción: repetir.
        # El mismo rng también cae en la última opción del HMM oculto
        # (FATIGADO, observación LENTA), que escala la duración base x1.5.
        ayudante = Ayudante(capacidad=3, rng=RngFijo(0.99))
        ayudante.carga = 1
        ayudante.cambiar_estado("LAVANDO", 1)
        energia = ayudante.energia
        ayudante.actualizar(0)
        self.assertEqual(ayudante.estado, "LAVANDO")
        duracion_base = DURACIONES_AYUDANTE["LAVANDO"](ayudante.carga)
        esperado = max(
            1, round(duracion_base * FACTOR_DURACION_POR_OBSERVACION["LENTA"])
        )
        self.assertEqual(ayudante.tiempo_restante, esperado)
        self.assertEqual(
            ayudante.energia, energia - Ayudante.COSTOS_ENERGIA["LAVANDO"]
        )

    def test_cliente_abandona_por_falta_de_paciencia(self):
        cliente = Cliente(1, 0, "Ensalada", 5, 20)
        cliente.paciencia_pedido = 1
        evento = cliente.actualizar()
        self.assertEqual(evento, "abandona_pedido")
        self.assertEqual(cliente.estado, "ABANDONO")

    def test_cliente_termina_de_comer(self):
        cliente = Cliente(1, 0, "Ensalada", 5, 1)
        cliente.cambiar_estado("COMIENDO")
        evento = cliente.actualizar()
        self.assertEqual(evento, "termina_comida")
        self.assertEqual(cliente.estado, "SALIENDO")

    def test_ayudante_lava_un_plato(self):
        # RngFijo(0.0) evita repeticiones y ciclos extra: el ciclo es lineal.
        ayudante = Ayudante(capacidad=3, rng=RngFijo(0.0))
        sucios = 1
        limpios = 0
        for _ in range(20):
            recogidos, guardados, _ = ayudante.actualizar(sucios)
            sucios -= recogidos
            limpios += guardados
        self.assertEqual(sucios, 0)
        self.assertEqual(limpios, 1)
        self.assertEqual(ayudante.platos_lavados, 1)

    def test_simulacion_genera_metricas_validas(self):
        simulacion = SimulacionRestaurante(
            duracion=120,
            semilla=7,
            mostrar_eventos=False,
        )
        simulacion.ejecutar()
        self.assertGreater(len(simulacion.clientes), 0)
        self.assertGreaterEqual(simulacion.area_cola, 0)
        self.assertLessEqual(simulacion.tiempo_cocina_ocupada, 120)
        self.assertLessEqual(simulacion.ayudante.tiempo_ocupado, 120)


class PruebasHmm(unittest.TestCase):
    def test_validar_pi_rechaza_suma_distinta_de_uno(self):
        with self.assertRaises(ValueError):
            validar_pi({"A": 0.5, "B": 0.4}, {"A": [], "B": []})

    def test_validar_pi_rechaza_estados_faltantes_o_extra(self):
        with self.assertRaises(ValueError):
            validar_pi({"A": 0.5, "C": 0.5}, {"A": [], "B": []})
        with self.assertRaises(ValueError):
            validar_pi({"A": 1.0}, {"A": [], "B": []})

    def test_estado_inicial_es_determinista_con_rng_fijo(self):
        pi = {"A": 0.3, "B": 0.7}
        self.assertEqual(estado_inicial(pi, RngFijo(0.0)), "A")
        self.assertEqual(estado_inicial(pi, RngFijo(0.99)), "B")

    def test_estado_inicial_no_sortea_si_pi_tiene_un_solo_estado(self):
        self.assertEqual(estado_inicial({"A": 1.0}, RngProhibido()), "A")

    def test_emitir_observacion_usa_el_mismo_metodo_que_siguiente_estado(self):
        B = {"A": [("RAPIDA", 0.5), ("LENTA", 0.5)]}
        self.assertEqual(emitir_observacion(B, "A", RngFijo(0.0)), "RAPIDA")
        self.assertEqual(emitir_observacion(B, "A", RngFijo(0.99)), "LENTA")

    def test_viterbi_secuencia_trivial_un_solo_estado_posible(self):
        A = {"UNICO": [("UNICO", 1.0)]}
        B = {"UNICO": [("X", 0.5), ("Y", 0.5)]}
        pi = {"UNICO": 1.0}
        observaciones = ["X", "Y", "X", "X"]
        resultado = viterbi(observaciones, A, B, pi)
        self.assertEqual(resultado, ["UNICO"] * len(observaciones))

    def test_viterbi_recupera_secuencia_oculta_obvia(self):
        A = {
            "RAPIDO": [("RAPIDO", 0.9), ("LENTO", 0.1)],
            "LENTO": [("RAPIDO", 0.1), ("LENTO", 0.9)],
        }
        B = {
            "RAPIDO": [("RAPIDA", 0.99), ("LENTA", 0.01)],
            "LENTO": [("RAPIDA", 0.01), ("LENTA", 0.99)],
        }
        pi = {"RAPIDO": 0.5, "LENTO": 0.5}
        observaciones = ["RAPIDA", "RAPIDA", "LENTA", "LENTA", "LENTA"]
        esperado = ["RAPIDO", "RAPIDO", "LENTO", "LENTO", "LENTO"]
        self.assertEqual(viterbi(observaciones, A, B, pi), esperado)

    def test_viterbi_maneja_emision_probabilidad_cero(self):
        A = {"A": [("A", 0.5), ("B", 0.5)], "B": [("A", 0.5), ("B", 0.5)]}
        B = {"A": [("X", 1.0)], "B": [("Y", 1.0)]}
        pi = {"A": 0.5, "B": 0.5}
        # "Y" nunca la emite "A" y "X" nunca la emite "B": ambas listas
        # tienen huecos, _probabilidad debe devolver 0.0 sin lanzar.
        resultado = viterbi(["X", "Y", "X"], A, B, pi)
        self.assertEqual(len(resultado), 3)

    def test_viterbi_longitud_de_salida_coincide_con_observaciones(self):
        A = {"A": [("A", 0.6), ("B", 0.4)], "B": [("A", 0.4), ("B", 0.6)]}
        B = {"A": [("X", 0.7), ("Y", 0.3)], "B": [("X", 0.3), ("Y", 0.7)]}
        pi = {"A": 0.5, "B": 0.5}
        observaciones = ["X", "Y", "X", "X", "Y", "Y", "X"]
        self.assertEqual(len(viterbi(observaciones, A, B, pi)), len(observaciones))


class PruebasAyudanteHmm(unittest.TestCase):
    def test_ayudante_inicia_con_estado_oculto_valido(self):
        ayudante = Ayudante(rng=RngFijo(0.0))
        self.assertIn(ayudante.estado_oculto, TRANSICION_OCULTA_RENDIMIENTO)

    def test_avanzar_rendimiento_oculto_actualiza_historiales(self):
        # RngFijo(0.0) elige siempre la primera opción: transición oculta
        # RENDIMIENTO_ALTO->RENDIMIENTO_ALTO, emisión ->RAPIDA.
        ayudante = Ayudante(rng=RngFijo(0.0))
        ayudante.estado_oculto = "RENDIMIENTO_ALTO"
        observacion = ayudante.avanzar_rendimiento_oculto()
        self.assertEqual(ayudante.estado_oculto, "RENDIMIENTO_ALTO")
        self.assertEqual(observacion, "RAPIDA")
        self.assertEqual(ayudante.historial_estados_ocultos, ["RENDIMIENTO_ALTO"])
        self.assertEqual(ayudante.historial_observaciones, ["RAPIDA"])

    def test_duracion_se_modula_por_observacion(self):
        # random()=0.99 cae siempre en la última opción de cada tabla:
        # transición visible LAVANDO->LAVANDO (repetir) no aplica aquí,
        # se usa un ciclo lineal: RECOGIENDO_PLATOS tiene única salida
        # (prob 1.0, no sortea) y la cadena oculta cae en FATIGADO->FATIGADO,
        # con emisión FATIGADO->LENTA (última opción, prob 0.7).
        ayudante = Ayudante(capacidad=3, rng=RngFijo(0.99))
        ayudante.estado_oculto = "FATIGADO"
        ayudante.carga = 1
        ayudante.cambiar_estado("LLEVANDO_AL_LAVAPLATOS", 1)
        ayudante.actualizar(5)
        self.assertEqual(ayudante.estado, "LAVANDO")
        duracion_base = DURACIONES_AYUDANTE["LAVANDO"](ayudante.carga)
        esperado = max(
            1, round(duracion_base * FACTOR_DURACION_POR_OBSERVACION["LENTA"])
        )
        self.assertEqual(ayudante.tiempo_restante, esperado)
        self.assertNotEqual(esperado, duracion_base)

    def test_desocupado_no_genera_observacion(self):
        # RECOGIENDO_PLATOS con platos_sucios=0 fuerza la rama sin_platos,
        # que vuelve a DESOCUPADO sin pasar por el HMM.
        ayudante = Ayudante(capacidad=3, rng=RngFijo(0.0))
        ayudante.cambiar_estado("RECOGIENDO_PLATOS", 1)
        ayudante.actualizar(0)
        self.assertEqual(ayudante.estado, "DESOCUPADO")
        self.assertEqual(ayudante.historial_observaciones, [])


class PruebasSimulacionHmm(unittest.TestCase):
    def test_simulacion_completa_permite_inferencia_hmm(self):
        simulacion = SimulacionRestaurante(
            duracion=300,
            semilla=7,
            mostrar_eventos=False,
        )
        simulacion.ejecutar()
        resultado = simulacion.inferencia_hmm_ayudante()
        self.assertIsNotNone(resultado)
        self.assertGreaterEqual(resultado["precision"], 0.0)
        self.assertLessEqual(resultado["precision"], 1.0)
        self.assertEqual(
            len(resultado["secuencia_real"]), len(resultado["secuencia_inferida"])
        )
        self.assertEqual(
            len(resultado["secuencia_real"]), len(resultado["observaciones"])
        )


class PruebasJuegos(unittest.TestCase):
    def test_validar_payoffs_rechaza_tabla_incompleta(self):
        with self.assertRaises(ValueError):
            validar_payoffs(
                {"RAPIDO": {"CORTA": {"exito": 1, "error": 0}}},
                ("RAPIDO", "CUIDADOSO"),
            )

    def test_clasificar_cola_fronteras(self):
        self.assertEqual(clasificar_cola(2), "CORTA")
        self.assertEqual(clasificar_cola(3), "MEDIA")
        self.assertEqual(clasificar_cola(4), "MEDIA")
        self.assertEqual(clasificar_cola(5), "LARGA")

    def test_elegir_estrategia_prefiere_cuidadoso_en_cola_corta(self):
        # La elección es maximización determinista, nunca sortea.
        estrategia = elegir_estrategia(
            PAYOFFS_COCINERO,
            "CORTA",
            {"RAPIDO": 0.15, "CUIDADOSO": 0.0},
            rng=RngProhibido(),
        )
        self.assertEqual(estrategia, "CUIDADOSO")

    def test_elegir_estrategia_prefiere_rapido_en_cola_larga(self):
        estrategia = elegir_estrategia(
            PAYOFFS_COCINERO,
            "LARGA",
            {"RAPIDO": 0.15, "CUIDADOSO": 0.0},
            rng=RngProhibido(),
        )
        self.assertEqual(estrategia, "RAPIDO")

    def test_elegir_estrategia_registra_la_decision(self):
        llamadas = []

        def registro(condicion, estrategia, payoff):
            llamadas.append((condicion, estrategia, payoff))

        elegir_estrategia(
            PAYOFFS_COCINERO,
            "LARGA",
            {"RAPIDO": 0.15, "CUIDADOSO": 0.0},
            registro=registro,
        )
        self.assertEqual(len(llamadas), 1)
        condicion, estrategia, payoff = llamadas[0]
        self.assertEqual(condicion, "LARGA")
        self.assertEqual(estrategia, "RAPIDO")
        self.assertIsInstance(payoff, float)

    def test_ocurre_error_es_determinista_con_rng_fijo(self):
        self.assertTrue(ocurre_error(0.15, RngFijo(0.0)))
        self.assertFalse(ocurre_error(0.15, RngFijo(0.99)))

    def test_ocurre_error_no_sortea_si_prob_es_cero(self):
        self.assertFalse(ocurre_error(0.0, RngProhibido()))


class PruebasSimulacionJuegos(unittest.TestCase):
    def test_cocina_usa_rapido_cuando_la_cola_esta_larga(self):
        simulacion = SimulacionRestaurante(
            duracion=300,
            semilla=7,
            mostrar_eventos=False,
        )
        simulacion.ejecutar()
        elecciones_en_larga = [
            estrategia
            for (condicion, estrategia) in simulacion.conteo_estrategias
            if condicion == "LARGA"
        ]
        self.assertIn("RAPIDO", elecciones_en_larga)

    def test_error_en_rapido_aumenta_platos_sucios_y_tiempo_cocina(self):
        simulacion = SimulacionRestaurante(
            duracion=1,
            semilla=7,
            mostrar_eventos=False,
        )
        # RngFijo(0.0) hace que elegir_estrategia (determinista, no sortea)
        # elija según los payoffs reales, y que ocurre_error (prob 0.15,
        # random()=0.0 < 0.15) siempre marque error en RAPIDO. Se llenan 6
        # pedidos en cola a mano para forzar la condición LARGA sin esperar
        # a que la simulación la alcance sola.
        simulacion.aleatorio = RngFijo(0.0)

        for numero in range(1, 7):
            cliente = Cliente(numero, 0, "Ensalada", 5, 20, rng=simulacion.aleatorio)
            cliente.registro_markov = simulacion.crear_registro_markov(
                f"Cliente {numero}"
            )
            simulacion.cola_pedidos.append(cliente)

        platos_sucios_antes = simulacion.platos_sucios
        simulacion.actualizar_cocina()

        self.assertEqual(simulacion.platos_sucios, platos_sucios_antes + 1)
        self.assertGreater(simulacion.errores_cocina, 0)

    def test_resumen_estrategias_cocina_cuenta_correctamente(self):
        simulacion = SimulacionRestaurante(
            duracion=300,
            semilla=7,
            mostrar_eventos=False,
        )
        simulacion.ejecutar()
        resumen = simulacion.resumen_estrategias_cocina()
        total_resumen = sum(
            veces
            for estrategias in resumen["decisiones"].values()
            for veces in estrategias.values()
        )
        total_conteo = sum(simulacion.conteo_estrategias.values())
        self.assertEqual(total_resumen, total_conteo)
        self.assertGreater(total_resumen, 0)


if __name__ == "__main__":
    unittest.main()
