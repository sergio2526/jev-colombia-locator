import concurrent.futures

from . import colombia_client, jev_client

DEPARTMENT_INSTRUCTIONS = (
    "El usuario describe en texto libre un lugar de Colombia. Elige el departamento "
    "colombiano cuya ubicación, geografía o descripción encaje mejor con lo descrito."
)

CITY_INSTRUCTIONS = (
    "El usuario describe en texto libre un lugar de Colombia. Elige el municipio "
    "colombiano (de cualquier departamento) que mejor encaje con lo descrito."
)


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"


def classify_department(text: str) -> dict:
    departments = colombia_client.get_departments()
    criteria = {d["name"]: _truncate(d.get("description") or d["name"], 400) for d in departments}

    outcome = jev_client.classify_choice(
        state=text, instructions=DEPARTMENT_INSTRUCTIONS, options=criteria
    )
    probabilities = outcome["probabilities"]

    results = [
        {"id": d["id"], "name": d["name"], "score": probabilities.get(d["name"], 0.0)}
        for d in departments
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"results": results, "usage": outcome["usage"], "calls": outcome["calls"]}


def classify_city(text: str) -> dict:
    cities = colombia_client.get_cities()
    department_names = {d["id"]: d["name"] for d in colombia_client.get_departments()}

    # Se usa el id como clave del criterio (no el nombre) porque ~70 nombres de
    # municipio se repiten entre departamentos (ej. "San Pedro" existe 3 veces).
    criteria: dict[str, str] = {}
    lookup: dict[str, dict] = {}
    for city in cities:
        key = str(city["id"])
        department_name = department_names.get(city["departmentId"], "")
        criteria_text = f"{city['name']}, municipio del departamento de {department_name}."
        description = city.get("description") or ""
        if description:
            criteria_text += " " + _truncate(description, 200)
        criteria[key] = criteria_text
        lookup[key] = {"name": city["name"], "department": department_name}

    outcome = jev_client.classify_choice(
        state=text, instructions=CITY_INSTRUCTIONS, options=criteria
    )
    probabilities = outcome["probabilities"]

    results = [
        {
            "id": int(key),
            "name": lookup[key]["name"],
            "department": lookup[key]["department"],
            "score": score,
        }
        for key, score in probabilities.items()
        if key in lookup
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"results": results, "usage": outcome["usage"], "calls": outcome["calls"]}


def _add_usage(a: dict, b: dict) -> dict:
    return {
        "input_tokens": a["input_tokens"] + b["input_tokens"],
        "output_tokens": a["output_tokens"] + b["output_tokens"],
        "calls": a["calls"] + b["calls"],
    }


def classify_text(text: str) -> dict:
    """Clasifica `text` contra los 33 departamentos y los ~1123 municipios de Colombia.

    Las dos clasificaciones son independientes (alcance nacional para ciudades, no
    limitado al departamento ganador) así que se ejecutan en paralelo.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        department_future = executor.submit(classify_department, text)
        city_future = executor.submit(classify_city, text)
        department_outcome = department_future.result()
        city_outcome = city_future.result()

    departments = department_outcome["results"]
    cities = city_outcome["results"]

    department_calls = department_outcome["calls"]
    city_calls = city_outcome["calls"]
    usage_calls = [
        {
            "stage": "Departamento"
            if len(department_calls) == 1
            else f"Departamento (bloque {i}/{len(department_calls)})",
            **call,
        }
        for i, call in enumerate(department_calls, start=1)
    ] + [
        {"stage": f"Municipios (bloque {i}/{len(city_calls)})", **call}
        for i, call in enumerate(city_calls, start=1)
    ]

    return {
        "departments": departments,
        "cities": cities,
        "top_department": departments[0] if departments else None,
        "top_city": cities[0] if cities else None,
        "usage": {
            "department": department_outcome["usage"],
            "city": city_outcome["usage"],
            "total": _add_usage(department_outcome["usage"], city_outcome["usage"]),
            "calls": usage_calls,
        },
    }
