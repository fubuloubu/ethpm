from collections.abc import Iterator
from typing import TYPE_CHECKING, Optional, Union

from pydantic import RootModel, model_validator

from ethpm_types.base import BaseModel

if TYPE_CHECKING:
    from ethpm_types.utils import SourceLocation


class SourceMapItem(BaseModel):
    """
    An object modeling a node in a source map; useful for mapping
    the source map string back to source code.
    """

    # NOTE: `None` entry means this path was inserted by the compiler during codegen
    start: Optional[int] = None
    """
    The byte-offset start of the range in the source file.
    """

    length: Optional[int] = None
    """
    The byte-offset length.
    """

    contract_id: Optional[int] = None
    """
    The source identifier.
    """

    jump_code: str
    """
    An identifier for whether a jump goes into a function, returns from a function,
    or is part of a loop.
    """
    # NOTE: ignore "modifier_depth" keyword introduced in solidity >0.6.x

    @classmethod
    def parse_str(cls, src_str: str, previous: Optional["SourceMapItem"] = None) -> "SourceMapItem":
        row: list[Union[int, str]] = [int(i) if i.isnumeric() else i for i in src_str.split(":")]

        if previous is None:
            start = int(cls._extract_value(row, 0) or -1)
            length = int(cls._extract_value(row, 1) or -1)
            contract_id = int(cls._extract_value(row, 2) or -1)
            jump_code = cls._extract_value(row, 3) or ""

        else:
            start = int(cls._extract_value(row, 0, previous=previous.start or -1))
            length = int(cls._extract_value(row, 1, previous=previous.length or -1))
            contract_id = int(cls._extract_value(row, 2, previous=previous.contract_id or -1))
            jump_code = cls._extract_value(row, 3, previous=previous.jump_code or "")

        return SourceMapItem.model_construct(
            # NOTE: `-1` for these three entries means `None`
            start=start if start != -1 else None,
            length=length if length != -1 else None,
            contract_id=contract_id if contract_id != -1 else None,
            jump_code=jump_code,
        )

    @staticmethod
    def _extract_value(
        row: list[Union[str, int]], item_idx: int, previous: Optional[Union[int, str]] = None
    ):
        if len(row) > item_idx and row[item_idx] != "":
            return row[item_idx]

        return previous


class SourceMap(RootModel[str]):
    """
    As part of the Abstract Syntax Tree (AST) output, the compiler provides the range
    of the source code that is represented by the respective node in the AST.

    This can be used for various purposes ranging from static analysis tools that
    report errors based on the AST and debugging tools that highlight local variables
    and their uses.

    `Solidity Doc <https://docs.soliditylang.org/en/v0.8.15/internals/source_mappings.html>`__.
    """

    def __repr__(self) -> str:
        return self.root

    def __str__(self) -> str:
        return self.root

    def parse(self) -> Iterator[SourceMapItem]:
        """
        Parses the source map string into a stream of
        :class:`~ethpm_types.contract_type.SourceMapItem` items.
        Useful for when parsing the map according to compiler-specific
        decompilation rules back to the source code language files.

        Returns:
            Iterator[:class:`~ethpm_types.contract_type.SourceMapItem`]
        """

        item = None

        # NOTE: Format of SourceMap is like `1:2:3:a;;4:5:6:b;;;`
        #       where an empty entry means to copy the previous step.
        #       This is because sourcemaps are compressed to save space.
        for i, row in enumerate(self.root.strip().split(";")):
            # NOTE: Set ``item`` so it updates each time for `previous` kwarg.
            item = SourceMapItem.parse_str(row, previous=item)
            yield item


class PCMapItem(BaseModel):
    """
    Line information for a given EVM instruction.

    These are utilized in the pc-map by which the compiler generates source code spans for given
    program counter positions.
    """

    line_start: Optional[int] = None
    column_start: Optional[int] = None
    line_end: Optional[int] = None
    column_end: Optional[int] = None
    dev: Optional[str] = None

    @property
    def location(self) -> "SourceLocation":
        return (
            (self.line_start or -1),
            (self.column_start or -1),
            (self.line_end or -1),
            (self.column_end or -1),
        )


RawPCMapItem = dict[str, Optional[Union[str, list[Optional[int]]]]]
RawPCMap = dict[str, RawPCMapItem]


class PCMap(RootModel[RawPCMap]):
    """
    A map of program counter values to statements in the source code.

    This can be used for various purposes ranging from static analysis tools that
    report errors based on the program counter value and debugging tools that highlight local
    variables and their uses.
    """

    @model_validator(mode="before")
    def validate_full(cls, value):
        # * Allows list values; turns them to {"location": value}.
        # * Allows `None`; turns it to {"location": None}
        # Else, expects dictionaries. This allows starting with a simple
        # location data but allowing compilers to enrich fields.

        return {
            f"{k}": ({"location": v} if isinstance(v, list) else v or {"location": None})
            for k, v in ((value or {}).get("root", value) or {}).items()
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def __getitem__(self, pc: Union[int, str]) -> RawPCMapItem:
        return self.root[str(pc)]

    def __setitem__(self, pc: Union[int, str], value: RawPCMapItem):
        value_dict: dict = {"location": value} if isinstance(value, list) else value
        self.root[str(pc)] = value_dict

    def __contains__(self, pc: Union[int, str]) -> bool:
        return str(pc) in self.root

    def parse(self) -> dict[int, PCMapItem]:
        """
        Parses the pc map string into a map of ``PCMapItem`` items, using integer pc values as keys.

        The format from the compiler will have numeric string keys with lists of ints for values.
        These integers represent (in order) the starting line, starting column, ending line, and
        ending column numbers.
        """
        results = {}

        for key, value in self.root.items():
            location = value["location"]
            dev = str(value["dev"]) if "dev" in value and value["dev"] is not None else None
            if location is not None:
                result = PCMapItem(
                    line_start=int(location[0]) if location[0] is not None else None,
                    column_start=int(location[1]) if location[1] is not None else None,
                    line_end=int(location[2]) if location[2] is not None else None,
                    column_end=int(location[3]) if location[3] is not None else None,
                    dev=dev,
                )
            else:
                result = PCMapItem(dev=dev)

            results[int(key)] = result

        return results
