import collections.abc
from copy import deepcopy
from pathlib import Path
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Iterable,
    List,
    Mapping,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    Optional,
)
import inspect
import logging

import copy
from itertools import chain
import json
import logging
import os
import zlib
from collections import OrderedDict
from collections.abc import MutableMapping
from os import PathLike
from typing import Any, Dict, List, Union, Optional, TypeVar, Iterable, Set
from wechaty_puppet import get_logger


logger = get_logger("FromParam")


class ConfigurationError(Exception):
    pass


# _jsonnet doesn't work on Windows, so we have to use fakes.
try:
    from _jsonnet import evaluate_file, evaluate_snippet
except ImportError:

    def evaluate_file(filename: str, **_kwargs) -> str:
        logger.warning(
            f"error loading _jsonnet (this is expected on Windows), treating {filename} as plain json"
        )
        with open(filename, "r") as evaluation_file:
            return evaluation_file.read()

    def evaluate_snippet(_filename: str, expr: str, **_kwargs) -> str:
        logger.warning(
            "error loading _jsonnet (this is expected on Windows), treating snippet as plain json"
        )
        return expr


def infer_and_cast(value: Any):
    """
    In some cases we'll be feeding params dicts to functions we don't own;
    for example, PyTorch optimizers. In that case we can't use `pop_int`
    or similar to force casts (which means you can't specify `int` parameters
    using environment variables). This function takes something that looks JSON-like
    and recursively casts things that look like (bool, int, float) to (bool, int, float).
    """

    if isinstance(value, (int, float, bool)):
        # Already one of our desired types, so leave as is.
        return value
    elif isinstance(value, list):
        # Recursively call on each list element.
        return [infer_and_cast(item) for item in value]
    elif isinstance(value, dict):
        # Recursively call on each dict value.
        return {key: infer_and_cast(item) for key, item in value.items()}
    elif isinstance(value, str):
        # If it looks like a bool, make it a bool.
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        else:
            # See if it could be an int.
            try:
                return int(value)
            except ValueError:
                pass
            # See if it could be a float.
            try:
                return float(value)
            except ValueError:
                # Just return it as a string.
                return value
    else:
        raise ValueError(f"cannot infer type of {value}")


def _is_encodable(value: str) -> bool:
    """
    We need to filter out environment variables that can't
    be unicode-encoded to avoid a "surrogates not allowed"
    error in jsonnet.
    """
    # Idiomatically you'd like to not check the != b""
    # but mypy doesn't like that.
    return (value == "") or (value.encode("utf-8", "ignore") != b"")


def _environment_variables() -> Dict[str, str]:
    """
    Wraps `os.environ` to filter out non-encodable values.
    """
    return {key: value for key, value in os.environ.items() if _is_encodable(value)}


T = TypeVar("T", dict, list)


def with_overrides(original: T, overrides_dict: Dict[str, Any], prefix: str = "") -> T:
    merged: T
    keys: Union[Iterable[str], Iterable[int]]
    if isinstance(original, list):
        merged = [None] * len(original)
        keys = range(len(original))
    elif isinstance(original, dict):
        merged = {}
        keys = chain(
            original.keys(), (k for k in overrides_dict if "." not in k and k not in original)
        )
    else:
        if prefix:
            raise ValueError(
                f"overrides for '{prefix[:-1]}.*' expected list or dict in original, "
                f"found {type(original)} instead"
            )
        else:
            raise ValueError(f"expected list or dict, found {type(original)} instead")

    used_override_keys: Set[str] = set()
    for key in keys:
        if str(key) in overrides_dict:
            merged[key] = copy.deepcopy(overrides_dict[str(key)])
            used_override_keys.add(str(key))
        else:
            overrides_subdict = {}
            for o_key in overrides_dict:
                if o_key.startswith(f"{key}."):
                    overrides_subdict[o_key[len(f"{key}.") :]] = overrides_dict[o_key]
                    used_override_keys.add(o_key)
            if overrides_subdict:
                merged[key] = with_overrides(
                    original[key], overrides_subdict, prefix=prefix + f"{key}."
                )
            else:
                merged[key] = copy.deepcopy(original[key])

    unused_override_keys = [prefix + key for key in set(overrides_dict.keys()) - used_override_keys]
    if unused_override_keys:
        raise ValueError(f"overrides dict contains unused keys: {unused_override_keys}")

    return merged


