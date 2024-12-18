from typing import Any

import pytest
from eth_pydantic_types import HexBytes

from ethpm_types import BaseModel


@pytest.fixture
def MyModel() -> type:
    class _MyModel(BaseModel):
        name: str
        input_types: dict[str, Any]

    return _MyModel


@pytest.mark.parametrize("mode", ("python", "json"))
def test_model_dump(mode, MyModel):
    model = MyModel(name="foo", input_types={"name": [HexBytes(123)]})
    actual = model.model_dump(mode=mode)
    assert isinstance(actual, dict)
    assert actual["name"] == "foo"
    assert len(actual["input_types"]) == 1


def test_model_dump_json(MyModel):
    model = MyModel(name="foo", input_types={"name": [HexBytes(123)]})
    actual = model.model_dump_json()
    assert actual == '{"input_types":{"name":["{"]},"name":"foo"}'
