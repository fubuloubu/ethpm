from typing import TYPE_CHECKING, Literal, Optional, Union

from pydantic import ConfigDict, Field

from ethpm_types.base import BaseModel
from ethpm_types.utils import parse_signature

if TYPE_CHECKING:
    from typing_extensions import Self


class ABIType(BaseModel):
    name: Optional[str] = None
    """
    The name attached to the type, such as the input name of
    a function.
    """

    type: Union[str, "ABIType"]
    """
    The value-type, such as ``address`` or ``address[]``.
    """

    components: Optional[list["ABIType"]] = None
    """
    A field of sub-types that makes up this type.
    Tuples and structs tend to have this field.
    """

    internal_type: Optional[str] = Field(default=None, alias="internalType")
    """
    Another name for the type. Sometimes, compilers are able to populate
    this field with the struct or enum name.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    @property
    def canonical_type(self) -> str:
        """
        The low-level type recognized by the virtual machine.
        For example, a tuple is converted to comma-separated string
        of its components.
        """

        if "tuple" in self.type and self.components:  # NOTE: 2nd condition just to satisfy mypy
            value = f"({','.join(m.canonical_type for m in self.components)})"
            if "[" in self.type:
                value += f"[{str(self.type).split('[')[-1]}"

            return value

        elif isinstance(self.type, str):
            return self.type

        else:
            # Recursively discover the canonical type
            return self.type.canonical_type

    @property
    def signature(self) -> str:
        """
        If the type has name, returns ``"<canonical_type> <name>"``.
        Else, returns ``"<canonical_type>"``.
        """

        return f"{self.canonical_type} {self.name}" if self.name else self.canonical_type


class EventABIType(ABIType):
    """
    ABI types describing event ABIs defined in contracts.
    """

    indexed: bool = False
    """
    Whether you can search logs based on this ABI type.
    **NOTE**: Only event ABI types should have this field
    """

    @property
    def signature(self) -> str:
        """
        The event signature.
        Will include the canonical type as well as the
        the name if it has one. Also notes indexed types.
        """

        sig = self.canonical_type

        # For events (handles both None and False conditions)
        if self.indexed:
            sig += " indexed"
        if self.name:
            sig += f" {self.name}"

        return sig


class BaseABI(BaseModel): ...


class ConstructorABI(BaseABI):
    """
    An ABI describing a contract constructor.
    **NOTE**: The constructor ABI does not have a ``name`` property.
    """

    type: Literal["constructor"] = "constructor"
    """The value ``"constructor"``."""

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    inputs: list[ABIType] = []
    """
    Contract constructor arguments.
    """

    @property
    def is_payable(self) -> bool:
        """
        Returns ``True`` if the contract accepts currency upon deployment.
        """

        return self.stateMutability == "payable"

    @property
    def signature(self) -> str:
        """
        String representing the function signature, which includes the arg names and types,
        for display purposes only.
        """

        input_args = ", ".join(i.signature for i in self.inputs)
        return f"constructor({input_args})"

    @property
    def selector(self) -> str:
        """
        String representing the constructor selector.
        """

        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"constructor({input_names})"


class FallbackABI(BaseABI):
    """
    An ABI dedicated to receiving unknown method selectors.
    **NOTE**: The fallback ABI does not have a name property.
    """

    type: Literal["fallback"] = "fallback"
    """The value ``"fallback"``."""

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    @property
    def is_payable(self) -> bool:
        """
        Returns ``True`` if the fallback accepts currency.
        """

        return self.stateMutability == "payable"

    @property
    def signature(self) -> str:
        """
        String representing the function signature for display purposes only.
        """
        return "fallback()"


class ReceiveABI(BaseABI):
    """
    An ABI dedicated to receiving currency from transactions with unknown
    method selectors.
    **NOTE**: The receive ABI does not have name field.
    """

    type: Literal["receive"] = "receive"
    """The value ``"receive"``."""

    stateMutability: Literal["payable"]
    """The value ``"payable"``."""

    @property
    def is_payable(self) -> bool:
        """
        Always returns ``True`` as receive methods are intended
        to receive money.
        """

        return True

    @property
    def signature(self) -> str:
        """
        String representing the function signature for display purposes only.
        """
        return "receive()"


class MethodABI(BaseABI):
    """
    An ABI representing a method you can invoke from a contact.
    """

    type: Literal["function"] = "function"
    """The value ``"function"``."""

    name: str
    """The name of the method."""

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    inputs: list[ABIType] = []
    """
    Inputs to the method as :class:`~ethpm_types.abi.ABIType` objects.
    """

    outputs: list[ABIType] = []
    """
    What the method returns as :class:`~ethpm_types.abi.ABIType` objects.
    """

    @property
    def is_payable(self) -> bool:
        """
        Whether the method expects currency or not.
        """

        return self.stateMutability == "payable"

    @property
    def is_stateful(self) -> bool:
        """
        Whether the method alters the state of the blockchain
        (and likely requires a transaction).
        """

        return self.stateMutability not in ("view", "pure")

    @property
    def selector(self) -> str:
        """
        String representing the function selector, used to compute ``method_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the function signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        output_args = ""

        if self.outputs:
            output_args = " -> "
            if len(self.outputs) > 1:
                output_args += "(" + ", ".join(o.canonical_type for o in self.outputs) + ")"

            else:
                output_args += self.outputs[0].canonical_type

        return f"{self.name}({input_args}){output_args}"

    @classmethod
    def from_signature(cls, sig: str) -> "Self":
        """
        Create an MethodABI instance from a method signature.

        **NOTE**: Method return types and state mutability are not included in signatures.
                  Therefore, they will not necessarily be accurate in the resulting MethodABI
                  instance.
        """
        name, inputs, outputs = parse_signature(sig)
        input_abis = [ABIType(name=name, type=type_) for type_, _, name in inputs]
        output_abis = [ABIType(type=type_) for type_ in outputs]
        return cls(name=name, inputs=input_abis, outputs=output_abis)