def parse_overrides(
    serialized_overrides: str, ext_vars: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if serialized_overrides:
        ext_vars = {**_environment_variables(), **(ext_vars or {})}

        return json.loads(evaluate_snippet("", serialized_overrides, ext_vars=ext_vars))
    else:
        return {}


def _is_dict_free(obj: Any) -> bool:
    """
    Returns False if obj is a dict, or if it's a list with an element that _has_dict.
    """
    if isinstance(obj, dict):
        return False
    elif isinstance(obj, list):
        return all(_is_dict_free(item) for item in obj)
    else:
        return True


class Params(MutableMapping):
    """
    Represents a parameter dictionary with a history, and contains other functionality around
    parameter passing and validation for AllenNLP.

    There are currently two benefits of a `Params` object over a plain dictionary for parameter
    passing:

    1. We handle a few kinds of parameter validation, including making sure that parameters
       representing discrete choices actually have acceptable values, and making sure no extra
       parameters are passed.
    2. We log all parameter reads, including default values.  This gives a more complete
       specification of the actual parameters used than is given in a JSON file, because
       those may not specify what default values were used, whereas this will log them.

    !!! Consumption
        The convention for using a `Params` object in AllenNLP is that you will consume the parameters
        as you read them, so that there are none left when you've read everything you expect.  This
        lets us easily validate that you didn't pass in any `extra` parameters, just by making sure
        that the parameter dictionary is empty.  You should do this when you're done handling
        parameters, by calling `Params.assert_empty`.
    """

    # This allows us to check for the presence of "None" as a default argument,
    # which we require because we make a distinction between passing a value of "None"
    # and passing no value to the default parameter of "pop".
    DEFAULT = object()

    def __init__(self, params: Dict[str, Any], history: str = "") -> None:
        self.params = _replace_none(params)
        self.history = history

    def pop(self, key: str, default: Any = DEFAULT, keep_as_dict: bool = False) -> Any:

        """
        Performs the functionality associated with dict.pop(key), along with checking for
        returned dictionaries, replacing them with Param objects with an updated history
        (unless keep_as_dict is True, in which case we leave them as dictionaries).

        If `key` is not present in the dictionary, and no default was specified, we raise a
        `ConfigurationError`, instead of the typical `KeyError`.
        """
        if default is self.DEFAULT:
            try:
                value = self.params.pop(key)
            except KeyError:
                msg = f'key "{key}" is required'
                if self.history:
                    msg += f' at location "{self.history}"'
                raise ConfigurationError(msg)
        else:
            value = self.params.pop(key, default)

        if keep_as_dict or _is_dict_free(value):
            logger.info(f"{self.history}{key} = {value}")
            return value
        else:
            return self._check_is_dict(key, value)

    def pop_int(self, key: str, default: Any = DEFAULT) -> Optional[int]:
        """
        Performs a pop and coerces to an int.
        """
        value = self.pop(key, default)
        if value is None:
            return None
        else:
            return int(value)

    def pop_float(self, key: str, default: Any = DEFAULT) -> Optional[float]:
        """
        Performs a pop and coerces to a float.
        """
        value = self.pop(key, default)
        if value is None:
            return None
        else:
            return float(value)

    def pop_bool(self, key: str, default: Any = DEFAULT) -> Optional[bool]:
        """
        Performs a pop and coerces to a bool.
        """
        value = self.pop(key, default)
        if value is None:
            return None
        elif isinstance(value, bool):
            return value
        elif value == "true":
            return True
        elif value == "false":
            return False
        else:
            raise ValueError("Cannot convert variable to bool: " + value)

    def get(self, key: str, default: Any = DEFAULT):
        """
        Performs the functionality associated with dict.get(key) but also checks for returned
        dicts and returns a Params object in their place with an updated history.
        """
        default = None if default is self.DEFAULT else default
        value = self.params.get(key, default)
        return self._check_is_dict(key, value)

    def pop_choice(
        self,
        key: str,
        choices: List[Any],
        default_to_first_choice: bool = False,
        allow_class_names: bool = True,
    ) -> Any:
        """
        Gets the value of `key` in the `params` dictionary, ensuring that the value is one of
        the given choices. Note that this `pops` the key from params, modifying the dictionary,
        consistent with how parameters are processed in this codebase.

        # Parameters

        key: `str`

            Key to get the value from in the param dictionary

        choices: `List[Any]`

            A list of valid options for values corresponding to `key`.  For example, if you're
            specifying the type of encoder to use for some part of your model, the choices might be
            the list of encoder classes we know about and can instantiate.  If the value we find in
            the param dictionary is not in `choices`, we raise a `ConfigurationError`, because
            the user specified an invalid value in their parameter file.

        default_to_first_choice: `bool`, optional (default = `False`)

            If this is `True`, we allow the `key` to not be present in the parameter
            dictionary.  If the key is not present, we will use the return as the value the first
            choice in the `choices` list.  If this is `False`, we raise a
            `ConfigurationError`, because specifying the `key` is required (e.g., you `have` to
            specify your model class when running an experiment, but you can feel free to use
            default settings for encoders if you want).

        allow_class_names: `bool`, optional (default = `True`)

            If this is `True`, then we allow unknown choices that look like fully-qualified class names.
            This is to allow e.g. specifying a model type as my_library.my_model.MyModel
            and importing it on the fly. Our check for "looks like" is extremely lenient
            and consists of checking that the value contains a '.'.
        """
        default = choices[0] if default_to_first_choice else self.DEFAULT
        value = self.pop(key, default)
        ok_because_class_name = allow_class_names and "." in value
        if value not in choices and not ok_because_class_name:
            key_str = self.history + key
            message = (
                f"{value} not in acceptable choices for {key_str}: {choices}. "
                "You should either use the --include-package flag to make sure the correct module "
                "is loaded, or use a fully qualified class name in your config file like "
                """{"model": "my_module.models.MyModel"} to have it imported automatically."""
            )
            raise ConfigurationError(message)
        return value

    def as_dict(self, quiet: bool = False, infer_type_and_cast: bool = False):
        """
        Sometimes we need to just represent the parameters as a dict, for instance when we pass
        them to PyTorch code.

        # Parameters

        quiet: `bool`, optional (default = `False`)

            Whether to log the parameters before returning them as a dict.

        infer_type_and_cast: `bool`, optional (default = `False`)

            If True, we infer types and cast (e.g. things that look like floats to floats).
        """
        if infer_type_and_cast:
            params_as_dict = infer_and_cast(self.params)
        else:
            params_as_dict = self.params

        if quiet:
            return params_as_dict

        def log_recursively(parameters, history):
            for key, value in parameters.items():
                if isinstance(value, dict):
                    new_local_history = history + key + "."
                    log_recursively(value, new_local_history)
                else:
                    logger.info(f"{history}{key} = {value}")

        log_recursively(self.params, self.history)
        return params_as_dict

    def as_flat_dict(self) -> Dict[str, Any]:
        """
        Returns the parameters of a flat dictionary from keys to values.
        Nested structure is collapsed with periods.
        """
        flat_params = {}

        def recurse(parameters, path):
            for key, value in parameters.items():
                newpath = path + [key]
                if isinstance(value, dict):
                    recurse(value, newpath)
                else:
                    flat_params[".".join(newpath)] = value

        recurse(self.params, [])
        return flat_params

    def duplicate(self) -> "Params":
        """
        Uses `copy.deepcopy()` to create a duplicate (but fully distinct)
        copy of these Params.
        """
        return copy.deepcopy(self)

    def assert_empty(self, class_name: str):
        """
        Raises a `ConfigurationError` if `self.params` is not empty.  We take `class_name` as
        an argument so that the error message gives some idea of where an error happened, if there
        was one.  `class_name` should be the name of the `calling` class, the one that got extra
        parameters (if there are any).
        """
        if self.params:
            raise ConfigurationError(
                "Extra parameters passed to {}: {}".format(class_name, self.params)
            )

    def __getitem__(self, key):
        if key in self.params:
            return self._check_is_dict(key, self.params[key])
        else:
            raise KeyError(str(key))

    def __setitem__(self, key, value):
        self.params[key] = value

    def __delitem__(self, key):
        del self.params[key]

    def __iter__(self):
        return iter(self.params)

    def __len__(self):
        return len(self.params)

    def _check_is_dict(self, new_history, value):
        if isinstance(value, dict):
            new_history = self.history + new_history + "."
            return Params(value, history=new_history)
        if isinstance(value, list):
            value = [self._check_is_dict(f"{new_history}.{i}", v) for i, v in enumerate(value)]
        return value

    @classmethod
    def from_file(
        cls,
        params_file: Union[str, PathLike],
        params_overrides: Union[str, Dict[str, Any]] = "",
        ext_vars: dict = None,
    ) -> "Params":
        """
        Load a `Params` object from a configuration file.

        # Parameters

        params_file: `str`

            The path to the configuration file to load.

        params_overrides: `Union[str, Dict[str, Any]]`, optional (default = `""`)

            A dict of overrides that can be applied to final object.
            e.g. `{"model.embedding_dim": 10}` will change the value of "embedding_dim"
            within the "model" object of the config to 10. If you wanted to override the entire
            "model" object of the config, you could do `{"model": {"type": "other_type", ...}}`.

        ext_vars: `dict`, optional

            Our config files are Jsonnet, which allows specifying external variables
            for later substitution. Typically we substitute these using environment
            variables; however, you can also specify them here, in which case they
            take priority over environment variables.
            e.g. {"HOME_DIR": "/Users/allennlp/home"}
        """
        if ext_vars is None:
            ext_vars = {}

        # redirect to cache, if necessary
        params_file = cached_path(params_file)
        ext_vars = {**_environment_variables(), **ext_vars}

        file_dict = json.loads(evaluate_file(params_file, ext_vars=ext_vars))

        if isinstance(params_overrides, dict):
            params_overrides = json.dumps(params_overrides)
        overrides_dict = parse_overrides(params_overrides, ext_vars=ext_vars)

        if overrides_dict:
            param_dict = with_overrides(file_dict, overrides_dict)
        else:
            param_dict = file_dict

        return cls(param_dict)

    def to_file(self, params_file: str, preference_orders: List[List[str]] = None) -> None:
        with open(params_file, "w") as handle:
            json.dump(self.as_ordered_dict(preference_orders), handle, indent=4)

    def as_ordered_dict(self, preference_orders: List[List[str]] = None) -> OrderedDict:
        """
        Returns Ordered Dict of Params from list of partial order preferences.

        # Parameters

        preference_orders: `List[List[str]]`, optional

            `preference_orders` is list of partial preference orders. ["A", "B", "C"] means
            "A" > "B" > "C". For multiple preference_orders first will be considered first.
            Keys not found, will have last but alphabetical preference. Default Preferences:
            `[["dataset_reader", "iterator", "model", "train_data_path", "validation_data_path",
            "test_data_path", "trainer", "vocabulary"], ["type"]]`
        """
        params_dict = self.as_dict(quiet=True)
        if not preference_orders:
            preference_orders = []
            preference_orders.append(
                [
                    "dataset_reader",
                    "iterator",
                    "model",
                    "train_data_path",
                    "validation_data_path",
                    "test_data_path",
                    "trainer",
                    "vocabulary",
                ]
            )
            preference_orders.append(["type"])

        def order_func(key):
            # Makes a tuple to use for ordering.  The tuple is an index into each of the `preference_orders`,
            # followed by the key itself.  This gives us integer sorting if you have a key in one of the
            # `preference_orders`, followed by alphabetical ordering if not.
            order_tuple = [
                order.index(key) if key in order else len(order) for order in preference_orders
            ]
            return order_tuple + [key]

        def order_dict(dictionary, order_func):
            # Recursively orders dictionary according to scoring order_func
            result = OrderedDict()
            for key, val in sorted(dictionary.items(), key=lambda item: order_func(item[0])):
                result[key] = order_dict(val, order_func) if isinstance(val, dict) else val
            return result

        return order_dict(params_dict, order_func)

    def get_hash(self) -> str:
        """
        Returns a hash code representing the current state of this `Params` object.  We don't
        want to implement `__hash__` because that has deeper python implications (and this is a
        mutable object), but this will give you a representation of the current state.
        We use `zlib.adler32` instead of Python's builtin `hash` because the random seed for the
        latter is reset on each new program invocation, as discussed here:
        https://stackoverflow.com/questions/27954892/deterministic-hashing-in-python-3.
        """
        dumped = json.dumps(self.params, sort_keys=True)
        hashed = zlib.adler32(dumped.encode())
        return str(hashed)

    def __str__(self) -> str:
        return f"{self.history}Params({self.params})"


def pop_choice(
    params: Dict[str, Any],
    key: str,
    choices: List[Any],
    default_to_first_choice: bool = False,
    history: str = "?.",
    allow_class_names: bool = True,
) -> Any:
    """
    Performs the same function as `Params.pop_choice`, but is required in order to deal with
    places that the Params object is not welcome, such as inside Keras layers.  See the docstring
    of that method for more detail on how this function works.

    This method adds a `history` parameter, in the off-chance that you know it, so that we can
    reproduce `Params.pop_choice` exactly.  We default to using "?." if you don't know the
    history, so you'll have to fix that in the log if you want to actually recover the logged
    parameters.
    """
    value = Params(params, history).pop_choice(
        key, choices, default_to_first_choice, allow_class_names=allow_class_names
    )
    return value


def _replace_none(params: Any) -> Any:
    if params == "None":
        return None
    elif isinstance(params, dict):
        for key, value in params.items():
            params[key] = _replace_none(value)
        return params
    elif isinstance(params, list):
        return [_replace_none(value) for value in params]
    return params


def remove_keys_from_params(params: Params, keys: List[str] = ["pretrained_file", "initializer"]):
    if isinstance(params, Params):  # The model could possibly be a string, for example.
        param_keys = params.keys()
        for key in keys:
            if key in param_keys:
                del params[key]
        for value in params.values():
            if isinstance(value, Params):
                remove_keys_from_params(value, keys)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="FromParams")

