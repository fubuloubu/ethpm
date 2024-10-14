from pathlib import Path

import pytest

from ethpm_types import ContractType, PackageManifest, Source, SourceMap

BASE = Path(__file__).parent / "data"
COMPILED_BASE = BASE / "Compiled"
SOURCE_BASE = BASE / "Sources"
SOURCE_ID = "VyperContract.vy"


@pytest.fixture
def get_contract_type(get_source_path):
    def fn(name: str) -> ContractType:
        model = (COMPILED_BASE / f"{name}.json").read_text()
        return ContractType.model_validate_json(model)

    return fn


@pytest.fixture
def get_source_path():
    def fn(name: str, base: Path = SOURCE_BASE) -> Path:
        contracts_path = base / "contracts"
        if not contracts_path.is_dir():
            raise AssertionError("test setup failed - contracts directory not found")

        for path in contracts_path.iterdir():
            if path.stem == name:
                return path

        raise AssertionError("test setup failed - test file '{name}' not found")

    return fn


@pytest.fixture
def oz_package_manifest_path():
    return COMPILED_BASE / "OpenZeppelinContracts.json"


@pytest.fixture
def oz_package(oz_package_manifest_path):
    model = oz_package_manifest_path.read_text()
    return PackageManifest.model_validate_json(model)


@pytest.fixture
def source_base() -> Path:
    return SOURCE_BASE


@pytest.fixture
def oz_contract_type(oz_package):
    # NOTE: AccessControl has events, view methods, and mutable methods.
    return oz_package.contract_types["AccessControl"]


@pytest.fixture
def content_raw(get_source_path) -> str:
    return get_source_path("VyperContract").read_text()


@pytest.fixture
def source(content_raw) -> Source:
    return Source.model_validate({"source_id": SOURCE_ID, "content": content_raw})


@pytest.fixture
def content(source):
    return source.content


@pytest.fixture
def vyper_contract(get_contract_type):
    return get_contract_type("VyperContract")


@pytest.fixture
def solidity_contract(get_contract_type):
    return get_contract_type("SolidityContract")


@pytest.fixture
def contract_with_error(get_contract_type):
    return get_contract_type("HasError")


@pytest.fixture(params=("Vyper", "Solidity"))
def contract(request, get_contract_type):
    yield get_contract_type(f"{request.param}Contract")


@pytest.fixture
def solidity_fallback_and_receive_contract(get_contract_type):
    return get_contract_type("SolFallbackAndReceive")


@pytest.fixture
def vyper_default_contract(get_contract_type):
    return get_contract_type("VyDefault")


@pytest.fixture(params=("Vyper", "Solidity"))
def fallback_contract(request, get_contract_type):
    key = "VyDefault" if request.param == "Vyper" else "SolFallbackAndReceive"
    return get_contract_type(key)


@pytest.fixture
def package_manifest(solidity_contract, vyper_contract, get_source_path):
    return PackageManifest(
        contractTypes={
            solidity_contract.name: solidity_contract,
            vyper_contract.name: vyper_contract,
        },
        sources={
            solidity_contract.source_id: {
                "content": get_source_path("SolidityContract"),
            },
            vyper_contract.source_id: {"content": get_source_path("VyperContract")},
        },
    )


@pytest.fixture
def sourcemap_from_vyper():
    """
    Output from:
    `vvm.vvm_compile_standard()["evm"]["deployedBytecode"]["sourceMap"]`.
    """
    root = "-1:-1:0:-;;;;:::-;;:::-;:::-;;;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;:::-;;;;1441:4;1959:3;1434:11;-1:-1;1434:28;:::-;1457:5;1959:3;1450:12;-1:-1;;1434:28;:::-;:::-;;:::-;1427:35;;:::-;1552:10;1540;1531:44;1565:3;-1:-1;;1568:3;-1:-1;;1571:3;-1:-1;;1575:0;-1:-1;;;1531:44;;1650:20;:31;-1:-1;;;;;;;1650:31;-1:-1;;;:::-;;;;;;;;:::-;;;;;:::-;;;;;;;:::-;;;;1650:31;-1:-1;1894:32;;;;;;;-1:-1;;;;;;;1894:32;-1:-1;;;:::-;;;;;;;;:::-;;;;;:::-;;;;;;;:::-;;;;1894:32;-1:-1;1959:3;-1:-1;;1947:16;-1:-1;1947:16;;:::i;:::-;;:37;1966:18;-1:-1;;1947:37;-1:-1;;;1947:37;-1:-1;;;;;;;:::-;1947:37;;;;1932:52;;1989:12;;;;-1:-1;2013:3;-1:-1;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;:::-;2041:9;;2087:1;2074:14;;2075:8;-1:-1;;;;;;;:::-;2074:14;;-1:-1;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;:::-;2117:9;;2150:1;:14;2155:8;2150:14;-1:-1;;;;;;;:::-;2150:14;;-1:-1;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;:::-;2190:9;;2227:1;2223:5;;-1:-1;;:::-;2223:5;:1;-1:-1;2223:5;;-1:-1;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;:::-;2254:9;;2291:1;2287:5;;-1:-1;;:::-;2287:5;:1;:5;;;-1:-1;;;;;:::-;;;;;:::-;;;;;:::-;2366:3;-1:-1;2352:13;-1:-1;;;;;:::-;2352:18;;-1:-1;;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;:::-;2407:10;;2467;2462:1;-1:-1;;2455:22;:::-;-1:-1;;;;;;;2514:1;-1:-1;;2507:23;:::-;2574:10;-1:-1;2569:1;-1:-1;;2562:22;:::-;2622:4;-1:-1;;2628:5;-1:-1;;2635:4;-1:-1;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;:::-;;;;;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;:::-;;;;;:::-;;;;;:::-;;;;;;;;;;;;;:::-;;:::-;;;;2659:402::-;2714:5;2705:1;-1:-1;2709:1;-1:-1;;;;;;:::-;2705:5;;-1:-1;2705:32;:::-;-1:-1;2705:32;:::-;:::-;2732:5;2723:1;-1:-1;2727:1;-1:-1;;;;;;:::-;2723:5;;-1:-1;;2705:32::-;2698:39;;:::-;2799:1;2793:18;;2802:8;2793:18;;;2786:4;2778;2772;2768:1;-1:-1;2768:8;2757:26;:33;:54;2742:69;;2819:18;:3;:10;2825:4;2819:10;-1:-1;2819:10;2825:4;-1:-1;;;;:::-;2819:10;;-1:-1;2816:41;:::-;2854:3;-1:-1;;2847:10;;;:::o;2816:41::-;-1:-1;;3056:5;2659:402::-;-1:-1::-;:::-;;;"  # noqa: E501
    return SourceMap(root=root)
