# Simulación de restaurante con agentes

Simulación por consola de un restaurante sencillo. No requiere interacción ni
una interfaz gráfica: el programa avanza automáticamente en pasos de un segundo.

## Estructura del proyecto

```text
Modelos_simulacion/
├── agentes/
│   ├── cliente.py       # Objeto Cliente
│   └── ayudante.py      # Objeto Ayudante
├── simulacion/
│   └── restaurante.py   # Control y métricas de la simulación
├── tests/
│   └── test_agentes.py  # Pruebas de los objetos
└── main.py              # Punto de entrada
```

## Agentes

- `Cliente`: espera su pedido, recibe la comida, busca una mesa, come y sale.
  Puede abandonar si espera demasiado.
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

## Cambiar el escenario

En `main.py` se pueden modificar la duración, la semilla aleatoria y la salida
de eventos. En `simulacion/restaurante.py` están la tasa de llegada, capacidad
de la cola, número de mesas y platos iniciales.

## Pruebas

```bash
python3 -m unittest discover -v
```
