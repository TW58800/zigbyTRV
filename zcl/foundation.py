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


class FrameType(t.enum2):
    """ZCL Frame Type."""

    GLOBAL_COMMAND = 0b00
    CLUSTER_COMMAND = 0b01
    RESERVED_2 = 0b10
    RESERVED_3 = 0b11


class Direction(t.enum1):
    """ZCL frame control direction."""

    Server_to_Client = 0
    Client_to_Server = 1

    @classmethod
    def _from_is_reply(cls, is_reply: bool) -> Direction:
        return cls.Client_to_Server if is_reply else cls.Server_to_Client


class FrameControl(t.Struct, t.uint8_t):
    """The frame control field contains information defining the command type
    and other control flags."""

    frame_type: FrameType
    is_manufacturer_specific: t.uint1_t
    direction: Direction
    disable_default_response: t.uint1_t
    reserved: t.uint3_t

    @property
    def is_reply(self) -> bool | None:
        warnings.warn("`is_reply` is deprecated, use `direction`", DeprecationWarning)

        if self.direction is None:
            return None

        return bool(self.direction)

    @is_reply.setter
    def is_reply(self, value: bool | None):
        warnings.warn("`is_reply` is deprecated, use `direction`", DeprecationWarning)

        if value is None:
            self.direction = None
        else:
            self.direction = Direction(value)

    @classmethod
    def cluster(
        cls,
        direction: Direction = Direction.Server_to_Client,
        is_reply: bool | None = None,
        is_manufacturer_specific: bool = False,
    ):
        if is_reply is not None:
            warnings.warn(
                "`is_reply` is deprecated, use `direction`", DeprecationWarning
            )
            direction = Direction(is_reply)

        return cls(
            frame_type=FrameType.CLUSTER_COMMAND,
            is_manufacturer_specific=is_manufacturer_specific,
            direction=direction,
            disable_default_response=(direction == Direction.Client_to_Server),
            reserved=0b000,
        )

    @classmethod
    def general(
        cls,
        direction: Direction = Direction.Server_to_Client,
        is_reply: bool | None = None,
        is_manufacturer_specific: bool = False,
    ):
        if is_reply is not None:
            warnings.warn(
                "`is_reply` is deprecated, use `direction`", DeprecationWarning
            )
            direction = Direction(is_reply)

        return cls(
            frame_type=FrameType.GLOBAL_COMMAND,
            is_manufacturer_specific=is_manufacturer_specific,
            direction=direction,
            disable_default_response=(direction == Direction.Client_to_Server),
            reserved=0b000,
        )

    @property
    def is_cluster(self) -> bool:
        """Return True if command is a local cluster specific command."""
        return bool(self.frame_type == FrameType.CLUSTER_COMMAND)

    @property
    def is_general(self) -> bool:
        """Return True if command is a global ZCL command."""
        return bool(self.frame_type == FrameType.GLOBAL_COMMAND)


class ZCLHeader(t.Struct):
    NO_MANUFACTURER_ID = -1  # type: typing.Literal

    frame_control: FrameControl
    manufacturer: t.uint16_t = t.StructField(
        requires=lambda hdr: hdr.frame_control.is_manufacturer_specific
    )
    tsn: t.uint8_t
    command_id: t.uint8_t

    def __new__(
        cls, frame_control=None, manufacturer=None, tsn=None, command_id=None
    ) -> ZCLHeader:
        # Allow "auto manufacturer ID" to be disabled in higher layers
        if manufacturer is cls.NO_MANUFACTURER_ID:
            manufacturer = None

        if frame_control is not None and manufacturer is not None:
            frame_control.is_manufacturer_specific = True

        return super().__new__(cls, frame_control, manufacturer, tsn, command_id)

    @property
    def is_reply(self) -> bool:
        """Return direction of Frame Control."""
        return self.frame_control.direction == Direction.Client_to_Server

    @property
    def direction(self) -> bool:
        """Return direction of Frame Control."""
        return self.frame_control.direction

    def __setattr__(self, name, value) -> None:
        if name == "manufacturer" and value is self.NO_MANUFACTURER_ID:
            value = None

        super().__setattr__(name, value)

        if name == "manufacturer" and self.frame_control is not None:
            self.frame_control.is_manufacturer_specific = value is not None

    @classmethod
    def general(
        cls,
        tsn: int | t.uint8_t,
        command_id: int | t.uint8_t,
        manufacturer: int | t.uint16_t | None = None,
        is_reply: bool = None,
        direction: Direction = Direction.Server_to_Client,
    ) -> ZCLHeader:
        return cls(
            frame_control=FrameControl.general(
                is_reply=is_reply,  # deprecated
                direction=direction,
                is_manufacturer_specific=(manufacturer is not None),
            ),
            manufacturer=manufacturer,
            tsn=tsn,
            command_id=command_id,
        )

    @classmethod
    def cluster(
        cls,
        tsn: int | t.uint8_t,
        command_id: int | t.uint8_t,
        manufacturer: int | t.uint16_t | None = None,
        is_reply: bool = None,
        direction: Direction = Direction.Server_to_Client,
    ) -> ZCLHeader:
        return cls(
            frame_control=FrameControl.cluster(
                is_reply=is_reply,  # deprecated
                direction=direction,
                is_manufacturer_specific=(manufacturer is not None),
            ),
            manufacturer=manufacturer,
            tsn=tsn,
            command_id=command_id,
        )


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


