import tempfile
from pathlib import Path

import pytest
from pydantic import FileUrl

from ethpm_types.source import Checksum, Compiler, Content, ContractSource, Source
from ethpm_types.utils import Algorithm, compute_checksum

SOURCE_LOCATION = (
    "https://github.com/OpenZeppelin/openzeppelin-contracts"
    "/blob/master/contracts/token/ERC20/IERC20.sol"
)


@pytest.fixture
def no_checksum() -> Source:
    return Source.model_validate({"source_id": "Foo.txt", "urls": [SOURCE_LOCATION]})


@pytest.fixture
def bad_checksum() -> Source:
    return Source.model_validate(
        {
            "source_id": "Foo.txt",
            "urls": [SOURCE_LOCATION],
            "checksum": {"algorithm": "md5", "hash": "0x"},
        }
    )


@pytest.fixture
def empty_source() -> Source:
    return Source.model_validate({"source_id": "Foo.txt", "content": ""})


def test_corrupt_source(bad_checksum, no_checksum):
    assert not no_checksum.content_is_valid()
    assert not bad_checksum.content_is_valid()


def test_empty_source(empty_source):
    assert empty_source.fetch_content() == ""
    assert empty_source.content_is_valid()


def test_source_repr(source):
    # Test default case.
    assert repr(source) == "<Source>"

    # Test that uses file URI when available.
    raw_uri = "file://path/to/file.vy"
    uri = FileUrl(raw_uri)
    source.urls = [uri]
    assert repr(source) == f"<Source {raw_uri}>"

    # Test that favors URI over checksum.
    checksum = source.calculate_checksum()
    source.checksum = checksum
    assert repr(source) == f"<Source {uri}>"

    # Test that uses checksum if available and no URI.
    source.urls = []
    assert repr(source) == f"<Source {checksum.hash}>"


def test_source_validate(source):
    src = source  # alias for avoiding pdb name conflict
    src_dict = src.model_dump()
    assert isinstance(src_dict["content"], str)
    assert source.model_validate(src)
    assert source.model_validate(src_dict)

    # Change src to a dict and retry
    src_dict["content"] = {i + 1: ln for i, ln in enumerate(src_dict["content"])}
    assert source.model_validate(src_dict)


def test_source_line_access(source, content_raw):
    lines = content_raw.splitlines()
    assert source[0] == lines[0]
    assert source[1] == lines[1]
    assert source[2] == lines[2]
    assert source[-1] == lines[-1]
    assert source[3:5] == lines[3:5]


def test_source_enumerate(source):
    for line_idx, line in enumerate(source):
        assert isinstance(line_idx, int)
        assert isinstance(line, str)


def test_source_len(source, content_raw):
    assert len(source) == len(content_raw.splitlines())


def test_content(content, content_raw):
    assert isinstance(content, Content)
    assert str(content) == content_raw
    # `__getitem__` works off linenos
    assert content[1] == "# @version 0.3.9"
    # slices are lineno-based from `content` because `root` is a dict.
    # Sometimes, like when building source tracebacks, not all lines are present.
    # In the `Source` object, for its content, all lines are always there.
    # Thus, its `__getitem__` is index based.
    assert content[1:2] == ["# @version 0.3.9"]
    assert content.begin_lineno == 1
    # The last line number is the same as the length of list of lines.
    length = len(content_raw.splitlines())
    assert content.end_lineno == length
    assert content.line_numbers == list(range(1, length + 1))
    assert content.encode("utf8") == content_raw.encode("utf8")
    lines = content_raw.splitlines()
    assert list(content.items())[:3] == [
        (1, lines[0]),
        (2, lines[1]),
        (3, lines[2]),
    ]
    assert [x for x in content][:3] == lines[:3]


def test_content_chunk(content_raw):
    """
    Proves that we can work with chunks of content,
    as is needed when forming source tracebacks.
    """
    chunk = content_raw.splitlines()[6:9]
    data = {7: chunk[0], 8: chunk[1], 9: chunk[2]}
    content = Content.model_validate(data)
    assert content.begin_lineno == 7
    assert content.end_lineno == 9
    assert len(content) == 3


def test_content_from_str():
    lines = ("I am content", " I am line 2 of content")
    content_str = "\n".join(lines)
    content = Content.model_validate(content_str)
    assert content[1] == lines[0]  # Line 1
    assert content[2] == lines[1]  # Line 2

    # Assert it passes re-validation.
    content.model_validate(content)


def test_content_from_dict():
    lines = {1: "I am content", 2: "I am line 2 of content"}
    content = Content.model_validate(lines)
    assert content[1] == lines[1]  # Line 1
    assert content[2] == lines[2]  # Line 2

    # Assert it passes re-validation.
    content.model_validate(content)


def test_content_from_root_dict():
    """
    Handles weird root-model behavior.
    """
    lines = {"_root": {1: "I am content", 2: "I am line 2 of content"}}
    content = Content.model_validate(lines)
    assert content[1] == lines["_root"][1]  # Line 1
    assert content[2] == lines["_root"][2]  # Line 2

    # Assert it passes re-validation.
    content.model_validate(content)


def test_content_with_root_suffix_in_line():
    """
    Tests against a strange bug where if your file contained
    ``_root``, it would cause an issue.
    """
    lines = {1: "I am _root"}
    content = Content.model_validate(lines)
    assert content[1] == "I am _root"


