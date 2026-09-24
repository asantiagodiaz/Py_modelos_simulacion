"""Punto de entrada de la simulación.

Cambie estas constantes para experimentar con diferentes escenarios.
"""

from simulacion import SimulacionRestaurante


TIEMPO_SIMULACION = 300  # segundos simulados
SEMILLA_ALEATORIA = 7
MOSTRAR_EVENTOS = True


def main():
    simulacion = SimulacionRestaurante(
        duracion=TIEMPO_SIMULACION,
        semilla=SEMILLA_ALEATORIA,
        mostrar_eventos=MOSTRAR_EVENTOS,
    )
    simulacion.ejecutar()
    simulacion.mostrar_resultados()


if __name__ == "__main__":
    main()
