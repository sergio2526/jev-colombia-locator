# JEV Locator

Clasificador de lugares de Colombia: el usuario escribe un texto libre describiendo un
lugar y la app calcula un **score por departamento** y un **score por municipio** de qué
tan bien encaja cada uno con la descripción.

- **Datos de referencia**: [api-colombia.com](https://api-colombia.com/) (33 departamentos,
  incluyendo Bogotá D.C., y ~1123 municipios).
- **Motor de clasificación**: JEV
  (TypeSafe.ai System One Model), usando el primitivo `choice` para obtener una
  probabilidad calibrada por cada opción.
- **Backend**: Python 3.12 + Flask, gestionado con `uv`.

## Cómo funciona

1. El usuario envía un texto en el formulario.
2. Se llama a JEV una vez con los 33 departamentos como opciones (`choice` admite hasta
   255 opciones, así que entran en una sola llamada) → score por departamento.
3. En paralelo, se llama a JEV con los ~1123 municipios del país. Como superan el límite
   de 255 opciones por llamada, se trocean en ~5 bloques y se consultan en paralelo, y
   los resultados se combinan en una sola tabla ordenada por score.
4. El front muestra el departamento y el municipio con mayor score destacados, más la
   tabla completa de cada uno, y una sección de **uso de JEV** con una fila por cada
   llamada HTTP real hecha a la API (tokens de entrada/salida del objeto `usage` de esa
   respuesta), más los totales agregados.

> **Nota sobre los tokens**: el input de cada llamada está dominado por los criterios
> fijos que se reenvían siempre (nombres/descripciones de departamentos o municipios),
> no por el texto que escribe el usuario. Por eso el conteo de tokens varía poco entre
> textos distintos, aunque sí varía entre llamadas (según el tamaño de cada bloque).

> **Nota sobre el score nacional de municipios**: al trocear en varias llamadas
> independientes, JEV calcula la probabilidad de cada municipio solo contra los demás
> municipios de su mismo bloque. La comparación entre municipios de bloques distintos es
> por lo tanto aproximada (no hay una única distribución de probabilidad conjunta sobre
> los 1123 municipios).

## Variables de entorno

El proyecto ya trae un archivo `.env` en la raíz (sin valores) con estas variables;
solo tienes que completarlas:

| Variable | Descripción |
|---|---|
| `JEV_API_KEY` | API key (Bearer) de JEV/TypeSafe.ai. **Requerida.** |
| `JEV_API_URL` | Endpoint de JEV. Default: `https://api.typesafe.ai/v1/systemone`. |
| `JEV_MODEL` | Modelo a usar en cada request. Default: `jev-latest`. |
| `API_COLOMBIA_BASE_URL` | Base URL de api-colombia.com. Default: `https://api-colombia.com/api/v1`. |
| `FLASK_SECRET_KEY` | Clave para firmar sesión/flash messages de Flask. Opcional en local (hay un default de desarrollo en `config.py`); en producción debe ser un valor aleatorio y secreto. |
| `FLASK_DEBUG` | `true`/`false`, modo debug del servidor. |
| `FLASK_PORT` | Puerto del servidor. En este caso utilizamos 5050.

## Uso

```bash
uv sync
uv run jev-locator
# o bien, para elegir el puerto manualmente:
uv run flask --app jev_locator.app run --debug --port 5050
```

Abre `http://127.0.0.1:5050/` (o el puerto que hayas puesto en `FLASK_PORT`).

## Estructura

```
src/jev_locator/
  app.py              # rutas Flask (formulario + resultado)
  classifier.py        # orquesta la clasificación de depto/ciudad
  jev_client.py         # cliente HTTP de JEV (choice + chunking >255 opciones)
  colombia_client.py    # cliente HTTP de api-colombia.com (con cache en memoria)
  config.py             # carga de variables de entorno
  templates/             # index.html, result.html, base.html
  static/style.css
```
