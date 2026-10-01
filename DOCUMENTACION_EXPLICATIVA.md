# Documentación explicativa

Guía sencilla de cómo funciona el proyecto, qué muestra la consola y cómo se
generan los archivos de la carpeta `salida/`.

## 1. ¿Qué es el proyecto?

Es la simulación de un restaurante pequeño que se ejecuta por consola. No hay
interfaz gráfica ni hay que interactuar: el programa avanza solo, **un paso =
un segundo simulado**, durante 300 segundos (5 minutos) por defecto.

En el restaurante hay dos tipos de **agentes** (personajes con estados que
cambian con el tiempo):

- **Cliente:** llega, pide, espera, come y se va (o vuelve a pedir).
- **Ayudante:** recoge los platos sucios, los lava, los seca y los guarda.

Y hay recursos limitados: una cocina que atiende un pedido a la vez, 3 mesas y
una cantidad de platos limpios.

El cambio de estado de los agentes se modela con **cadenas de Markov**: desde
cada estado, el agente pasa al siguiente con cierta probabilidad.

## 2. Estructura de archivos

| Archivo | Para qué sirve |
|---|---|
| `main.py` | Punto de entrada. Aquí se cambia la duración, la semilla y qué se imprime. |
| `simulacion/restaurante.py` | El "director": corre el reloj, maneja cola, cocina, mesas, métricas y archivos de salida. |
| `agentes/cliente.py` | El agente Cliente y su cadena de Markov. |
| `agentes/ayudante.py` | El agente Ayudante, su cadena de Markov y su sistema de energía. |
| `agentes/markov.py` | Funciones comunes: validar una cadena y sortear el siguiente estado. |
| `tests/test_agentes.py` | Pruebas automáticas. |
| `diagramas_agentes.drawio` | Diagramas de proceso de ambos agentes. |
| `salida/` | Archivos generados en cada ejecución (no se sube a git). |

## 3. ¿Cómo funciona una ejecución?

`main.py` crea una `SimulacionRestaurante` y la ejecuta. En cada segundo, la
simulación hace estos pasos en orden:

1. **Llegadas:** cuenta regresiva para el próximo cliente. Los intervalos entre
   llegadas son aleatorios (distribución exponencial, promedio de un cliente
   cada 10 s). Si la cola de pedidos está llena (7), el cliente se va.
2. **Métricas:** anota cuántos hay en cola, mesas ocupadas y platos sucios.
3. **Clientes:** cada cliente avanza un segundo (paciencia, comida, salida).
4. **Mesas:** asigna las mesas que se liberaron a quienes esperaban.
5. **Cocina:** termina el pedido en curso o toma el siguiente de la cola.
6. **Ayudante:** avanza un segundo en su ciclo de trabajo.

Al final del tiempo se calculan los resultados y se guardan los archivos.

### Reproducibilidad (la semilla)

Todo el azar sale de **un solo generador** con semilla (`SEMILLA_ALEATORIA = 7`).
Con la misma semilla y la misma duración, la simulación da **siempre lo mismo**.
Si cambias la semilla, cambian las llegadas, las recetas y las decisiones de
las cadenas de Markov.

## 4. Los agentes

### Cliente

Recorrido normal:

`ESPERANDO_PEDIDO → ESPERANDO_COMIDA → BUSCANDO_MESA → COMIENDO → SALIENDO → FIN`

- Si no hay mesa libre espera en `ESPERANDO_MESA`.
- **Abandona** si se le agota la paciencia: 45 s esperando el pedido o 35 s
  esperando mesa. Esto se decide por tiempo, no por probabilidad.
- Al terminar de comer deja un plato sucio (le da trabajo al ayudante).
- En `SALIENDO` decide: **30% vuelve a la fila** (nueva visita) y **70% se va**.

Si vuelve a la fila cuenta como una **visita nueva**: se reinician su llegada,
su paciencia y sus tiempos, y se sortea otra receta. Así las métricas (cola,
espera) se miden por visita y no arrastran tiempos de la visita anterior.

### Ayudante

Ciclo de trabajo:

`DESOCUPADO → BUSCANDO_PLATOS → RECOGIENDO_PLATOS → LLEVANDO_AL_LAVAPLATOS →
LAVANDO → SECANDO → GUARDANDO`

- Carga hasta 3 platos por viaje.
- Solo empieza cuando hay platos sucios.
- **Energía:** cada etapa completada gasta energía (3 a 6 puntos según la
  etapa). Si llega a 0 pasa a `DESCANSANDO`, recupera 8 por segundo y retoma
  su trabajo al llegar a 20. `DESCANSANDO` **no** forma parte de la cadena de
  Markov, porque lo decide la energía, no el azar.

### La cocina

Es un servidor de una sola plaza con cola FIFO (el primero que llega es el
primero en atenderse). Cada pedido gasta **un plato limpio**; sin platos
limpios la cocina se detiene hasta que el ayudante devuelva alguno.

## 5. Las cadenas de Markov

Una cadena de Markov dice: *"si estoy en este estado, ¿a cuál paso y con qué
probabilidad?"*. Aquí se guarda como **diccionario de listas**:

```python
"SALIENDO": [("HACER_FILA", 0.3), ("FIN", 0.7)]
```

Reglas que se cumplen:

- Las probabilidades que salen de un estado **suman 1** (0.3 + 0.7 = 1).
- La cadena es **lineal**: no se saltan etapas (de `LAVANDO` no se pasa
  directo a `GUARDANDO`).