class EventABI(BaseABI):
    """
    An ABI describing an event-type defined in a contract.
    """

    type: Literal["event"] = "event"
    """The value ``"event"``."""

    name: str
    """The name of the event."""

    inputs: list[EventABIType] = []
    """
    Event properties defined as :class:`~ethpm_types.abi.EventABIType` objects.
    """

    anonymous: bool = False
    """``True`` if the event has no name."""

    @property
    def selector(self) -> str:
        """
        String representing the event selector, used to compute ``event_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the event signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        return f"{self.name}({input_args})"

    @classmethod
    def from_signature(cls, sig: str) -> "Self":
        """Create an EventABI instance from an event signature."""
        name, inputs, _ = parse_signature(sig)
        input_abis = [
            EventABIType(name=name, indexed=(indexed == "indexed"), type=type_)
            for type_, indexed, name in inputs
        ]
        return cls(name=name, inputs=input_abis)


class ErrorABI(BaseABI):
    """
    An ABI describing an error-type defined in a contract.
    """

    type: Literal["error"] = "error"
    """The value ``"error"``."""

    name: str
    """The name of the error."""

    inputs: list[ABIType] = []
    """
    Inputs when raising the error defined as
    :class:`~ethpm_types.abi.ABIType` objects.
    """

    @property
    def selector(self) -> str:
        """
        String representing the event selector, used to compute ``event_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the event signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        return f"{self.name}({input_args})"


class StructABI(BaseABI):
    """
    An ABI describing a struct-type defined in a contract.
    """

    type: Literal["struct"] = "struct"
    """The value ``"struct"``."""

    name: str
    """The name of the struct."""

    members: list[ABIType]
    """The properties that compose the struct."""

    model_config = ConfigDict(extra="allow")

    @property
    def selector(self) -> str:
        """
        String representing the struct selector.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.members)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the struct signature, which includes the member names and types,
        and offsets (if any) for display purposes only.
        """
        members_str = ", ".join(m.signature for m in self.members)
        return f"{self.name}({members_str})"


class UnprocessedABI(BaseABI):
    """
    An ABI representing an unknown entity.
    This is useful for supporting custom compiler types,
    such as types defined in L2 ecosystems but are not
    in Ethereum.
    """

    type: str
    """The type name as a string."""

    @property
    def signature(self) -> str:
        """
        The full ABI JSON output, as we are unable to know
        a more useful-looking signature.
        """

        return self.model_dump_json()


ABI = Union[
    ConstructorABI,
    FallbackABI,
    ReceiveABI,
    MethodABI,
    EventABI,
    ErrorABI,
    StructABI,
    UnprocessedABI,
]
