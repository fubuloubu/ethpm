from functools import cached_property, singledispatchmethod
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Type, TypeVar, Union, cast

from eth_pydantic_types import Address, HashStr32, HexBytes, HexStr
from eth_utils import is_0x_prefixed
from pydantic import Field, computed_field, field_validator

from ethpm_types.abi import (
    ABI,
    ConstructorABI,
    ErrorABI,
    EventABI,
    FallbackABI,
    MethodABI,
    ReceiveABI,
    StructABI,
)
from ethpm_types.ast import ASTNode
from ethpm_types.base import BaseModel
from ethpm_types.sourcemap import PCMap, SourceMap
from ethpm_types.types import ContractName, SourceId

ABI_W_SELECTOR_T = Union[ConstructorABI, MethodABI, EventABI, StructABI, ErrorABI]
"""ABI types with selectors"""

ABILIST_T = TypeVar("ABILIST_T", bound=Union[MethodABI, EventABI, StructABI, ErrorABI])
"""The generic used for the ABIList class. Only for type-checking."""

ABI_SINGLETON_T = TypeVar("ABI_SINGLETON_T", bound=Union[FallbackABI, ConstructorABI, ReceiveABI])
"""
The generic used for discovering the unique ABIs from the list.
Only for type-checking.
"""


# TODO link references & link values are for solidity, not used with Vyper
# Offsets are for dynamic links, e.g. EIP1167 proxy forwarder
class LinkDependency(BaseModel):
    offsets: List[int]
    """
    The locations within the corresponding bytecode where the value for this
    link value was written. These locations are 0-indexed from the beginning
    of the bytes representation of the corresponding bytecode.
    """

    type: str
    """
    The value type for determining what is encoded when linking the corresponding
    bytecode.
    """

    value: str
    """
    The value which should be written when linking the corresponding bytecode.
    """


class LinkReference(BaseModel):
    offsets: List[int]
    """
    An array of integers, corresponding to each of the start positions
    where the link reference appears in the bytecode. Locations are 0-indexed
    from the beginning of the bytes representation of the corresponding bytecode.
    This field is invalid if it references a position that is beyond the end of
    the bytecode.
    """

    length: int
    """
    The length in bytes of the link reference.
    This field is invalid if the end of the defined link reference exceeds the
    end of the bytecode.
    """

    name: Optional[str] = None
    """
    A valid identifier for the reference.
    Any link references which should be linked with the same link value should
    be given the same name.
    """


class Bytecode(BaseModel):
    bytecode: Optional[HexStr] = None
    """
    A string containing the 0x prefixed hexadecimal representation of the bytecode.
    """

    link_references: Optional[List[LinkReference]] = Field(None, alias="linkReferences")
    """
    The locations in the corresponding bytecode which require linking.
    """

    link_dependencies: Optional[List[LinkDependency]] = Field(None, alias="linkDependencies")
    """
    The link values that have been used to link the corresponding bytecode.
    """

    def __repr__(self) -> str:
        self_str = super().__repr__()

        # Truncate bytecode for display
        if self.bytecode and len(self.bytecode) > 10:
            self_str = self_str.replace(
                self.bytecode, self.bytecode[:5] + "..." + self.bytecode[-3:]
            )

        return self_str

    def to_bytes(self) -> Optional[HexBytes]:
        # TODO: Resolve links to produce dynamically linked bytecode
        return HexBytes(self.bytecode) if self.bytecode else None


class ContractInstance(BaseModel):
    contract_type: str = Field(..., alias="contractType")
    """
    Any of the contract type names included in this Package
    or any of the contract type names found in any of the package dependencies
    from the ``buildDependencies`` section of the Package Manifest.
    """

    address: Address
    """The contract address."""

    transaction: Optional[HashStr32] = None
    """The transaction hash from which the contract was created."""

    block: Optional[HashStr32] = None
    """
    The block hash in which this the transaction which created this
    contract instance was mined.
    """

    runtime_bytecode: Optional[Bytecode] = Field(None, alias="runtimeBytecode")
    """
    The runtime portion of bytecode for this Contract Instance.
    When present, the value from this field supersedes the ``runtimeBytecode``
    from the :class:`~ethpm_types.contract_type.ContractType` for this
    ``ContractInstance``.
    """


