import concurrent.futures

import requests

from .config import config

# Límite documentado del primitivo `choice` de JEV: máximo 255 opciones por llamada.
JEV_MAX_CHOICES = 255


def _call_systemone(state: str, questions: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {config.JEV_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"state": state, "model": config.JEV_MODEL, "questions": questions}
    response = requests.post(config.JEV_API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def classify_choice(state: str, instructions: str, options: dict[str, str]) -> dict:
    """Clasifica `state` contra `options` (nombre -> criterio) con el primitivo choice de JEV.

    Si hay más de JEV_MAX_CHOICES opciones, se trocean en llamadas paralelas independientes
    y las probabilidades se combinan en un único dict. Nota: cuando hay troceo, las
    probabilidades de cada bloque las calcula JEV de forma aislada (solo contra las demás
    opciones de su propio bloque), así que la comparación entre bloques es aproximada.

    Devuelve {"probabilities": {...}, "usage": {...agregado...}, "calls": [...por llamada...]}.
    `calls` trae un elemento por cada request HTTP real hecho a JEV, con sus propios
    input_tokens/output_tokens/options_count — así se ve el detalle, no solo el total.
    """
    items = list(options.items())
    chunks = [items[i : i + JEV_MAX_CHOICES] for i in range(0, len(items), JEV_MAX_CHOICES)]

    def run_chunk(chunk: list[tuple[str, str]]) -> tuple[dict[str, float], dict, int]:
        response = _call_systemone(
            state=state,
            questions={
                "match": {
                    "type": "choice",
                    "instructions": instructions,
                    "criteria": dict(chunk),
                }
            },
        )
        return response["answers"]["match"]["probabilities"], response.get("usage", {}), len(chunk)

    if len(chunks) == 1:
        chunk_results = [run_chunk(chunks[0])]
    else:
        # executor.map conserva el orden de los chunks aunque se ejecuten en paralelo.
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            chunk_results = list(executor.map(run_chunk, chunks))

    probabilities: dict[str, float] = {}
    calls: list[dict] = []
    for probs, usage, options_count in chunk_results:
        probabilities.update(probs)
        calls.append(
            {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "options_count": options_count,
            }
        )

    return {
        "probabilities": probabilities,
        "usage": {
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "calls": len(calls),
        },
        "calls": calls,
    }
