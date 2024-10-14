from collections.abc import Iterator

import pytest

from ethpm_types.sourcemap import SourceMap, SourceMapItem
from tests.conftest import COMPILED_BASE

SOURCE_MAP_FILES = {p.stem: p for p in sorted(COMPILED_BASE.glob("*.srcmap"))}


def serialize(sourcemap: Iterator[SourceMapItem]) -> str:
    result = ""
    previous_item = None
    for item in sourcemap:
        if item == previous_item:
            result += ";"
            continue

        skip_start = previous_item and item.start == previous_item.start
        skip_stop = previous_item and item.length == previous_item.length
        skip_contract_id = previous_item and item.contract_id == previous_item.contract_id
        skip_jump_code = previous_item and item.jump_code == previous_item.jump_code

        if skip_jump_code and skip_contract_id and skip_stop and skip_start:
            result += ";"

        elif skip_jump_code and skip_contract_id and skip_stop:
            result += str(item.start) if item.start is not None else "-1"
            result += ";"

        elif skip_jump_code and skip_contract_id:
            if not skip_start:
                result += str(item.start) if item.start is not None else "-1"
            result += ":"
            result += str(item.length) if item.length is not None else "-1"
            result += ";"

        elif skip_jump_code:
            if not skip_start:
                result += str(item.start) if item.start is not None else "-1"
            result += ":"
            if not skip_stop:
                result += str(item.length) if item.length is not None else "-1"
            result += ":"
            result += str(item.contract_id) if item.contract_id is not None else "-1"
            result += ";"

        else:
            if not skip_start:
                result += str(item.start) if item.start is not None else "-1"
            result += ":"
            if not skip_stop:
                result += str(item.length) if item.length is not None else "-1"
            result += ":"
            if not skip_contract_id:
                result += str(item.contract_id) if item.contract_id is not None else "-1"
            result += ":"
            result += item.jump_code
            result += ";"

        previous_item = item

    return result[:-1]  # Ignore last ";" char


@pytest.mark.parametrize("sourcemap_filename", SOURCE_MAP_FILES)
def test_source_map(sourcemap_filename):
    sourcemap = SOURCE_MAP_FILES[sourcemap_filename].read_text().strip()
    sourcemap_obj = SourceMap.model_construct(root=sourcemap)
    # Serialize back to the sourcemap to make sure we decoded it properly
    assert sourcemap[:10] == serialize(sourcemap_obj.parse())[:10]


def test_source_map_parse_from_vyper(sourcemap_from_vyper):
    """
    Ensure we don't break source mapping features on Vyper.
    """
    actual = list(sourcemap_from_vyper.parse())[1:]
    parts = sourcemap_from_vyper.root.strip().split(";")
    assert len(parts) == 608
    assert parts[52] == ":::-"
    assert len(actual) == 607
    assert actual[0].jump_code == "-"
    assert actual[45].start == 1434


def test_source_map_item():
    """
    Occasionally, you may need to parse individual source map items,
    like when they are coming from other compiler artifacts such as
    AST JSON.
    """
    src = "4:5:6"
    actual = SourceMapItem.parse_str(src)
    assert actual.start == 4
    assert actual.length == 5
    assert actual.contract_id == 6
    assert actual.jump_code == ""


def test_repr_and_str():
    key = list(SOURCE_MAP_FILES.keys())[0]
    sourcemap = SOURCE_MAP_FILES[key].read_text().strip()
    sourcemap_obj = SourceMap(root=sourcemap)
    assert repr(sourcemap_obj) == sourcemap
    assert str(sourcemap_obj) == sourcemap