class ABIList(List[ABILIST_T]):
    """
    Adds selection by name, selector and keccak(selector).
    """

    def __init__(
        self,
        iterable: Optional[Iterable[ABILIST_T]] = None,
        *,
        selector_id_size: int = 32,
        selector_hash_fn: Optional[Callable[[str], bytes]] = None,
    ):
        self._selector_id_size = selector_id_size
        self._selector_hash_fn = selector_hash_fn
        super().__init__(iterable or ())

    @singledispatchmethod
    def __getitem__(self, selector):
        raise NotImplementedError(f"Cannot use {type(selector)} as a selector.")

    @__getitem__.register
    def __getitem_int(self, selector: int):
        return super().__getitem__(selector)

    @__getitem__.register
    def __getitem_slice(self, selector: slice):
        return super().__getitem__(selector)

    @__getitem__.register
    def __getitem_str(self, selector: str):
        try:
            if "(" in selector:
                # String-style selector e.g. `method(arg0)`.
                return next(abi for abi in self if abi.selector == selector)

            elif is_0x_prefixed(selector):
                # Hashed bytes selector, but as a hex str.
                return self.__getitem__(HexBytes(selector))

            # Search by name (could be ambiguous()
            return next(abi for abi in self if abi.name == selector)

        except StopIteration:
            raise KeyError(selector)

    @__getitem__.register
    def __getitem_bytes(self, selector: bytes):
        try:
            if self._selector_hash_fn:
                return next(
                    abi
                    for abi in self
                    if self._selector_hash_fn(abi.selector)[: self._selector_id_size]
                    == selector[: self._selector_id_size]
                )

            else:
                raise KeyError(selector)

        except StopIteration:
            raise KeyError(selector)

    @__getitem__.register
    def __getitem_method_abi(self, selector: MethodABI):
        return self.__getitem__(selector.selector)

    @__getitem__.register
    def __getitem_event_abi(self, selector: EventABI):
        return self.__getitem__(selector.selector)

    @singledispatchmethod
    def __contains__(self, selector):
        raise NotImplementedError(f"Cannot use {type(selector)} as a selector.")

    @__contains__.register
    def __contains_str(self, selector: str) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_bytes(self, selector: bytes) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_method_abi(self, selector: MethodABI) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_event_abi(self, selector: EventABI) -> bool:
        return self._contains(selector)

    def _contains(self, selector: Union[str, bytes, MethodABI, EventABI]) -> bool:
        try:
            _ = self[selector]
            return True
        except (KeyError, IndexError):
            return False


