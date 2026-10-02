"""Teoría de juegos simple: el cocinero decide una estrategia observando
el estado del sistema (tamaño de la cola), no contra un segundo jugador
activo. Es una tabla de decisión bajo incertidumbre ("juego contra la
naturaleza"): para cada condición del sistema hay un payoff esperado por
estrategia, y se elige la que lo maximiza.
"""


# Payoffs (beneficio neto, unidades arbitrarias) de cada estrategia según
# la presión de la cola. CORTA: apurarse no aporta y el riesgo no vale la
# pena -> conviene CUIDADOSO. LARGA: ganar tiempo evita abandonos por cola
# llena, el riesgo vale la pena -> conviene RAPIDO. MEDIA es un cruce
# estrecho a propósito, para que la decisión sea sensible al contexto y no
# un umbral binario brusco.
PAYOFFS_COCINERO = {
    "RAPIDO": {
        "CORTA": {"exito": 3, "error": -4},
        "MEDIA": {"exito": 6, "error": -2},
        "LARGA": {"exito": 10, "error": 1},
    },
    "CUIDADOSO": {
        "CORTA": {"exito": 6, "error": 6},
        "MEDIA": {"exito": 5, "error": 5},
        "LARGA": {"exito": 2, "error": 2},
    },
}

PROB_ERROR_RAPIDO = 0.15  # probabilidad de plato mal hecho al elegir RAPIDO
FACTOR_RAPIDO = 0.6  # reduce tiempo_preparacion cuando se elige RAPIDO
PENALIZACION_ERROR = 4  # segundos extra de reproceso si RAPIDO falla


def validar_payoffs(payoffs, estrategias):
    """Comprueba que cada estrategia tenga payoff ("exito" y "error") para
    cada condición, y que todas las estrategias estén presentes. Falla
    rápido si la tabla queda mal formada al importar el módulo.
    """
    if set(payoffs) != set(estrategias):
        raise ValueError("La tabla de payoffs no cubre exactamente las estrategias dadas")
    condiciones = {c for tabla in payoffs.values() for c in tabla}
    for estrategia, tabla in payoffs.items():
        if set(tabla) != condiciones:
            raise ValueError(
                f"La estrategia {estrategia} no cubre todas las condiciones"
            )
        for condicion, valores in tabla.items():
            if set(valores) != {"exito", "error"}:
                raise ValueError(
                    f"{estrategia}/{condicion} debe tener 'exito' y 'error'"
                )


validar_payoffs(PAYOFFS_COCINERO, ("RAPIDO", "CUIDADOSO"))


def clasificar_cola(longitud_cola, corta_hasta=2, media_hasta=4):
    """Discretiza len(cola_pedidos) en CORTA / MEDIA / LARGA.

    Los cortes son arbitrarios pero coherentes con capacidad_cola=7 del
    restaurante: CORTA es "sin presión", LARGA es "cerca de llenarse y
    perder clientes", MEDIA es la zona intermedia.
    """
    if longitud_cola <= corta_hasta:
        return "CORTA"
    if longitud_cola <= media_hasta:
        return "MEDIA"
    return "LARGA"


def payoff_esperado(payoffs, estrategia, condicion, prob_error):
    """E[payoff] = (1 - prob_error) * exito + prob_error * error.

    Con prob_error=0 (estrategia sin riesgo, como CUIDADOSO) esto colapsa
    al valor de "exito".
    """
    valores = payoffs[estrategia][condicion]
    return (1 - prob_error) * valores["exito"] + prob_error * valores["error"]


def elegir_estrategia(payoffs, condicion, prob_error_por_estrategia, rng=None, registro=None):
    """Elige la estrategia con mayor payoff esperado dado `condicion`.

    No es un sorteo (a diferencia de siguiente_estado): es maximización
    determinista de valor esperado, el cocinero no tira dados para decidir
    su estrategia, solo las consecuencias de RAPIDO tienen azar después
    (ver ocurre_error). `rng` solo se usa para desempatar si dos
    estrategias quedan exactamente iguales, evitando un sesgo silencioso
    hacia la primera en orden de iteración.

    `registro(condicion, estrategia, payoff)` sigue el mismo patrón que
    crear_registro_markov: permite loggear sin acoplar este módulo a
    bitácora ni consola.
    """
    mejores = []
    mejor_valor = float("-inf")
    for estrategia, prob_error in prob_error_por_estrategia.items():
        valor = payoff_esperado(payoffs, estrategia, condicion, prob_error)
        if valor > mejor_valor:
            mejor_valor = valor
            mejores = [estrategia]
        elif valor == mejor_valor:
            mejores.append(estrategia)

    if len(mejores) == 1 or rng is None:
        elegida = mejores[0]
    else:
        elegida = mejores[rng.randrange(len(mejores))]

    if registro:
        registro(condicion, elegida, mejor_valor)
    return elegida


def ocurre_error(prob_error, rng):
    """Sortea si la estrategia arriesgada produce un plato mal hecho.

    Función separada de elegir_estrategia porque es el único sorteo real
    del módulo: debe poder probarse con RngFijo/RngProhibido igual que
    siguiente_estado. No consume rng si prob_error<=0 (estrategias sin
    riesgo, como CUIDADOSO), igual que el resto del proyecto evita
    sorteos innecesarios en casos deterministas.
    """
    if prob_error <= 0:
        return False
    return rng.random() < prob_error