def test_content_from_path():
    lines = ("I am content", " I am line 2 of content")
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "Contract.vy"
        path.write_text("\n".join(lines))
        content = Content.model_validate(path)
        assert content[1] == lines[0]  # Line 1
        assert content[2] == lines[1]  # Line 2

        # Assert it passes re-validation.
        content.model_validate(content)


def test_content_from_root_path():
    lines = ("I am content", " I am line 2 of content")
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "Contract.vy"
        path.write_text("\n".join(lines))
        content = Content.model_validate(path)
        assert content[1] == lines[0]  # Line 1
        assert content[2] == lines[1]  # Line 2

        # Assert it passes re-validation.
        content.model_validate(content)


@pytest.mark.parametrize("val", ("", {}, None))
def test_content_validate_empty(val):
    content = Content.model_validate(val)
    assert content.model_validate(val) == Content(root={})


def test_contract_source(vyper_contract, source, source_base):
    actual = ContractSource.create(vyper_contract, source, source_base)
    assert actual.contract_type == vyper_contract
    assert actual.source == source
    assert actual.source_path == source_base / vyper_contract.source_id
    assert repr(actual) == "<contracts/VyperContract.vy::VyperContract>"

    # Get a location we can use as an input (that we know should work).
    fn_name = "getEmptyTupleOfDynArrayStructs"
    fn = [x for x in actual.ast.functions if x.name == fn_name][0]
    location = fn.line_numbers

    function = actual.lookup_function(location)
    # Tests ``Function`` class here.
    assert function.name == "getEmptyTupleOfDynArrayStructs"
    assert (
        function.full_name
        == "getEmptyTupleOfDynArrayStructs() -> (DynArray[MyStruct, 10], DynArray[MyStruct, 10])"
    )
    assert repr(function) == "<Function getEmptyTupleOfDynArrayStructs>"
    # Ensure signature lines are also in content.
    assert str(function.content).splitlines()[0].startswith("def getEmptyTupleOfDynArrayStructs()")


def test_contract_source_use_method_id(vyper_contract, source, source_base):
    actual = ContractSource.create(vyper_contract, source, source_base)

    # Get a location we know will work.
    fn_name = "getEmptyTupleOfDynArrayStructs"
    fn = [x for x in actual.ast.functions if x.name == fn_name][0]
    location = fn.line_numbers

    hash_fn = vyper_contract._selector_hash_fn
    abi = vyper_contract.methods[fn_name]
    method_id = hash_fn(abi.selector)

    function = actual.lookup_function(location, method_id=method_id)
    assert function.name == fn_name
    assert function.full_name == "getEmptyTupleOfDynArrayStructs()"


def test_compiler_equality():
    compiler_1 = Compiler(
        name="yo", version="0.1.0", settings={"evmVersion": "shanghai"}, contractType=["test1"]
    )
    compiler_2 = Compiler(
        name="yo",
        version="0.1.0",
        settings={"evmVersion": "shanghai"},
        contractType=["test1", "test2"],
    )
    assert compiler_1 == compiler_2

    # Name affects equality.
    compiler_1.name = "yo2"
    assert compiler_1 != compiler_2
    compiler_1.name = compiler_2.name

    # Version affects equality.
    compiler_1.version = "0.100000.0"
    assert compiler_1 != compiler_2
    compiler_1.version = compiler_2.version

    # Settings affect equality.
    compiler_2.settings["evmVersion"] = "london"
    assert compiler_1 != compiler_2
    compiler_2.settings["evmVersion"] = "shanghai"


def test_compiler_hash():
    compiler_1 = Compiler(
        name="yo", version="0.2.0", settings={"evmVersion": "shanghai"}, contractType=["test1"]
    )
    compiler_2 = Compiler(
        name="foo",
        version="0.1.0",
        settings={"evmVersion": "shanghai", "outputSelection": {"test1": ["*"]}},
        contractType=["test1", "test2"],
    )
    compiler_3 = Compiler(
        name="yo",
        version="0.2.0",
        settings={"evmVersion": "shanghai"},
        contractType=["test1", "test2"],
    )
    compiler_4 = Compiler(
        name="yo",
        version="0.2.0",
        settings={"evmVersion": "shanghai", "optimizer": {"enabled": False, "runs": 200}},
        contractType=["test1"],
    )
    compiler_5 = Compiler(
        name="yo",
        version="0.2.0",
        settings={"evmVersion": "shanghai", "optimize": True},
        contractType=["test1"],
    )
    compiler_set = {compiler_1, compiler_2, compiler_3, compiler_4, compiler_5}
    assert len(compiler_set) == 4
    assert compiler_1 in compiler_set
    assert compiler_2 in compiler_set
    assert compiler_3 in compiler_set
    assert compiler_4 in compiler_set
    assert compiler_5 in compiler_set


def test_checksum_from_file():
    file = Path(tempfile.mktemp())
    file.write_text("foobartest123")
    actual = Checksum.from_file(file)
    expected = Checksum(
        algorithm=Algorithm.MD5,
        hash=compute_checksum(file.read_bytes()),
    )
    assert actual == expected


def test_source_excludes_extra_lines():
    content = "helloworld\n\n\n  \n\n\t\n\n"
    source = Source(content=content)
    assert len(source) == 1


def test_references():
    """
    Tests against a bug where the model validation
    would accidentally ignore all extra properties.
    """
    source = Source(content="foo\n", references=["bar.txt"])
    assert source.references == ["bar.txt"]


def test_model_validate_empty_str():
    """
    There was a bug where if a file was empty,
    it would try to use the empty str as a
    dict to create the source content, due to an improper
    truthy check.
    """
    source = Source.model_validate("")
    assert isinstance(source, Source)
