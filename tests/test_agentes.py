import random
import unittest

from agentes import Ayudante, Cliente
from agentes.ayudante import TRANSICIONES_AYUDANTE
from agentes.cliente import TRANSICIONES_CLIENTE
from agentes.markov import siguiente_estado, validar_transiciones
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
        ayudante = Ayudante(capacidad=3, rng=RngFijo(0.99))
        ayudante.carga = 1
        ayudante.cambiar_estado("LAVANDO", 1)
        energia = ayudante.energia
        ayudante.actualizar(0)
        self.assertEqual(ayudante.estado, "LAVANDO")
        self.assertEqual(ayudante.tiempo_restante, 3)  # duración completa
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


if __name__ == "__main__":
    unittest.main()
