import unittest

from agentes import Ayudante, Cliente
from simulacion import SimulacionRestaurante


class PruebasAgentes(unittest.TestCase):
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
        ayudante = Ayudante(capacidad=3)
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
