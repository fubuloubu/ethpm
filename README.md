# EthPM v3 Implementation

EthPM is an Ethereum Package Manifest containing data types for contracts, deployments,
and source code using [EIP-2678](https://eips.ethereum.org/EIPS/eip-2678).
Validates and serializes contract related data and provides JSON schemas.

## Dependencies

* [python3](https://www.python.org/downloads) version 3.7 or greater, python3-dev

## Installation

### via `pip`

You can install the latest release via [`pip`](https://pypi.org/project/pip/):

```bash
pip install ethpm-types
```

### via `setuptools`

You can clone the repository and use [`setuptools`](https://github.com/pypa/setuptools) for the most up-to-date version:

```bash
git clone https://github.com/ApeWorX/ethpm-types.git
cd ethpm-types
python3 setup.py install
```

## Quick Usage

Starting with a dictionary of attribute data, such as a contract instance, you can
build an EthPM typed object.

```python
from ethpm_types import ContractInstance

# contract_dict assumes a pre-defined dictionary containing all required keywords/args
# contract_dict = {"keyword": "value",...}
contract = ContractInstance(**contract_dict)

print(contract.name)
```

## Development

This project is in development and should be considered a beta.
Things might not be in their final state and breaking changes may occur.
Comments, questions, criticisms and pull requests are welcomed.

## License

This project is licensed under the [Apache 2.0](LICENSE).
