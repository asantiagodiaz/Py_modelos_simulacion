"""Motor genérico de Modelo Oculto de Markov (HMM).

Reutiliza el formato y las funciones de `markov.py`: tanto la matriz de
transición oculta A como la matriz de emisión B se guardan como dict de
listas, igual que las cadenas observables. Así `validar_transiciones` y
`siguiente_estado` sirven tal cual para A y B, sin duplicar lógica: avanzar
el estado oculto o emitir una observación es, en ambos casos, el mismo
sorteo por suma acumulada.
"""

import math

from .markov import siguiente_estado


def validar_pi(pi, estados_A):
    """Comprueba que `pi` (dict estado->probabilidad) sea una distribución
    válida sobre exactamente los estados de A.

    A diferencia de una tabla de transiciones, `pi` no es un dict de listas
    sino una única fila (no hay "estado de origen": es el punto de partida).
    """
    if not math.isclose(sum(pi.values()), 1.0):
        raise ValueError(f"pi suma {sum(pi.values())}, no 1")
    if set(pi) != set(estados_A):
        raise ValueError("pi debe cubrir exactamente los estados de A")
    for estado, prob in pi.items():
        if prob < 0:
            raise ValueError(f"Probabilidad negativa en pi para {estado}")


def estado_inicial(pi, rng):
    """Sortea el estado oculto inicial según `pi`.

    Mismo método de suma acumulada que `siguiente_estado`, pero sobre una
    distribución (pi.items()) en vez de una tabla de transiciones. No
    consume `rng` si `pi` tiene un único estado (prob 1.0).
    """
    salidas = list(pi.items())
    if len(salidas) == 1:
        return salidas[0][0]

    sorteo = rng.random()
    acumulado = 0.0
    for estado, probabilidad in salidas:
        acumulado += probabilidad
        if sorteo < acumulado:
            return estado

    return salidas[-1][0]


def siguiente_estado_oculto(A, estado_oculto, rng, registro=None):
    """Avanza la cadena oculta. Alias semántico de `siguiente_estado(A, ...)`:
    mantiene la frontera de módulos clara, todo lo oculto entra y sale por
    `hmm.py` en vez de que los agentes importen `markov.py` directamente
    para su parte oculta.
    """
    return siguiente_estado(A, estado_oculto, rng, registro)


def emitir_observacion(B, estado_oculto, rng, registro=None):
    """Sortea la observación emitida por `estado_oculto` según B. Alias
    semántico de `siguiente_estado(B, ...)`: "emitir" es formalmente el
    mismo sorteo por suma acumulada, solo que el destino es una categoría
    de observación en vez de otro estado.
    """
    return siguiente_estado(B, estado_oculto, rng, registro)


def _probabilidad(salidas, destino):
    """Busca `destino` en una lista de tuplas (destino, prob) de A o B;
    devuelve 0.0 si no está. Evita que Viterbi explote con KeyError ante
    matrices dispersas, que es justamente el formato elegido para A y B.
    """
    for d, p in salidas:
        if d == destino:
            return p
    return 0.0


def _log(p):
    """log(p) manejando p == 0 como -inf en vez de dejar que math.log
    lance ValueError: una emisión o transición imposible debe descartar
    ese camino, no tumbar el algoritmo.
    """
    return math.log(p) if p > 0 else float("-inf")


def viterbi(observaciones, A, B, pi):
    """Devuelve la secuencia de estados ocultos más probable (list[str],
    misma longitud que `observaciones`) dado el modelo (A, B, pi).

    Trabaja en espacio logarítmico (sumas en vez de productos) porque la
    simulación genera secuencias largas y el producto directo de
    probabilidades subflotaría a 0.0 mucho antes de terminar.

    - delta[estado] = log-probabilidad del mejor camino que termina en ese
      estado y explica observaciones[:t+1].
    - psi[t][estado] = predecesor que logró ese máximo, para reconstruir
      la secuencia completa por backtracking.
    """
    estados = list(A.keys())

    delta = {
        s: _log(pi[s]) + _log(_probabilidad(B[s], observaciones[0]))
        for s in estados
    }
    psi = [{}]

    for observacion in observaciones[1:]:
        nuevo_delta = {}
        paso_psi = {}
        for destino in estados:
            mejor_origen, mejor_valor = None, float("-inf")
            for origen in estados:
                valor = delta[origen] + _log(_probabilidad(A[origen], destino))
                if valor > mejor_valor:
                    mejor_valor, mejor_origen = valor, origen
            nuevo_delta[destino] = mejor_valor + _log(
                _probabilidad(B[destino], observacion)
            )
            paso_psi[destino] = mejor_origen
        delta = nuevo_delta
        psi.append(paso_psi)

    estado_final = max(estados, key=lambda s: delta[s])

    secuencia = [estado_final]
    for paso_psi in reversed(psi[1:]):
        secuencia.append(paso_psi[secuencia[-1]])
    secuencia.reverse()

    return secuencia
