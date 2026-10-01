# Simulación de restaurante con agentes

Simulación por consola de un restaurante sencillo. No requiere interacción ni
una interfaz gráfica: el programa avanza automáticamente en pasos de un segundo.

## Estructura del proyecto

```text
Modelos_simulacion/
├── agentes/
│   ├── cliente.py       # Objeto Cliente
│   ├── ayudante.py      # Objeto Ayudante
│   └── markov.py        # Validación y sorteo de cadenas de Markov
├── simulacion/
│   └── restaurante.py   # Control y métricas de la simulación
├── tests/
│   └── test_agentes.py  # Pruebas de los objetos
└── main.py              # Punto de entrada
```

## Agentes

- `Cliente`: espera su pedido, recibe la comida, busca una mesa, come y sale.
  Puede abandonar si espera demasiado. Al terminar de comer decide con una
  cadena de Markov si vuelve a hacer fila o se va (ver más abajo).
- `Ayudante`: busca platos sucios, los recoge, lleva al lavaplatos, lava, seca y
  guarda. Tiene un sistema dinámico de energía (barra mostrada por consola):
  cada etapa completada del ciclo le consume energía y, al llegar a 0, entra
  en el estado `DESCANSANDO` para recuperarse antes de seguir trabajando.

  Ecuación del sistema (integrador discreto, un paso = 1 segundo):

  ```text
  E(t+1) = clamp(E(t) - gasto(estado_completado) + r · [estado == DESCANSANDO], 0, E_max)
  ```

  - `E_max = 100`, umbral para reanudar trabajo = 20.
  - `gasto(estado)` (energía por etapa completada): buscar=3, recoger=4,
    llevar=3, lavar=6, secar=4, guardar=3.
  - `r = 8` (energía recuperada por segundo en reposo).

  Estos valores se definen en `Ayudante` (`agentes/ayudante.py`) y se
  eligieron para que el ayudante trabaje varios ciclos completos antes de
  agotarse y se recupere en pocos segundos, sin detener la simulación por
  periodos prolongados.

## Cadenas de Markov

Los estados de ambos agentes se modelan como cadena de Markov lineal (no se
salta ninguna etapa), guardada como diccionario de listas
`estado -> [(destino, probabilidad), ...]`. Las probabilidades que salen de
un mismo estado suman 1; `validar_transiciones` lo comprueba al importar los
módulos y `siguiente_estado` sortea con el generador de la simulación
(`self.aleatorio`), por lo que la semilla sigue dando corridas idénticas.

**Cliente** (`TRANSICIONES_CLIENTE`): solo hay decisión al terminar de comer.

| Estado | Destinos (probabilidad) |
|---|---|
| `SALIENDO` | `HACER_FILA` 0.3, `FIN` 0.7 |
| Demás estados | una sola salida, 1.0 |

Si vuelve a la fila se cuenta como una **visita nueva**: se reinician llegada,
paciencia y tiempos, y se sortea una receta nueva (Lq y Wq se miden por
visita). `ABANDONO` no está en la cadena: lo causa la paciencia agotada.

**Ayudante** (`TRANSICIONES_AYUDANTE`):

| Estado | Destinos (probabilidad) |
|---|---|
| `LAVANDO` | `SECANDO` 0.9, `LAVANDO` 0.1 (repite) |
| `SECANDO` | `GUARDANDO` 0.9, `SECANDO` 0.1 (repite) |
| `GUARDANDO` | `DESOCUPADO` 0.5, `BUSCANDO_PLATOS` 0.5 |
| Demás estados | una sola salida, 1.0 |

`DESCANSANDO` queda fuera de la cadena porque lo gobierna la energía. Repetir
una etapa vuelve a durar lo mismo y a gastar su energía.

La cocina se representa como un servidor FIFO. También existen tres recursos
limitados: mesas, platos limpios y capacidad de la cola.

## Ejecutar

```bash
python3 main.py
```

La simulación muestra los eventos y al final presenta las siguientes métricas:

- `Lq`: número promedio de clientes esperando en la cola de pedidos.
- `Wq`: tiempo promedio antes de comenzar la preparación.
- Utilización de cocina, ayudante y mesas.
- Tiempo promedio dentro del sistema.
- Tasa de salida y probabilidad de abandono.
- Promedio de platos sucios pendientes.
- Reingresos a la fila (clientes que deciden pedir otra vez).

La barra de energía del ayudante se imprime solo cuando cambia su estado y en
el resumen de cada minuto.

## Cambiar el escenario

En `main.py` se pueden modificar la duración, la semilla aleatoria y la salida
de eventos. En `simulacion/restaurante.py` están la tasa de llegada, capacidad
de la cola, número de mesas y platos iniciales.

## Pruebas

```bash
python3 -m unittest discover -v
```