# If a function parameter has no default value specified,
# this is what the inspect module returns.
_NO_DEFAULT = inspect.Parameter.empty


def takes_arg(obj, arg: str) -> bool:
    """
    Checks whether the provided obj takes a certain arg.
    If it's a class, we're really checking whether its constructor does.
    If it's a function or method, we're checking the object itself.
    Otherwise, we raise an error.
    """
    if inspect.isclass(obj):
        signature = inspect.signature(obj.__init__)
    elif inspect.ismethod(obj) or inspect.isfunction(obj):
        signature = inspect.signature(obj)
    else:
        raise ConfigurationError(f"object {obj} is not callable")
    return arg in signature.parameters


def takes_kwargs(obj) -> bool:
    """
    Checks whether a provided object takes in any positional arguments.
    Similar to takes_arg, we do this for both the __init__ function of
    the class or a function / method
    Otherwise, we raise an error
    """
    if inspect.isclass(obj):
        signature = inspect.signature(obj.__init__)
    elif inspect.ismethod(obj) or inspect.isfunction(obj):
        signature = inspect.signature(obj)
    else:
        raise ConfigurationError(f"object {obj} is not callable")
    return any(
        p.kind == inspect.Parameter.VAR_KEYWORD  # type: ignore
        for p in signature.parameters.values()
    )