- La mayoría de estados tiene una sola salida (1.0). Las decisiones reales son:

| Agente | Estado | Destinos |
|---|---|---|
| Cliente | `SALIENDO` | `HACER_FILA` 0.3 / `FIN` 0.7 |
| Ayudante | `LAVANDO` | `SECANDO` 0.9 / `LAVANDO` 0.1 (repite) |
| Ayudante | `SECANDO` | `GUARDANDO` 0.9 / `SECANDO` 0.1 (repite) |
| Ayudante | `GUARDANDO` | `DESOCUPADO` 0.5 / `BUSCANDO_PLATOS` 0.5 |

Si el ayudante **repite** una etapa, tarda lo mismo y gasta la misma energía
que la primera vez.

### Cómo se usa en el código

- `validar_transiciones` (en `agentes/markov.py`) revisa las tablas al cargar
  el programa: que sumen 1 y que apunten a estados que existen. Si algo está
  mal, el programa falla de inmediato.
- `siguiente_estado` sortea el destino. Usa el generador con semilla de la
  simulación y, si el estado tiene una sola salida, no sortea nada.

## 6. La salida de la consola

Al ejecutar `python main.py` se ve, en este orden:

1. **Encabezado y agentes:** quiénes participan.
2. **Cadenas de Markov:** los dos diccionarios de listas, ya validados.
3. **RESULTADOS:** el balance del restaurante.
4. **MARKOV: teórica vs observada:** compara la probabilidad de la tabla con la
   frecuencia con que realmente ocurrió cada decisión.
5. **Ruta de la carpeta de salida.**

### Qué significa cada resultado

| Línea | Significado |
|---|---|
| Clientes que llegaron / completaron / abandonaron | Total de clientes y cómo terminó cada uno. |
| Clientes todavía en el sistema | Seguían dentro cuando se acabó el tiempo. |
| Reingresos a la fila | Veces que un cliente decidió pedir otra vez. |
| Platos lavados | Platos que el ayudante devolvió limpios. |
| **Lq** | Promedio de clientes esperando en la cola de pedidos. |
| **Wq** | Segundos promedio de espera antes de que empiece su pedido. |
| Cola promedio para mesas | Clientes esperando mesa, en promedio. |
| Tiempo promedio en el sistema | Cuánto dura una visita completa. |
| Utilización de cocina / ayudante / mesas | Porcentaje del tiempo que estuvieron ocupados. |
| Promedio de platos sucios | Platos sucios acumulados, en promedio. |
| Tasa de salida | Clientes que terminan por minuto. |
| Probabilidad de abandono | Porcentaje de clientes que se fueron sin completar. |

### Teórica vs observada

Con pocas decisiones (pocos segundos simulados) las frecuencias pueden
alejarse de la teoría, por ejemplo 0.43 en lugar de 0.30. Es normal: con más
tiempo simulado se acercan. Para comprobarlo, sube `TIEMPO_SIMULACION` en
`main.py`.

## 7. Los archivos de la carpeta `salida/`

Los tres se generan **al final de la ejecución**, con `guardar_salida()`.
Durante la simulación, cada evento se guarda en una bitácora en memoria
(aunque no se imprima en consola) y cada sorteo de Markov se cuenta. Al
terminar, eso se escribe en disco.

| Archivo | Qué contiene | De dónde sale |
|---|---|---|
| `eventos.txt` | Bitácora segundo a segundo: llegadas, abandonos, acciones del ayudante y cada sorteo (`[MARKOV] Cliente 1: SALIENDO -> HACER_FILA (p=0.3)`). | La lista de eventos que se llena con cada `escribir_evento`. |
| `markov.json` | Las tablas de Markov, la semilla, `"validado": true` y las frecuencias teórica/observada. | Las tablas de los agentes y el conteo de sorteos. |
| `resultados.json` | Las mismas métricas de la sección RESULTADOS, como datos. | `calcular_resultados()`, la misma función que alimenta la consola. |

**Importante:** en cada ejecución estos archivos **se sobrescriben**. Si quieres
conservar una corrida, copia la carpeta `salida/` antes de volver a ejecutar.

La carpeta está en `.gitignore`, porque son archivos generados que se pueden
recrear ejecutando el programa.

## 8. Cómo ejecutar y configurar

```powershell
python main.py                     # ejecutar la simulación
python -m unittest discover -v     # correr las pruebas
```

Ajustes en `main.py`:

| Constante | Efecto |
|---|---|
| `TIEMPO_SIMULACION` | Segundos simulados (por defecto 300). |
| `SEMILLA_ALEATORIA` | Semilla del azar (por defecto 7). |
| `MOSTRAR_EVENTOS` | `True` imprime todos los eventos en consola. |
| `MOSTRAR_SORTEOS_MARKOV` | `True` imprime cada sorteo de Markov en consola. |
| `CARPETA_SALIDA` | Carpeta de los archivos; `None` para no guardarlos. |

Parámetros del restaurante (en `simulacion/restaurante.py`): tasa de llegada,
capacidad de la cola (7), número de mesas (3) y platos limpios iniciales (6).

## 9. Pruebas automáticas

`tests/test_agentes.py` comprueba, entre otras cosas, que:

- las probabilidades de cada estado suman 1;
- no hay saltos prohibidos entre estados;
- con probabilidad 1.0 el resultado es siempre el mismo y no se sortea;
- con semilla fija las frecuencias se acercan a las esperadas (0.3 y 0.1);
- el cliente puede volver a la fila y el ayudante puede repetir el lavado;
- la simulación completa produce métricas válidas.
