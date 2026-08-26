"""A model: the one a run asks for, and the one the runtime describes.

Two types rather than one, because the same two numbers mean different things
in each direction. A window a run states is the one being asked for; a window
the runtime states is the one being served. They can differ, and reading
either as the other is the failure the whole context split exists to prevent.
"""

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from offgrid.shared.exceptions import (
    ContextWindowUnworkableError,
    ModelUnavailableError,
    OffgridError,
)

# Which flag says each key, so a refusal names the one that was typed rather
# than the one that is refused most often.
FLAGS = {"identifier": "--model", "context_window": "--context-window"}


@dataclass(frozen=True, kw_only=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g.
        ``qwen/qwen3.6-35b-a3b``.
    :param context_ceiling: The most this model could be served at, and
        ``None`` when the runtime states none. A zero is a number the runtime
        stated: nothing here validates what it answered, so the two are told
        apart by what said them rather than by being falsy.
    :param context_window: What it is being served at now, and ``None`` when
        nothing is holding it — a stopped model is not being served at its
        ceiling, it is not being served.
    """

    identifier: str
    context_ceiling: int | None
    context_window: int | None


def refuse_a_yes_or_no(value: object) -> object:
    """Refuse a flag written where a number of tokens belongs.

    A boolean is an integer to anything that does not look: `32768` and `true`
    both arrive as numbers, the second one as 1. The run is then refused
    against the agent's floor, naming a window nobody wrote. The file's reader
    answers `yes` and `on` with the word rather than a boolean, so what this
    catches is what a caller hands over directly.

    :param value: What the file or the caller said the window is.

    :return: The value, for the rest of the validation to read.

    :raise ValueError: When it is a boolean.
    """
    if isinstance(value, bool):
        raise ValueError("a window is a number of tokens, not yes or no")

    return value


class ModelRequest(BaseModel):
    """The model a run asked the runtime to hold, and at what window.

    Naming neither is how a run says it wants whatever is already there, at
    whatever it is already served at, which costs no load.

    Validated rather than trusted, and a `BaseModel` rather than a dataclass
    for it, because it is the one of these two a person writes: `Model` is
    parsed from what a runtime answered, and this is stated on a command line
    or in a hand-edited file. Keys it does not name are refused, so a typo is
    reported rather than read as "nothing wanted".

    :param identifier: The model to hold, or ``None`` for whichever the
        runtime is already holding. Never empty: a name nobody typed is not
        the same statement as no name at all, and reading one as the other
        answers with the resident model where the runtime should have said it
        does not have that.
    :param context_window: The context to hold it at, or ``None`` to inherit
        whatever the runtime serves it at. Above zero, because zero is not a
        small window, it is not a window. It is a request, not a reading:
        what the runtime settles on is on the `Model` that comes back, and
        the two are only usually the same number.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    identifier: str | None = Field(default=None, min_length=1)
    context_window: Annotated[int | None, BeforeValidator(refuse_a_yes_or_no)] = Field(
        default=None, gt=0
    )


def read_what_was_typed(
    *, identifier: str | None, context_window: int | None
) -> ModelRequest:
    """Read what a command line asked for, refusing it in offgrid's own words.

    The type is the same one the profile is read through, so what it refuses
    is refused at both doors — but a validator's block of text is what the
    file's reader converts into a sentence, and the command line has no such
    reader. This is it.

    :param identifier: What was typed after the model flag, or ``None`` where
        it was left out.
    :param context_window: What was typed after the window flag, or ``None``
        where it was left out.

    :return: What this run asks for.

    :raise ModelUnavailableError: When the model flag was given a name that is
        no name, which is what an unset variable arrives as.
    :raise ContextWindowUnworkableError: When the window flag was given a
        number the request will not carry.
    """
    try:
        return ModelRequest(identifier=identifier, context_window=context_window)
    except ValidationError as error:
        raise _say_what_cannot_be_asked_for(error) from error


def _say_what_cannot_be_asked_for(error: ValidationError) -> OffgridError:
    """Turn what the request refused into the sentence a person reads.

    The flag is named from the key the validator rejected rather than written
    into the message, so what it says stays true of what was actually refused.
    The validator's own words are passed through beside it, which is what the
    file's reader does with the same refusal.

    :param error: What the request refused.

    :return: The error to raise, of the kind the refused key is about.
    """
    refused = error.errors()[0]
    key = str(refused["loc"][0])

    said = (
        f"`{FLAGS[key]}` was given {refused['input']!r}, which offgrid cannot "
        f"ask for: {refused['msg'].lower()}. Leave the flag out to take "
        "whatever the runtime is already holding."
    )

    if key == "context_window":
        return ContextWindowUnworkableError(said)

    return ModelUnavailableError(said)


def settle_what_to_run(typed: ModelRequest, *, stored: ModelRequest) -> ModelRequest:
    """Settle what a run asks for from what was typed and what was written down.

    Key by key, because the two are stated one at a time: a run naming a model
    and no window still wants the window somebody wrote down, and reading the
    pair as one would drop it back to whatever the runtime remembered.

    :param typed: What this run said, where it said anything.
    :param stored: What the profile says, where it says anything.

    :return: The model to hold, or ``None`` where neither named one, and the
        window to hold it at.
    """
    # Falling back on falsiness is safe here only because the request refuses
    # an empty name and a window of zero: neither can arrive as a statement.
    return ModelRequest(
        identifier=typed.identifier or stored.identifier,
        context_window=typed.context_window or stored.context_window,
    )