class ContractType(BaseModel):
    """
    A serializable type representing the type of a contract.
    For example, if you define your contract as ``contract MyContract`` (in Solidity),
    then ``MyContract`` would be the type.
    """

    name: Optional[ContractName] = Field(None, alias="contractName")
    """
    The name of the contract type. The field is optional if ``ContractAlias``
    is the same as ``ContractName``.
    """

    source_id: Optional[SourceId] = Field(None, alias="sourceId")
    """
    The global source identifier for the source file from which this contract type was generated.
    """

    deployment_bytecode: Optional[Bytecode] = Field(None, alias="deploymentBytecode")
    """The bytecode for the ContractType."""

    runtime_bytecode: Optional[Bytecode] = Field(None, alias="runtimeBytecode")
    """The unlinked 0x-prefixed runtime portion of bytecode for this ContractType."""

    abi: List[ABI] = []
    """The application binary interface to the contract."""

    sourcemap: Optional[SourceMap] = None
    """
    The range of the source code that is represented by the respective node in the AST.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    pcmap: Optional[PCMap] = None
    """
    The program counter map representing which lines in the source code account for which
    instructions in the bytecode.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    dev_messages: Optional[Dict[int, str]] = None
    """
    A map of dev-message comments in the source contract by their starting line number.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    ast: Optional[ASTNode] = None
    """
    The contract's root abstract syntax tree node.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    userdoc: Optional[dict] = None
    devdoc: Optional[dict] = None

    def __repr__(self) -> str:
        repr_id = self.__class__.__name__
        if name := self.name:
            repr_id = f"{repr_id} {name}"

        return f"<{repr_id}>"

    def __eq__(self, other) -> bool:
        if not isinstance(other, ContractType):
            return NotImplemented

        return (
            other.name == self.name
            and other.abi == self.abi
            and self.runtime_bytecode == other.runtime_bytecode
            and self.deployment_bytecode == other.deployment_bytecode
        )

    def get_runtime_bytecode(self) -> Optional[HexBytes]:
        if bytecode := self.runtime_bytecode:
            return bytecode.to_bytes()

        return None

    def get_deployment_bytecode(self) -> Optional[HexBytes]:
        if bytecode := self.deployment_bytecode:
            return bytecode.to_bytes()

        return None

    @property
    def selector_identifiers(self) -> Dict[str, str]:
        """
        Returns a mapping of the full suite of signatures to selectors/topics/IDs for this
        contract.
        """
        return {atype.selector: sig for atype, sig in self._abi_identifiers}

    @property
    def identifier_lookup(self) -> Dict[str, ABI_W_SELECTOR_T]:
        """
        Returns a mapping of the full suite of selectors/topics/IDs of this contract to human
        readable signature
        """
        return {sig: atype for atype, sig in self._abi_identifiers if sig is not None}

    @computed_field(alias="methodIdentifiers")  # type: ignore
    @cached_property
    def method_identifiers(self) -> Dict[str, str]:
        return {
            atype.selector: sig for atype, sig in self._abi_identifiers if atype.type == "function"
        }

    @field_validator("deployment_bytecode", "runtime_bytecode", mode="before")
    @classmethod
    def validate_bytecode(cls, value):
        if not value:
            return {}

        elif isinstance(value, dict):
            rest_attributes = value
            code = value["bytecode"]

        elif isinstance(value, Bytecode):
            # Already validated
            return value

        else:
            rest_attributes = {}
            code = value

        code_bytes = code if isinstance(code, bytes) else HexBytes(code)
        return {**rest_attributes, "bytecode": code_bytes.hex()}

    @property
    def constructor(self) -> ConstructorABI:
        """
        The constructor of the contract, if it has one. For example,
        your smart-contract (in Solidity) may define a ``constructor() public {}``.
        This property contains information about the parameters needed to initialize
        a contract.
        """

        # Use default constructor (no args) when no defined.
        return self._get_first_instance(ConstructorABI) or ConstructorABI(type="constructor")

    @property
    def fallback(self) -> Optional[FallbackABI]:
        """
        The fallback method of the contract, if it has one. A fallback method
        is external, has no name, arguments, or return value, and gets invoked
        when the user attempts to call a method that does not exist.
        """
        return self._get_first_instance(FallbackABI)

    @property
    def receive(self) -> Optional[ReceiveABI]:
        """
        The ``receive()`` method of the contract, if it has one. A contract may
        have 0-1 ``receive()`` methods defined. It gets executed when calling
        the contract with empty calldata. The method is not allowed any arguments
        and cannot return anything.
        """
        return self._get_first_instance(ReceiveABI)

    @property
    def view_methods(self) -> ABIList[MethodABI]:
        """
        The call-methods (read-only method, non-payable methods) defined in a smart contract.

        Returns:
            List[:class:`~ethpm_types.abi.ABI`]
        """
        return self._get_abis(
            selector_id_size=4, filter_fn=lambda x: isinstance(x, MethodABI) and not x.is_stateful
        )

    @property
    def mutable_methods(self) -> ABIList[MethodABI]:
        """
        The transaction-methods (stateful or payable methods) defined in a smart contract.

        Returns:
            List[:class:`~ethpm_types.abi.ABI`]
        """
        return self._get_abis(
            selector_id_size=4, filter_fn=lambda x: isinstance(x, MethodABI) and x.is_stateful
        )

    @property
    def events(self) -> ABIList[EventABI]:
        """
        The events defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(filter_fn=lambda a: isinstance(a, EventABI))

    @property
    def errors(self) -> ABIList[ErrorABI]:
        """
        The errors defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(selector_id_size=4, filter_fn=lambda a: isinstance(a, ErrorABI))

    @property
    def methods(self) -> ABIList:
        """
        All methods defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(selector_id_size=4, filter_fn=lambda a: isinstance(a, MethodABI))

    @property
    def structs(self) -> ABIList:
        """
        All structs defined in this contract.

        Returns:
            class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(filter_fn=lambda a: isinstance(a, StructABI))

    @classmethod
    def _selector_hash_fn(cls, selector: str) -> bytes:
        # keccak is the default on most ecosystems, other ecosystems can subclass to override it
        from eth_utils import keccak

        return keccak(text=selector)

    def _get_abis(
        self,
        selector_id_size: int = 32,
        filter_fn: Optional[Callable[[ABI], bool]] = None,
    ):
        def noop(a: ABI) -> bool:
            return True

        filter_fn = filter_fn or noop
        method_abis = [abi for abi in self.abi if filter_fn(abi)]

        return ABIList(
            method_abis,
            selector_id_size=selector_id_size,
            selector_hash_fn=self._selector_hash_fn,
        )

    def _get_first_instance(self, _type: Type[ABI_SINGLETON_T]) -> Optional[ABI_SINGLETON_T]:
        for abi in self.abi:
            if not isinstance(abi, _type):
                continue

            return abi

        return None

    @cached_property
    def _abi_identifiers(self) -> List[Tuple[ABI_W_SELECTOR_T, str]]:
        def get_id(aitem: ABI_W_SELECTOR_T) -> str:
            if isinstance(aitem, MethodABI) or isinstance(aitem, ErrorABI):
                return HexBytes(self._selector_hash_fn(aitem.selector)[:4]).hex()
            else:
                return HexBytes(self._selector_hash_fn(aitem.selector)).hex()

        abis_with_selector = cast(
            List[ABI_W_SELECTOR_T], [x for x in self.abi if hasattr(x, "selector")]
        )
        return [(x, get_id(x)) for x in abis_with_selector]