def can_construct_from_params(type_: Type) -> bool:
    if type_ in [str, int, float, bool]:
        return True
    origin = getattr(type_, "__origin__", None)
    if hasattr(type_, "from_params"):
        return True
    args = getattr(type_, "__args__")
    return all(can_construct_from_params(arg) for arg in args)

    return hasattr(type_, "from_params")


def is_base_registrable(cls) -> bool:
    """
    Checks whether this is a class that directly inherits from Registrable, or is a subclass of such
    a class.
    """
    from bot_maker.registrable import Registrable

    if not issubclass(cls, Registrable):
        return False
    method_resolution_order = inspect.getmro(cls)[1:]
    for base_class in method_resolution_order:
        if issubclass(base_class, Registrable) and base_class is not Registrable:
            return False
    return True


def remove_optional(annotation: type):
    """
    Optional[X] annotations are actually represented as Union[X, NoneType].
    For our purposes, the "Optional" part is not interesting, so here we
    throw it away.
    """
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    if origin == Union:
        return Union[tuple([arg for arg in args if arg != type(None)])]  # noqa: E721
    else:
        return annotation


def infer_constructor_params(
    cls: Type[T], constructor: Union[Callable[..., T], Callable[[T], None]] = None
) -> Dict[str, inspect.Parameter]:
    if constructor is None:
        constructor = cls.__init__
    return infer_method_params(cls, constructor)


