import json

from pydantic import BaseModel as _BaseModel


def _set_dict_defaults(**kwargs) -> dict:
    # NOTE: We do this to accommodate the aliases needed for EIP-2678 compatibility
    if "by_alias" not in kwargs:
        kwargs["by_alias"] = True

    # EIP-2678: skip empty fields (at least by default)
    if "exclude_none" not in kwargs:
        kwargs["exclude_none"] = True

    return kwargs


def _to_json_str(model, *args, **kwargs) -> str:
    # NOTE: When serializing to IPFS, the canonical representation must be repeatable

    # EIP-2678: minified representation (at least by default)
    separators = kwargs.pop("separators", (",", ":"))

    # EIP-2678: sort keys (at least by default)
    sort_keys = kwargs.pop("sort_keys", True)

    # TODO: Find a better way to handle sorting the keys and custom separators.
    #    or open an issue(s) with pydantic. `super().model_dump_json()` does not
    #    support `sort_keys` or `separators`.
    kwargs["by_alias"] = True
    kwargs["mode"] = "json"
    result_dict = model.model_dump(*args, **kwargs)
    return json.dumps(result_dict, sort_keys=sort_keys, separators=separators)


class BaseModel(_BaseModel):
    def model_dump(self, *args, **kwargs) -> dict:
        kwargs = _set_dict_defaults(**kwargs)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs) -> str:
        return _to_json_str(self, *args, **kwargs)

    def dict(self, *args, **kwargs) -> dict:
        kwargs = _set_dict_defaults(**kwargs)
        return super().dict(*args, **kwargs)

    def json(self, *args, **kwargs) -> str:
        return _to_json_str(self, *args, **kwargs)
