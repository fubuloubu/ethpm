from pathlib import Path
from typing import Optional

from eth_pydantic_types import Bip122Uri
from pydantic import Field, field_validator, model_validator
from pydantic_core import CoreSchema, PydanticCustomError
from pydantic_core.core_schema import str_schema, with_info_before_validator_function

from ethpm_types.base import BaseModel
from ethpm_types.contract_type import ContractInstance, ContractType
from ethpm_types.source import Compiler, Source
from ethpm_types.utils import AnyUrl

ALPHABET = set("abcdefghijklmnopqrstuvwxyz")
NUMBERS = set("0123456789")


def PackageNameError(name: str, message: str) -> PydanticCustomError:
    error_name = f"{PackageName.__name__}Error"
    return PydanticCustomError(error_name, message, {"name": name})


def validate_package_name(name: str, info) -> str:
    if not isinstance(name, str):
        # NOTE: Don't raise TypeError here.
        # Those no longer turn to ValidationError in Pydantic.
        raise PackageNameError(name, "`name` element must be a `str`")

    elif not (0 < len(name) < 256):
        raise PackageNameError(name, "Length must be between 1 and 255")

    elif name[0] not in ALPHABET:
        raise PackageNameError(name, "First character in name must be a-z")

    elif set(name) > ALPHABET.union(NUMBERS).union("-"):
        raise PackageNameError(name, "Characters in name must be one of a-z or 0-9 or '-'")

    return name


class PackageName(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, value, handler=None) -> CoreSchema:
        schema = with_info_before_validator_function(
            validate_package_name,
            str_schema(),
        )
        return schema

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema.update(
            format="binary",
            pattern="^[a-z][-a-z0-9]{0,254}$",
            examples=["my-token", "safe-math", "nft"],
        )
        return json_schema


class PackageMeta(BaseModel):
    """
    Important data that is not integral to installation
    but should be included when publishing.
    """

    authors: Optional[list[str]] = None
    """A list of human readable names for the authors of this package."""

    license: Optional[str] = None
    """
    The license associated with this package.
    This value should conform to the SPDX format.
    Packages should include this field.
    If a file Source Object defines its own license, that license takes
    precedence for that particular file over this package-scoped meta license.
    """

    description: Optional[str] = None
    """Additional detail that may be relevant for this package."""

    keywords: Optional[list[str]] = None
    """Relevant keywords related to this package."""

    links: Optional[dict[str, AnyUrl]] = None
    """
    URIs to relevant resources associated with this package.
    When possible, authors should use the following keys for the following common resources.
    """