infer_params = infer_constructor_params  # Legacy name


def infer_method_params(cls: Type[T], method: Callable) -> Dict[str, inspect.Parameter]:
    signature = inspect.signature(method)
    parameters = dict(signature.parameters)

    has_kwargs = False
    var_positional_key = None
    for param in parameters.values():
        if param.kind == param.VAR_KEYWORD:
            has_kwargs = True
        elif param.kind == param.VAR_POSITIONAL:
            var_positional_key = param.name

    if var_positional_key:
        del parameters[var_positional_key]

    if not has_kwargs:
        return parameters

    # "mro" is "method resolution order". The first one is the current class, the next is the
    # first superclass, and so on. We take the first superclass we find that inherits from
    # FromParams.
    super_class = None
    for super_class_candidate in cls.mro()[1:]:
        if issubclass(super_class_candidate, FromParams):
            super_class = super_class_candidate
            break
    if super_class:
        super_parameters = infer_params(super_class)
    else:
        super_parameters = {}

    return {**super_parameters, **parameters}  # Subclass parameters overwrite superclass ones


def create_kwargs(
    constructor: Callable[..., T], cls: Type[T], params: Params, **extras
) -> Dict[str, Any]:
    """
    Given some class, a `Params` object, and potentially other keyword arguments,
    create a dict of keyword args suitable for passing to the class's constructor.

    The function does this by finding the class's constructor, matching the constructor
    arguments to entries in the `params` object, and instantiating values for the parameters
    using the type annotation and possibly a from_params method.

    Any values that are provided in the `extras` will just be used as is.
    For instance, you might provide an existing `Vocabulary` this way.
    """
    # Get the signature of the constructor.

    kwargs: Dict[str, Any] = {}

    parameters = infer_params(cls, constructor)
    accepts_kwargs = False

    # Iterate over all the constructor parameters and their annotations.
    for param_name, param in parameters.items():
        # Skip "self". You're not *required* to call the first parameter "self",
        # so in theory this logic is fragile, but if you don't call the self parameter
        # "self" you kind of deserve what happens.
        if param_name == "self":
            continue

        if param.kind == param.VAR_KEYWORD:
            # When a class takes **kwargs, we do two things: first, we assume that the **kwargs are
            # getting passed to the super class, so we inspect super class constructors to get
            # allowed arguments (that happens in `infer_params` above).  Second, we store the fact
            # that the method allows extra keys; if we get extra parameters, instead of crashing,
            # we'll just pass them as-is to the constructor, and hope that you know what you're
            # doing.
            accepts_kwargs = True
            continue

        # If the annotation is a compound type like typing.Dict[str, int],
        # it will have an __origin__ field indicating `typing.Dict`
        # and an __args__ field indicating `(str, int)`. We capture both.
        annotation = remove_optional(param.annotation)

        explicitly_set = param_name in params
        constructed_arg = pop_and_construct_arg(
            cls.__name__, param_name, annotation, param.default, params, **extras
        )

        if explicitly_set or constructed_arg is not param.default:
            kwargs[param_name] = constructed_arg

    if accepts_kwargs:
        kwargs.update(params)
    else:
        params.assert_empty(cls.__name__)
    return kwargs


