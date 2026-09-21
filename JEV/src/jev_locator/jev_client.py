import concurrent.futures

from typesafe_sdk import Choice, TypeSafeClient

from .config import config

# Límite documentado del primitivo `choice` de JEV: máximo 255 opciones por llamada.
# El SDK no lo valida ni trocea por nosotros, así que el chunking sigue siendo manual.
JEV_MAX_CHOICES = 255

_client: TypeSafeClient | None = None


def _get_client() -> TypeSafeClient:
    global _client
    if _client is None:
        _client = TypeSafeClient(
            api_key=config.JEV_API_KEY,
            base_url=config.JEV_API_URL,
            model=config.JEV_MODEL,
        )
    return _client


def classify_choice(state: str, instructions: str, options: dict[str, str]) -> dict:
    """Clasifica `state` contra `options` (nombre -> criterio) con el primitivo choice de JEV.

    Si hay más de JEV_MAX_CHOICES opciones, se trocean en llamadas paralelas independientes
    y las probabilidades se combinan en un único dict. Nota: cuando hay troceo, las
    probabilidades de cada bloque las calcula JEV de forma aislada (solo contra las demás
    opciones de su propio bloque), así que la comparación entre bloques es aproximada.

    Devuelve {"probabilities": {...}, "usage": {...agregado...}, "calls": [...por llamada...]}.
    `calls` trae un elemento por cada request real hecho a JEV (reintentos automáticos del
    SDK ante 429/5xx/timeouts no cuentan como llamadas nuevas), con su propio
    input_tokens/output_tokens/options_count.
    """
    client = _get_client()
    items = list(options.items())
    chunks = [items[i : i + JEV_MAX_CHOICES] for i in range(0, len(items), JEV_MAX_CHOICES)]

    def run_chunk(chunk: list[tuple[str, str]]) -> tuple[dict[str, float], object, int]:
        response = client.system_one(
            state=state,
            questions={"match": Choice(instructions=instructions, criteria=dict(chunk))},
        )
        answer = response.choices["match"]
        return answer.probabilities, response.usage, len(chunk)

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
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
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
