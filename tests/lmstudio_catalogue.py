"""How LM Studio's catalogue describes one model.

The shape every capture in `tests/fixtures/` has: an id, a type, a state, the
ceiling the model states, and — only where something is holding it — the
window it is being served at.
"""


def describe_model(
    identifier: str, *, served: int | None, ceiling: int | None, in_memory: bool
) -> dict:
    """Describe one model the way LM Studio's catalogue does.

    :param identifier: The model's id.
    :param served: The context it is served at once it is loaded, or ``None``
        to leave the field out of a held model — a server that says what it is
        holding without saying what it is holding it at.
    :param ceiling: The context it states before anything loads it, or
        ``None`` to leave the field out. Every captured payload states one for
        every model, so that is what a parser reading an entry without it
        tolerates rather than something a server here has been seen to do.
    :param in_memory: Whether it is held.

    :return: One catalogue entry.
    """
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
    }

    if ceiling is not None:
        entry["max_context_length"] = ceiling

    if in_memory and served is not None:
        entry["loaded_context_length"] = served

    return entry
