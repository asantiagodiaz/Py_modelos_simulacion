"""Punto de entrada de la simulación.

Cambie estas constantes para experimentar con diferentes escenarios.
"""

import sys

from simulacion import SimulacionRestaurante


TIEMPO_SIMULACION = 300  # segundos simulados
SEMILLA_ALEATORIA = 7
MOSTRAR_EVENTOS = False  # eventos segundo a segundo en consola
MOSTRAR_SORTEOS_MARKOV = False  # cada sorteo de Markov en consola
MOSTRAR_RESUMEN_HMM = True  # inferencia Viterbi del ayudante al final
MOSTRAR_RESUMEN_JUEGOS = True  # estrategia del cocinero y tasa de error
CARPETA_SALIDA = "salida"  # el detalle completo se guarda aquí (None = no)


def main():
    # La consola de Windows usa cp1252 por defecto y falla al imprimir la
    # barra de energía (█, ░) y las tildes; se fuerza UTF-8 en la salida.
    sys.stdout.reconfigure(encoding="utf-8")

    simulacion = SimulacionRestaurante(
        duracion=TIEMPO_SIMULACION,
        semilla=SEMILLA_ALEATORIA,
        mostrar_eventos=MOSTRAR_EVENTOS,
        mostrar_markov=MOSTRAR_SORTEOS_MARKOV,
        resumen_markov=True,
        resumen_hmm=MOSTRAR_RESUMEN_HMM,
        resumen_juegos=MOSTRAR_RESUMEN_JUEGOS,
        carpeta_salida=CARPETA_SALIDA,
    )
    simulacion.ejecutar()
    simulacion.mostrar_resultados()
    simulacion.guardar_salida()


if __name__ == "__main__":
    main()
