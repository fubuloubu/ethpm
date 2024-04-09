# Quick Start

EthPM is an Ethereum package manifest containing data types for contracts, deployments, and source code using [EIP-2678](https://eips.ethereum.org/EIPS/eip-2678).
The library validates and serializes contract related data and provides JSON schemas.

## Dependencies

- [python3](https://www.python.org/downloads) version 3.8 to 3.12.

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

Starting with a dictionary of attribute data, such as a contract instance, you can build an EthPM typed object.

```python
from ethpm_types import ContractInstance

contract = ContractInstance(contractType="ContractClassName", address="0x123...")
print(contract.contract_type)
```
