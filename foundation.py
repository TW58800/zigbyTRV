from __future__ import annotations
import dataclasses
import enum
import functools
import keyword
import warnings
import types as t


def ensure_valid_name(name: str | None) -> None:
    """
    Ensures that the name of an attribute or command is valid.
    """
    if name is not None and not name.isidentifier():
        raise ValueError(f"{name!r} is not a valid identifier name.")


class ZCLAttributeAccess(enum.Flag):
    NONE = 0
    Read = 1
    Write = 2
    Write_Optional = 4
    Report = 8
    Scene = 16

    _names: dict[ZCLAttributeAccess, str]

    @classmethod
    @functools.lru_cache(None)
    def from_str(cls: ZCLAttributeAccess, value: str) -> ZCLAttributeAccess:
        orig_value = value
        access = cls.NONE

        while value:
            for mode, prefix in cls._names.items():
                if value.startswith(prefix):
                    value = value[len(prefix) :]
                    access |= mode
                    break
            else:
                raise ValueError(f"Invalid access mode: {orig_value!r}")

        return cls(access)


ZCLAttributeAccess._names = {
    ZCLAttributeAccess.Write_Optional: "*w",
    ZCLAttributeAccess.Write: "w",
    ZCLAttributeAccess.Read: "r",
    ZCLAttributeAccess.Report: "p",
    ZCLAttributeAccess.Scene: "s",
}


@dataclasses.dataclass(frozen=True)
class ZCLAttributeDef:
    name: str = None
    type: type = None
    access: ZCLAttributeAccess = dataclasses.field(
        default=(
            ZCLAttributeAccess.Read
            | ZCLAttributeAccess.Write
            | ZCLAttributeAccess.Report
        ),
    )
    mandatory: bool = False
    is_manufacturer_specific: bool = False

    # The ID will be specified later
    id: t.uint16_t = None

    def __post_init__(self):
        if self.id is not None and not isinstance(self.id, t.uint16_t):
            object.__setattr__(self, "id", t.uint16_t(self.id))

        if isinstance(self.access, str):
            ZCLAttributeAccess.NONE
            object.__setattr__(self, "access", ZCLAttributeAccess.from_str(self.access))

        ensure_valid_name(self.name)

    def replace(self, **kwargs) -> ZCLAttributeDef:
        return dataclasses.replace(self, **kwargs)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id=0x{self.id:04X}, "
            f"name={self.name!r}, "
            f"type={self.type}, "
            f"access={self.access!r}, "
            f"mandatory={self.mandatory!r}, "
            f"is_manufacturer_specific={self.is_manufacturer_specific}"
            f")"
        )

    def __getitem__(self, key):
        warnings.warn("Attributes should be accessed by name", DeprecationWarning)
        return (self.name, self.type)[key]


class Direction(t.enum1):
    """ZCL frame control direction."""

    Server_to_Client = 0
    Client_to_Server = 1

    @classmethod
    def _from_is_reply(cls, is_reply: bool) -> Direction:
        return cls.Client_to_Server if is_reply else cls.Server_to_Client


class CommandSchema(t.Struct, tuple):
    """
    Struct subclass that behaves more like a tuple.
    """

    command: ZCLCommandDef = None

    def __iter__(self):
        return iter(self.as_tuple())

    def __getitem__(self, item):
        return self.as_tuple()[item]

    def __len__(self) -> int:
        return len(self.as_tuple())

    def __eq__(self, other) -> bool:
        if isinstance(other, tuple) and not isinstance(other, type(self)):
            return self.as_tuple() == other

        return super().__eq__(other)


@dataclasses.dataclass(frozen=True)
class ZCLCommandDef:
    name: str = None
    schema: CommandSchema = None
    direction: Direction = None
    id: t.uint8_t = None
    is_manufacturer_specific: bool = None

    # Deprecated
    is_reply: bool = None

    def __post_init__(self):
        ensure_valid_name(self.name)

        if self.is_reply is not None:
            warnings.warn(
                "`is_reply` is deprecated, use `direction`", DeprecationWarning
            )
            object.__setattr__(self, "direction", Direction(self.is_reply))

        object.__setattr__(self, "is_reply", bool(self.direction))

    def with_compiled_schema(self):
        """
        Return a copy of the ZCL command definition object with its dictionary command
        schema converted into a `CommandSchema` subclass.
        """

        if isinstance(self.schema, tuple):
            raise ValueError(
                f"Tuple schemas are deprecated: {self.schema!r}. Use a dictionary or a"
                f" Struct subclass."
            )
        elif not isinstance(self.schema, dict):
            # If the schema is already a struct, do nothing
            self.schema.command = self
            return self

        assert self.id is not None
        assert self.name is not None

        cls_attrs = {
            "__annotations__": {},
            "command": self,
        }

        for name, param_type in self.schema.items():
            plain_name = name.rstrip("?")

            # Make sure parameters with names like "foo bar" and "class" can't exist
            if not plain_name.isidentifier() or keyword.iskeyword(plain_name):
                raise ValueError(
                    f"Schema parameter {name} must be a valid Python identifier"
                )

            cls_attrs["__annotations__"][plain_name] = "None"
            cls_attrs[plain_name] = t.StructField(
                type=param_type,
                optional=name.endswith("?"),
            )

        schema = type(self.name, (CommandSchema,), cls_attrs)

        return self.replace(schema=schema)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id=0x{self.id:02X}, "
            f"name={self.name!r}, "
            f"direction={self.direction}, "
            f"schema={self.schema}, "
            f"is_manufacturer_specific={self.is_manufacturer_specific}"
            f")"
        )

    def replace(self, **kwargs) -> ZCLCommandDef:
        return dataclasses.replace(self, is_reply=None, **kwargs)

    def __getitem__(self, key):
        warnings.warn("Attributes should be accessed by name", DeprecationWarning)
        return (self.name, self.schema, self.direction)[key]