class PackageManifest(BaseModel):
    """
    A data format describing a smart contract software package.
    `EIP-2678 <https://eips.ethereum.org/EIPS/eip-2678#ethpm-manifest-version>`__.
    """

    manifest: str = "ethpm/3"
    """The specification version that the project conforms to."""

    name: Optional[PackageName] = None  # type: ignore[valid-type]
    """A human-readable name for the package."""

    version: Optional[str] = None
    """The version of the release, which should be SemVer."""

    meta: Optional[PackageMeta] = None
    """
    Important data that is not integral to installation
    but should be included when publishing.
    **NOTE**: All published projects *should* include
    ``meta``.
    """

    sources: Optional[dict[str, Source]] = None
    """
    The sources field defines a source tree that should comprise the full source tree
    necessary to recompile the contracts contained in this release.
    """

    contract_types: Optional[dict[str, ContractType]] = Field(default=None, alias="contractTypes")
    """
    :class:`~ethpm_types.contract_type.ContractType` objects that have been included
    in this release.

      * Should only include types that can be found in the sources.
      * Should not include types from dependencies.
      * Should not include abstracts.
    """

    compilers: Optional[list[Compiler]] = None
    """
    Information about the compilers and their settings that have been
    used to generate the various contractTypes included in this release.
    """

    deployments: Optional[dict[Bip122Uri, dict[str, ContractInstance]]] = None
    """
    Information for the chains on which this release has
    :class:`~ethpm_types.contract_type.ContractInstance` references as well as the
    :class:`~ethpm_types.contract_type.ContractType` definitions and other deployment
    details for those deployed contract instances. The set of chains defined by the BIP122
    URI keys for this object must be unique. There cannot be two different URI keys in a
    deployments field representing the same blockchain. The value of the URIs is a dictionary
    mapping the contract instance names to the instance themselves. The contract instance names
    must be unique across all other contract instances for the given chain.
    """

    dependencies: Optional[dict[PackageName, AnyUrl]] = Field(  # type: ignore[valid-type]
        default=None, alias="buildDependencies"
    )
    """
    A mapping of EthPM packages that this project depends on.
    The values must be content-addressable URIs that conforms to the same
    manifest version as ``manifest``.
    """

    @model_validator(mode="after")
    def check_valid_manifest_version(cls, values):
        # NOTE: We only support v3 (EIP-2678) of the ethPM spec currently
        if values.manifest != "ethpm/3":
            raise PydanticCustomError(
                f"{PackageManifest.__name__}Error",
                "Only ethPM V3 (EIP-2678) supported.",
                {"version": values.manifest},
            )

        return values

    @model_validator(mode="before")
    def check_both_version_and_name(cls, values):
        if ("name" in values or "version" in values) and (
            "name" not in values or "version" not in values
        ):
            raise PydanticCustomError(
                f"{PackageManifest.__name__}Error",
                "Both `name` and `version` must be present if either is specified.",
            )

        return values

    @model_validator(mode="before")
    def check_contract_source_ids(cls, values):
        sources = values.get("sources", {}) or {}

        sources_fixed = {}
        for src_id, source_obj in sources.items():
            if isinstance(source_obj, str):
                # Backwards compat: Allow str-based sources.
                sources_fixed[src_id] = Source.model_validate({"content": source_obj})
            elif isinstance(source_obj, dict):
                sources_fixed[src_id] = Source.model_validate(source_obj)
            else:
                sources_fixed[src_id] = source_obj

        contract_types = values.get("contract_types", {}) or {}
        for alias in contract_types:
            source_id = values["contract_types"][alias].source_id
            if source_id and (source_id not in sources_fixed):
                raise PydanticCustomError(
                    f"{PackageManifest.__name__}Error",
                    f"'{source_id}' missing from `sources`.",
                    {"source_id": source_id},
                )

        # NOTE: This MUST return a new dictionary here or else we end up
        #  modifying the original model dict (passed to `model_validate()`).
        return {**values, "sources": sources_fixed or None}

    @field_validator("contract_types")
    @classmethod
    def add_name_to_contract_types(cls, values):
        aliases = list((values or {}).keys())
        # NOTE: Must manually inject names to types here
        for alias in aliases:
            if not values[alias]:
                values[alias].name = alias
            # else: contractName != contractAlias (key used in `contractTypes` dict)

        return values

    def __getattr__(self, attr_name: str):
        try:
            # Check if regular attribute.
            return self.__getattribute__(attr_name)
        except AttributeError:
            # Check if contract type name.
            if contract_type := self.get_contract_type(attr_name):
                return contract_type

        # NOTE: **must** raise `AttributeError` or return here, or else Python breaks
        raise AttributeError(
            f"{self.__class__.__name__} has no attribute or contract type named '{attr_name}'."
        )

    def get_contract_type(self, name: str) -> Optional[ContractType]:
        """
        Get a contract type by name, if it exists. Else, returns ``None``.

        Args: name (str): The name of the contract type.

        Returns:
          Optional[:class:`~ethpm_types.contract_type.ContractType`]
        """
        return (
            self.contract_types[name]
            if self.contract_types and name in self.contract_types
            else None
        )

    def unpack_sources(self, destination: Path):
        """
        Unpack a package manifest's content sources into
        the given directory.

        Args:
            destination (pathlib.Path): The destination where to unpack.
        """
        if not (sources := (self.sources or None)):
            return

        elif not destination.parent.is_dir():
            raise ValueError("Destination parent path does not exist.")

        # It is okay if the destination does not exist yet.
        destination.mkdir(exist_ok=True)

        for source_id, source_obj in sources.items():
            content = str(source_obj.content or "")
            source_path = (destination / source_id).absolute()

            # Create nested directories as needed.
            source_path.parent.mkdir(parents=True, exist_ok=True)

            source_path.write_text(content, encoding="utf8")

    def get_compiler(self, name: str, version: str) -> Optional[Compiler]:
        """
        Get a compiler by name and version.

        Args:
            name (str): The name of the compiler, such as ``"vyper"``.
            version (str): The version of the compiler.

        Returns:
            Optional[`~ethpm_types.source.Compiler`]
        """
        for compiler in self.compilers or []:
            if compiler.name == name.lower() and compiler.version == version:
                return compiler

        return None

    def get_contract_compiler(self, contract_type_name: str) -> Optional[Compiler]:
        """
        Get the compiler used to compile the contract type, if it exists.

        Args:
            contract_type_name (str): The name of the compiled contract.

        Returns:
            Optional[`~ethpm_types.source.Compiler`]
        """
        for compiler in self.compilers or []:
            if contract_type_name in (compiler.contractTypes or []):
                return compiler

        return None

    def add_compilers(self, *compilers: Compiler):
        """
        Update compilers in the manifest. This method appends any
        given compiler with a a different name, version, and settings
        combination.

        Args:
            compilers (List[`~ethpm_types.source.Compiler]`): A list of
              compilers.
        """

        start = self.compilers or []
        start.extend([c for c in compilers if c not in start])
        self.compilers = start
