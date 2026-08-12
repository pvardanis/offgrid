"""What every call to LM Studio says when nothing is there to answer it.

A server that is not running fails the same way whatever was being asked, so
what to do about it is one sentence rather than one per call. The failures
that name an operation — a load that ran out of time, an answer that could
not be read — stay with the call that knows which operation it was.
"""


def nothing_answered_at(host: str) -> str:
    """Say that no server is listening, and what to do about it.

    :param host: Address the runtime was expected on.

    :return: What to tell whoever ran offgrid.
    """
    return (
        f"No model server answered at http://{host}. "
        "Start LM Studio, or point offgrid elsewhere with --host."
    )
