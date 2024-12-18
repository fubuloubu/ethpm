import json
from collections.abc import Sequence
from enum import Enum
from hashlib import md5, sha3_256, sha256
from typing import Annotated, Any, Optional, Union

from eth_pydantic_types import HexStr
from pydantic import AnyUrl as _AnyUrl
from pydantic import FileUrl

CONTENT_ADDRESSED_SCHEMES = {"ipfs"}
AnyUrl = Union[FileUrl, _AnyUrl]


class Algorithm(str, Enum):
    """
    Algorithm enum options MD5, SHA3, and SHA256.
    """

    MD5 = "md5"
    SHA3 = "sha3"
    SHA256 = "sha256"


def compute_checksum(content: bytes, algorithm: Algorithm = Algorithm.MD5) -> HexStr:
    """
    Calculate the checksum of the given content.

    Args:
        content (bytes): Content to hash.
        algorithm (:class:`~ethpm_types.utils.Algorithm`)" The algorithm to use.

    Returns:
        :class:`~ethpm_types.utils.Hex`
    """

    if isinstance(algorithm, str):
        algorithm = Algorithm(algorithm)

    if algorithm is Algorithm.MD5:
        return HexStr.from_bytes(md5(content).digest())

    elif algorithm is Algorithm.SHA3:
        return HexStr.from_bytes(sha3_256(content).digest())

    elif algorithm is Algorithm.SHA256:
        return HexStr.from_bytes(sha256(content).digest())

    # TODO: Support IPFS CIDv0 & CIDv1
    # TODO: Support keccak256 (if even necessary, mentioned in EIP but not used)
    # TODO: Explore other algorithms needed
    else:
        raise ValueError(f"Unsupported algorithm '{algorithm}'.")


def stringify_dict_for_hash(
    data: dict, include: Optional[Sequence[str]] = None, exclude: Optional[Sequence[str]] = None
) -> str:
    """
    Convert the given dict to a consistent str that can be used in hash.

    Args:
        data (Dict): The data to stringify.
        include (Optional[Sequence[str]]): Optionally filter keys to include.
        exclude (Optional[Sequence[str]]): Optionally filter keys to exclude.

    Returns:
        str
    """

    if include:
        data = {k: v for k, v in data.items() if k in include}
    if exclude:
        data = {k: v for k, v in data.items() if k not in exclude}

    # For hashing and ID.
    # Recursively sort dictionaries based on values
    def _sort(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _sort(value[k]) for k in sorted(value)}
        elif isinstance(value, list):
            return [_sort(item) for item in value]

        return value

    sorted_settings = _sort(data or {})
    return json.dumps(sorted_settings, separators=(",", ":"), sort_keys=True)


def parse_signature(sig: str) -> tuple[str, list[tuple[str, str, str]], list[str]]:
    """
    Parse an event or function signature into name and inputs

    Args:
        sig (str): The string signature to parse.

    Returns:
        A tuple of (name, inputs, outputs) where inputs is a list of tuples of (type, indexed, arg
        name) and outputs is a list of types.
    """
    outsplit = sig.split(" -> ")
    std_sig = outsplit[0]
    outputs_maybe = ""
    if len(outsplit) > 1:
        outputs_maybe = outsplit[1]
    name, remainder = std_sig.split("(")
    input_tups = [
        tuple(y.strip().split(" "))
        for y in filter(lambda x: x, [x for x in remainder.rstrip(")").split(",")])
    ]
    inputs = []
    outputs = []

    for intup in input_tups:
        inlen = len(intup)
        if inlen == 1:
            inputs.append((intup[0], "", ""))
        elif inlen == 2:
            inputs.append((intup[0], "", intup[1]))
        elif inlen == 3 and intup[1] == "indexed":
            assert len(intup) == 3  # mypy more like mywhy
            inputs.append(intup)
        else:
            raise ValueError(f'Unexpected parameter format: {" ".join(intup)}')

    if outputs_maybe:
        for outtyp in outputs_maybe.strip("()").split(","):
            outputs.append(outtyp.strip())

    return (name, inputs, outputs)


SourceLocation = tuple[int, int, int, int]

__all__ = [
    "Algorithm",
    "Annotated",
    "compute_checksum",
    "CONTENT_ADDRESSED_SCHEMES",
    "SourceLocation",
]
