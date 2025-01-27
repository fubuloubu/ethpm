from ethpm_types.base import BaseModel
from ethpm_types.source import Source
from pydantic import Field, field_validator, ConfigDict


class OutputSelection(BaseModel):
    """
    The ``outputSelection`` model of Solidity' standard input JSON.
    """


class Settings(BaseModel):
    """
    A model representing the settings-key in Solidity's defined
    standard input JSON model.
    """

    output_selection: OutputSelection = Field(default={}, alias="outputSelection")
    """
    Compiler output settings per source file.
    """

    model_config = ConfigDict(extra="allow")
    """
    Expected extra items. Most settings are compiler-specific."
    """


class StandardInput(BaseModel):
    """
    A model representing the standard-input JSON ``solc`` expects.
    """

    language: str
    """
    The compiler language name, e.g. ``"Solidity"``.
    """

    sources: dict[str, Source] = {}
    """
    Each source needed to compile, even if not included in ``outputSelection``.
    """

    settings: Settings = Settings.model_construct({})
    """
    Compiler settings, such as ``evm_version``.
    """

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value):
        return f"{value}".capitalize()
