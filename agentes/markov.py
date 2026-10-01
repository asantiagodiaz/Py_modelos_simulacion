"""Utilidades para modelar los estados de un agente como cadena de Markov.

Una cadena se guarda como diccionario de listas:

    {"ESTADO": [("DESTINO_A", 0.3), ("DESTINO_B", 0.7)], ...}

Se eligió este formato (y no una matriz) porque es legible, solo lista las
transiciones que existen y hace evidente que no se pueden saltar estados.
"""

import math


def validar_transiciones(transiciones, terminales=()):
    """Comprueba que la cadena esté bien formada; lanza ValueError si no.

    - Las probabilidades que salen de un mismo estado deben sumar 1
      (math.isclose evita falsos errores por redondeo de floats).
    - Todo destino debe ser un estado válido: una clave del diccionario o
      un estado terminal (ej. "FIN") que no tiene salidas propias.

    Se llama al importar cada agente, así un error en la tabla falla de
    inmediato en vez de dar una simulación silenciosamente incorrecta.
    """
    validos = set(transiciones) | set(terminales)
    for estado, salidas in transiciones.items():
        if not salidas:
            raise ValueError(f"El estado {estado} no tiene transiciones")
        total = sum(prob for _, prob in salidas)
        if not math.isclose(total, 1.0):
            raise ValueError(
                f"Las probabilidades de {estado} suman {total}, no 1"
            )
        for destino, prob in salidas:
            if prob < 0:
                raise ValueError(f"Probabilidad negativa en {estado}")
            if destino not in validos:
                raise ValueError(
                    f"{estado} apunta a un estado inexistente: {destino}"
                )


def siguiente_estado(transiciones, estado, rng, registro=None):
    """Sortea el estado siguiente a partir de `estado`.

    `registro(origen, destino, probabilidad)` es opcional: si se da, se llama
    en cada sorteo REAL (estados con más de una salida). Así la simulación
    puede contar y mostrar las decisiones sin que este módulo sepa nada de
    archivos ni de consola.

    `rng` es el generador aleatorio de la simulación (self.aleatorio), no el
    módulo `random` global: así la semilla sigue dando corridas idénticas.
    """
    salidas = transiciones[estado]

    # Con una única salida (prob 1.0) no hay nada que sortear. No se consume
    # el generador para no alterar la secuencia aleatoria del resto de la
    # simulación en los pasos puramente lineales.
    if len(salidas) == 1:
        return salidas[0][0]

    # Método de la suma acumulada: se elige el primer destino cuyo
    # acumulado supera al número sorteado en [0, 1).
    sorteo = rng.random()
    acumulado = 0.0
    for destino, probabilidad in salidas:
        acumulado += probabilidad
        if sorteo < acumulado:
            if registro:
                registro(estado, destino, probabilidad)
            return destino

    # Salvaguarda: por redondeo el acumulado puede quedar en 0.9999...
    destino, probabilidad = salidas[-1]
    if registro:
        registro(estado, destino, probabilidad)
    return destino