def create_extras(cls: Type[T], extras: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a dictionary of extra arguments, returns a dictionary of
    kwargs that actually are a part of the signature of the cls.from_params
    (or cls) method.
    """
    subextras: Dict[str, Any] = {}
    if hasattr(cls, "from_params"):
        from_params_method = cls.from_params  # type: ignore
    else:
        # In some rare cases, we get a registered subclass that does _not_ have a
        # from_params method (this happens with Activations, for instance, where we
        # register pytorch modules directly).  This is a bit of a hack to make those work,
        # instead of adding a `from_params` method for them somehow. Then the extras
        # in the class constructor are what we are looking for, to pass on.
        from_params_method = cls
    if takes_kwargs(from_params_method):
        # If annotation.params accepts **kwargs, we need to pass them all along.
        # For example, `BasicTextFieldEmbedder.from_params` requires a Vocabulary
        # object, but `TextFieldEmbedder.from_params` does not.
        subextras = extras
    else:
        # Otherwise, only supply the ones that are actual args; any additional ones
        # will cause a TypeError.
        subextras = {k: v for k, v in extras.items() if takes_arg(from_params_method, k)}
    return subextras


def pop_and_construct_arg(
    class_name: str, argument_name: str, annotation: Type, default: Any, params: Params, **extras
) -> Any:
    """
    Does the work of actually constructing an individual argument for
    [`create_kwargs`](./#create_kwargs).

    Here we're in the inner loop of iterating over the parameters to a particular constructor,
    trying to construct just one of them.  The information we get for that parameter is its name,
    its type annotation, and its default value; we also get the full set of `Params` for
    constructing the object (which we may mutate), and any `extras` that the constructor might
    need.

    We take the type annotation and default value here separately, instead of using an
    `inspect.Parameter` object directly, so that we can handle `Union` types using recursion on
    this method, trying the different annotation types in the union in turn.
    """
    return None

    # from allennlp.models.archival import load_archive  # import here to avoid circular imports

    # We used `argument_name` as the method argument to avoid conflicts with 'name' being a key in
    # `extras`, which isn't _that_ unlikely.  Now that we are inside the method, we can switch back
    # to using `name`.
    name = argument_name

    # Some constructors expect extra non-parameter items, e.g. vocab: Vocabulary.
    # We check the provided `extras` for these and just use them if they exist.
    if name in extras:
        if name not in params:
            return extras[name]
        else:
            logger.warning(
                f"Parameter {name} for class {class_name} was found in both "
                "**extras and in params. Using the specification found in params, "
                "but you probably put a key in a config file that you didn't need, "
                "and if it is different from what we get from **extras, you might "
                "get unexpected behavior."
            )
    # Next case is when argument should be loaded from pretrained archive.
    elif (
        name in params
        and isinstance(params.get(name), Params)
        and "_pretrained" in params.get(name)
    ):
        load_module_params = params.pop(name).pop("_pretrained")
        archive_file = load_module_params.pop("archive_file")
        module_path = load_module_params.pop("module_path")
        freeze = load_module_params.pop("freeze", True)
        archive = load_archive(archive_file)
        result = archive.extract_module(module_path, freeze)
        if not isinstance(result, annotation):
            raise ConfigurationError(
                f"The module from model at {archive_file} at path {module_path} "
                f"was expected of type {annotation} but is of type {type(result)}"
            )
        return result

    popped_params = params.pop(name, default) if default != _NO_DEFAULT else params.pop(name)
    if popped_params is None:
        return None

    return construct_arg(class_name, name, popped_params, annotation, default, **extras)


def construct_arg(
    class_name: str,
    argument_name: str,
    popped_params: Params,
    annotation: Type,
    default: Any,
    **extras,
) -> Any:
    """
    The first two parameters here are only used for logging if we encounter an error.
    """
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", [])

    # The parameter is optional if its default value is not the "no default" sentinel.
    optional = default != _NO_DEFAULT

    if hasattr(annotation, "from_params"):
        if popped_params is default:
            return default
        elif popped_params is not None:
            # Our params have an entry for this, so we use that.

            subextras = create_extras(annotation, extras)

            # In some cases we allow a string instead of a param dict, so
            # we need to handle that case separately.
            if isinstance(popped_params, str):
                popped_params = Params({"type": popped_params})
            elif isinstance(popped_params, dict):
                popped_params = Params(popped_params)
            result = annotation.from_params(params=popped_params, **subextras)

            return result
        elif not optional:
            # Not optional and not supplied, that's an error!
            raise ConfigurationError(f"expected key {argument_name} for {class_name}")
        else:
            return default

    # If the parameter type is a Python primitive, just pop it off
    # using the correct casting pop_xyz operation.
    elif annotation in {int, bool}:
        if type(popped_params) in {int, bool}:
            return annotation(popped_params)
        else:
            raise TypeError(f"Expected {argument_name} to be a {annotation.__name__}.")
    elif annotation == str:
        # Strings are special because we allow casting from Path to str.
        if type(popped_params) == str or isinstance(popped_params, Path):
            return str(popped_params)  # type: ignore
        else:
            raise TypeError(f"Expected {argument_name} to be a string.")
    elif annotation == float:
        # Floats are special because in Python, you can put an int wherever you can put a float.
        # https://mypy.readthedocs.io/en/stable/duck_type_compatibility.html
        if type(popped_params) in {int, float}:
            return popped_params
        else:
            raise TypeError(f"Expected {argument_name} to be numeric.")

    # This is special logic for handling types like Dict[str, TokenIndexer],
    # List[TokenIndexer], Tuple[TokenIndexer, Tokenizer], and Set[TokenIndexer],
    # which it creates by instantiating each value from_params and returning the resulting structure.
    elif (
        origin in {collections.abc.Mapping, Mapping, Dict, dict}
        and len(args) == 2
        and can_construct_from_params(args[-1])
    ):
        value_cls = annotation.__args__[-1]
        value_dict = {}
        if not isinstance(popped_params, Mapping):
            raise TypeError(
                f"Expected {argument_name} to be a Mapping (probably a dict or a Params object)."
            )

        for key, value_params in popped_params.items():
            value_dict[key] = construct_arg(
                str(value_cls),
                argument_name + "." + key,
                value_params,
                value_cls,
                _NO_DEFAULT,
                **extras,
            )

        return value_dict

    elif origin in (Tuple, tuple) and all(can_construct_from_params(arg) for arg in args):
        value_list = []

        for i, (value_cls, value_params) in enumerate(zip(annotation.__args__, popped_params)):
            value = construct_arg(
                str(value_cls),
                argument_name + f".{i}",
                value_params,
                value_cls,
                _NO_DEFAULT,
                **extras,
            )
            value_list.append(value)

        return tuple(value_list)

    elif origin in (Set, set) and len(args) == 1 and can_construct_from_params(args[0]):
        value_cls = annotation.__args__[0]

        value_set = set()

        for i, value_params in enumerate(popped_params):
            value = construct_arg(
                str(value_cls),
                argument_name + f".{i}",
                value_params,
                value_cls,
                _NO_DEFAULT,
                **extras,
            )
            value_set.add(value)

        return value_set

    elif origin == Union:
        # Storing this so we can recover it later if we need to.
        backup_params = deepcopy(popped_params)

        # We'll try each of the given types in the union sequentially, returning the first one that
        # succeeds.
        error_chain: Optional[Exception] = None
        for arg_annotation in args:
            try:
                return construct_arg(
                    str(arg_annotation),
                    argument_name,
                    popped_params,
                    arg_annotation,
                    default,
                    **extras,
                )
            except (ValueError, TypeError, ConfigurationError, AttributeError) as e:
                # Our attempt to construct the argument may have modified popped_params, so we
                # restore it here.
                popped_params = deepcopy(backup_params)
                e.args = (f"While constructing an argument of type {arg_annotation}",) + e.args
                e.__cause__ = error_chain
                error_chain = e

        # If none of them succeeded, we crash.
        config_error = ConfigurationError(
            f"Failed to construct argument {argument_name} with type {annotation}."
        )
        config_error.__cause__ = error_chain
        raise config_error

    # For any other kind of iterable, we will just assume that a list is good enough, and treat
    # it the same as List. This condition needs to be at the end, so we don't catch other kinds
    # of Iterables with this branch.
    elif (
        origin in {collections.abc.Iterable, Iterable, List, list}
        and len(args) == 1
        and can_construct_from_params(args[0])
    ):
        value_cls = annotation.__args__[0]

        value_list = []

        for i, value_params in enumerate(popped_params):
            value = construct_arg(
                str(value_cls),
                argument_name + f".{i}",
                value_params,
                value_cls,
                _NO_DEFAULT,
                **extras,
            )
            value_list.append(value)

        return value_list

    else:
        # Pass it on as is and hope for the best.   ¯\_(ツ)_/¯
        if isinstance(popped_params, Params):
            return popped_params.as_dict()
        return popped_params


class FromParams:
    """
    Mixin to give a from_params method to classes. We create a distinct base class for this
    because sometimes we want non-Registrable classes to be instantiatable from_params.
    """

    @classmethod
    def from_params(
        cls: Type[T],
        params: Params,
        constructor_to_call: Callable[..., T] = None,
        constructor_to_inspect: Union[Callable[..., T], Callable[[T], None]] = None,
        **extras,
    ) -> T:
        """
        This is the automatic implementation of `from_params`. Any class that subclasses
        `FromParams` (or `Registrable`, which itself subclasses `FromParams`) gets this
        implementation for free.  If you want your class to be instantiated from params in the
        "obvious" way -- pop off parameters and hand them to your constructor with the same names --
        this provides that functionality.

        If you need more complex logic in your from `from_params` method, you'll have to implement
        your own method that overrides this one.

        The `constructor_to_call` and `constructor_to_inspect` arguments deal with a bit of
        redirection that we do.  We allow you to register particular `@classmethods` on a class as
        the constructor to use for a registered name.  This lets you, e.g., have a single
        `Vocabulary` class that can be constructed in two different ways, with different names
        registered to each constructor.  In order to handle this, we need to know not just the class
        we're trying to construct (`cls`), but also what method we should inspect to find its
        arguments (`constructor_to_inspect`), and what method to call when we're done constructing
        arguments (`constructor_to_call`).  These two methods are the same when you've used a
        `@classmethod` as your constructor, but they are `different` when you use the default
        constructor (because you inspect `__init__`, but call `cls()`).
        """
        from bot_maker.registrable import Registrable

        logger.debug(
            f"instantiating class {cls} from params {getattr(params, 'params', params)} "
            f"and extras {set(extras.keys())}"
        )

        if params is None:
            return None

        if isinstance(params, str):
            params = Params({"type": params})

        if not isinstance(params, Params):
            raise ConfigurationError(
                "from_params was passed a `params` object that was not a `Params`. This probably "
                "indicates malformed parameters in a configuration file, where something that "
                "should have been a dictionary was actually a list, or something else. "
                f"This happened when constructing an object of type {cls}."
            )

        registered_subclasses = Registrable._registry.get(cls)

        if is_base_registrable(cls) and registered_subclasses is None:
            # NOTE(mattg): There are some potential corner cases in this logic if you have nested
            # Registrable types.  We don't currently have any of those, but if we ever get them,
            # adding some logic to check `constructor_to_call` should solve the issue.  Not
            # bothering to add that unnecessary complexity for now.
            raise ConfigurationError(
                "Tried to construct an abstract Registrable base class that has no registered "
                "concrete types. This might mean that you need to use --include-package to get "
                "your concrete classes actually registered."
            )

        if registered_subclasses is not None and not constructor_to_call:
            # We know `cls` inherits from Registrable, so we'll use a cast to make mypy happy.

            as_registrable = cast(Type[Registrable], cls)
            default_to_first_choice = as_registrable.default_implementation is not None
            choice = params.pop_choice(
                "type",
                choices=as_registrable.list_available(),
                default_to_first_choice=default_to_first_choice,
            )
            subclass, constructor_name = as_registrable.resolve_class_name(choice)
            # See the docstring for an explanation of what's going on here.
            if not constructor_name:
                constructor_to_inspect = subclass.__init__
                constructor_to_call = subclass  # type: ignore
            else:
                constructor_to_inspect = cast(Callable[..., T], getattr(subclass, constructor_name))
                constructor_to_call = constructor_to_inspect

            if hasattr(subclass, "from_params"):
                # We want to call subclass.from_params.
                extras = create_extras(subclass, extras)
                # mypy can't follow the typing redirection that we do, so we explicitly cast here.
                retyped_subclass = cast(Type[T], subclass)
                return retyped_subclass.from_params(
                    params=params,
                    constructor_to_call=constructor_to_call,
                    constructor_to_inspect=constructor_to_inspect,
                    **extras,
                )
            else:
                # In some rare cases, we get a registered subclass that does _not_ have a
                # from_params method (this happens with Activations, for instance, where we
                # register pytorch modules directly).  This is a bit of a hack to make those work,
                # instead of adding a `from_params` method for them somehow.  We just trust that
                # you've done the right thing in passing your parameters, and nothing else needs to
                # be recursively constructed.
                return subclass(**params)  # type: ignore
        else:
            # This is not a base class, so convert our params and extras into a dict of kwargs.

            # See the docstring for an explanation of what's going on here.
            if not constructor_to_inspect:
                constructor_to_inspect = cls.__init__
            if not constructor_to_call:
                constructor_to_call = cls

            if constructor_to_inspect == object.__init__:
                # This class does not have an explicit constructor, so don't give it any kwargs.
                # Without this logic, create_kwargs will look at object.__init__ and see that
                # it takes *args and **kwargs and look for those.
                kwargs: Dict[str, Any] = {}
                params.assert_empty(cls.__name__)
            else:
                # This class has a constructor, so create kwargs for it.
                constructor_to_inspect = cast(Callable[..., T], constructor_to_inspect)
                kwargs = create_kwargs(constructor_to_inspect, cls, params, **extras)

            return constructor_to_call(**kwargs)  # type: ignore

    def to_params(self) -> Params:
        """
        Returns a `Params` object that can be used with `.from_params()` to recreate an
        object just like it.

        This relies on `_to_params()`. If you need this in your custom `FromParams` class,
        override `_to_params()`, not this method.
        """

        def replace_object_with_params(o: Any) -> Any:
            if isinstance(o, FromParams):
                return o.to_params()
            elif isinstance(o, List):
                return [replace_object_with_params(i) for i in o]
            elif isinstance(o, Set):
                return {replace_object_with_params(i) for i in o}
            elif isinstance(o, Dict):
                return {key: replace_object_with_params(value) for key, value in o.items()}
            else:
                return o

        return Params(replace_object_with_params(self._to_params()))

    def _to_params(self) -> Dict[str, Any]:
        """
        Returns a dictionary of parameters that, when turned into a `Params` object and
        then fed to `.from_params()`, will recreate this object.

        You don't need to implement this all the time. AllenNLP will let you know if you
        need it.
        """
        raise NotImplementedError()