class GeneralCommand(t.enum8):
    """ZCL Foundation General Command IDs."""

    Read_Attributes = 0x00
    Read_Attributes_rsp = 0x01
    Write_Attributes = 0x02
    Write_Attributes_Undivided = 0x03
    Write_Attributes_rsp = 0x04
    Write_Attributes_No_Response = 0x05
    Configure_Reporting = 0x06
    Configure_Reporting_rsp = 0x07
    Read_Reporting_Configuration = 0x08
    Read_Reporting_Configuration_rsp = 0x09
    Report_Attributes = 0x0A
    Default_Response = 0x0B
    Discover_Attributes = 0x0C
    Discover_Attributes_rsp = 0x0D
    # Read_Attributes_Structured = 0x0e
    # Write_Attributes_Structured = 0x0f
    # Write_Attributes_Structured_rsp = 0x10
    Discover_Commands_Received = 0x11
    Discover_Commands_Received_rsp = 0x12
    Discover_Commands_Generated = 0x13
    Discover_Commands_Generated_rsp = 0x14
    Discover_Attribute_Extended = 0x15
    Discover_Attribute_Extended_rsp = 0x16


GENERAL_COMMANDS = COMMANDS = {
    GeneralCommand.Read_Attributes: ZCLCommandDef(
        schema={"attribute_ids": t.List[t.uint16_t]},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Read_Attributes_rsp: ZCLCommandDef(
        schema={"status_records": t.List[ReadAttributeRecord]},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Write_Attributes: ZCLCommandDef(
        schema={"attributes": t.List[Attribute]}, direction=Direction.Server_to_Client
    ),
    GeneralCommand.Write_Attributes_Undivided: ZCLCommandDef(
        schema={"attributes": t.List[Attribute]}, direction=Direction.Server_to_Client
    ),
    GeneralCommand.Write_Attributes_rsp: ZCLCommandDef(
        schema={"status_records": WriteAttributesResponse},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Write_Attributes_No_Response: ZCLCommandDef(
        schema={"attributes": t.List[Attribute]}, direction=Direction.Server_to_Client
    ),
    GeneralCommand.Configure_Reporting: ZCLCommandDef(
        schema={"config_records": t.List[AttributeReportingConfig]},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Configure_Reporting_rsp: ZCLCommandDef(
        schema={"status_records": ConfigureReportingResponse},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Read_Reporting_Configuration: ZCLCommandDef(
        schema={"attribute_records": t.List[ReadReportingConfigRecord]},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Read_Reporting_Configuration_rsp: ZCLCommandDef(
        schema={"attribute_configs": t.List[AttributeReportingConfigWithStatus]},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Report_Attributes: ZCLCommandDef(
        schema={"attribute_reports": t.List[Attribute]},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Default_Response: ZCLCommandDef(
        schema={"command_id": t.uint8_t, "status": Status},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Discover_Attributes: ZCLCommandDef(
        schema={"start_attribute_id": t.uint16_t, "max_attribute_ids": t.uint8_t},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Discover_Attributes_rsp: ZCLCommandDef(
        schema={
            "discovery_complete": t.Bool,
            "attribute_info": t.List[DiscoverAttributesResponseRecord],
        },
        direction=Direction.Client_to_Server,
    ),
    # Command.Read_Attributes_Structured: ZCLCommandDef(schema=(, ), direction=Direction.Server_to_Client),
    # Command.Write_Attributes_Structured: ZCLCommandDef(schema=(, ), direction=Direction.Server_to_Client),
    # Command.Write_Attributes_Structured_rsp: ZCLCommandDef(schema=(, ), direction=Direction.Client_to_Server),
    GeneralCommand.Discover_Commands_Received: ZCLCommandDef(
        schema={"start_command_id": t.uint8_t, "max_command_ids": t.uint8_t},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Discover_Commands_Received_rsp: ZCLCommandDef(
        schema={"discovery_complete": t.Bool, "command_ids": t.List[t.uint8_t]},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Discover_Commands_Generated: ZCLCommandDef(
        schema={"start_command_id": t.uint8_t, "max_command_ids": t.uint8_t},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Discover_Commands_Generated_rsp: ZCLCommandDef(
        schema={"discovery_complete": t.Bool, "command_ids": t.List[t.uint8_t]},
        direction=Direction.Client_to_Server,
    ),
    GeneralCommand.Discover_Attribute_Extended: ZCLCommandDef(
        schema={"start_attribute_id": t.uint16_t, "max_attribute_ids": t.uint8_t},
        direction=Direction.Server_to_Client,
    ),
    GeneralCommand.Discover_Attribute_Extended_rsp: ZCLCommandDef(
        schema={
            "discovery_complete": t.Bool,
            "extended_attr_info": t.List[DiscoverAttributesExtendedResponseRecord],
        },
        direction=Direction.Client_to_Server,
    ),
}

for command_id, command_def in list(GENERAL_COMMANDS.items()):
    GENERAL_COMMANDS[command_id] = command_def.replace(
        id=command_id, name=command_id.name
    ).with_compiled_schema()

ZCL_CLUSTER_REVISION_ATTR = ZCLAttributeDef(
    "cluster_revision", type=t.uint16_t, access="r", mandatory=True
)
ZCL_REPORTING_STATUS_ATTR = ZCLAttributeDef(
    "attr_reporting_status", type=AttributeReportingStatus, access="r"
)