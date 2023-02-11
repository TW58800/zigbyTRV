import types as t
from zcl import Cluster
from zcl.foundation import ZCLAttributeDef, ZCLCommandDef


class AttributeReportingStatus(t.enum8):
    Pending = 0x00
    Attribute_Reporting_Complete = 0x01


ZCL_CLUSTER_REVISION_ATTR = ZCLAttributeDef(
    "cluster_revision", type=t.uint16_t, access="r", mandatory=True
)
ZCL_REPORTING_STATUS_ATTR = ZCLAttributeDef(
    "attr_reporting_status", type=AttributeReportingStatus, access="r"
)


class Basic(Cluster):
    """Attributes for determining basic information about a
    device, setting user device information such as location,
    and enabling a device.
    """

    class PowerSource(t.enum8):
        """Power source enum."""

        Unknown = 0x00
        Mains_single_phase = 0x01
        Mains_three_phase = 0x02
        Battery = 0x03
        DC_Source = 0x04
        Emergency_Mains_Always_On = 0x05
        Emergency_Mains_Transfer_Switch = 0x06

        def __init__(self, *args, **kwargs):
            self.battery_backup = False

        @classmethod
        def deserialize(cls, data: bytes) -> tuple[bytes, bytes]:
            val, data = t.uint8_t.deserialize(data)
            r = cls(val & 0x7F)
            r.battery_backup = bool(val & 0x80)
            return r, data

    class PhysicalEnvironment(t.enum8):
        Unspecified_environment = 0x00
        # Mirror Capacity Available: for 0x0109 Profile Id only; use 0x71 moving forward
        # Atrium: defined for legacy devices with non-0x0109 Profile Id; use 0x70 moving
        #         forward

        # Note: This value is deprecated for Profile Id 0x0104. The value 0x01 is
        #       maintained for historical purposes and SHOULD only be used for backwards
        #       compatibility with devices developed before this specification. The 0x01
        #       value MUST be interpreted using the Profile Id of the endpoint upon
        #       which it is implemented. For endpoints with the Smart Energy Profile Id
        #       (0x0109) the value 0x01 has a meaning of Mirror. For endpoints with any
        #       other profile identifier, the value 0x01 has a meaning of Atrium.
        Mirror_or_atrium_legacy = 0x01
        Bar = 0x02
        Courtyard = 0x03
        Bathroom = 0x04
        Bedroom = 0x05
        Billiard_Room = 0x06
        Utility_Room = 0x07
        Cellar = 0x08
        Storage_Closet = 0x09
        Theater = 0x0A
        Office = 0x0B
        Deck = 0x0C
        Den = 0x0D
        Dining_Room = 0x0E
        Electrical_Room = 0x0F
        Elevator = 0x10
        Entry = 0x11
        Family_Room = 0x12
        Main_Floor = 0x13
        Upstairs = 0x14
        Downstairs = 0x15
        Basement = 0x16
        Gallery = 0x17
        Game_Room = 0x18
        Garage = 0x19
        Gym = 0x1A
        Hallway = 0x1B
        House = 0x1C
        Kitchen = 0x1D
        Laundry_Room = 0x1E
        Library = 0x1F
        Master_Bedroom = 0x20
        Mud_Room_small_room_for_coats_and_boots = 0x21
        Nursery = 0x22
        Pantry = 0x23
        Office_2 = 0x24
        Outside = 0x25
        Pool = 0x26
        Porch = 0x27
        Sewing_Room = 0x28
        Sitting_Room = 0x29
        Stairway = 0x2A
        Yard = 0x2B
        Attic = 0x2C
        Hot_Tub = 0x2D
        Living_Room = 0x2E
        Sauna = 0x2F
        Workshop = 0x30
        Guest_Bedroom = 0x31
        Guest_Bath = 0x32
        Back_Yard = 0x34
        Front_Yard = 0x35
        Patio = 0x36
        Driveway = 0x37
        Sun_Room = 0x38
        Grand_Room = 0x39
        Spa = 0x3A
        Whirlpool = 0x3B
        Shed = 0x3C
        Equipment_Storage = 0x3D
        Craft_Room = 0x3E
        Fountain = 0x3F
        Pond = 0x40
        Reception_Room = 0x41
        Breakfast_Room = 0x42
        Nook = 0x43
        Garden = 0x44
        Balcony = 0x45
        Panic_Room = 0x46
        Terrace = 0x47
        Roof = 0x48
        Toilet = 0x49
        Toilet_Main = 0x4A
        Outside_Toilet = 0x4B
        Shower_room = 0x4C
        Study = 0x4D
        Front_Garden = 0x4E
        Back_Garden = 0x4F
        Kettle = 0x50
        Television = 0x51
        Stove = 0x52
        Microwave = 0x53
        Toaster = 0x54
        Vacuum = 0x55
        Appliance = 0x56
        Front_Door = 0x57
        Back_Door = 0x58
        Fridge_Door = 0x59
        Medication_Cabinet_Door = 0x60
        Wardrobe_Door = 0x61
        Front_Cupboard_Door = 0x62
        Other_Door = 0x63
        Waiting_Room = 0x64
        Triage_Room = 0x65
        Doctors_Office = 0x66
        Patients_Private_Room = 0x67
        Consultation_Room = 0x68
        Nurse_Station = 0x69
        Ward = 0x6A
        Corridor = 0x6B
        Operating_Theatre = 0x6C
        Dental_Surgery_Room = 0x6D
        Medical_Imaging_Room = 0x6E
        Decontamination_Room = 0x6F
        Atrium = 0x70
        Mirror = 0x71
        Unknown_environment = 0xFF

    class AlarmMask(t.bitmap8):
        General_hardware_fault = 0x01
        General_software_fault = 0x02

    class DisableLocalConfig(t.bitmap8):
        Reset = 0x01
        Device_Configuration = 0x02

    class GenericDeviceClass(t.enum8):
        Lighting = 0x00

    class GenericLightingDeviceType(t.enum8):
        Incandescent = 0x00
        Spotlight_Halogen = 0x01
        Halogen_bulb = 0x02
        CFL = 0x03
        Linear_Fluorescent = 0x04
        LED_bulb = 0x05
        Spotlight_LED = 0x06
        LED_strip = 0x07
        LED_tube = 0x08
        Generic_indoor_luminaire = 0x09
        Generic_outdoor_luminaire = 0x0A
        Pendant_luminaire = 0x0B
        Floor_standing_luminaire = 0x0C
        Generic_Controller = 0xE0
        Wall_Switch = 0xE1
        Portable_remote_controller = 0xE2
        Motion_sensor = 0xE3
        # 0xe4 to 0xef Reserved
        Generic_actuator = 0xF0
        Wall_socket = 0xF1
        Gateway_Bridge = 0xF2
        Plug_in_unit = 0xF3
        Retrofit_actuator = 0xF4
        Unspecified = 0xFF

    cluster_id = 0x0000
    ep_attribute = "basic"
    attributes: dict[int, ZCLAttributeDef] = {
        # Basic Device Information
        0x0000: ZCLAttributeDef(
            "zcl_version", type=t.uint8_t, access="r", mandatory=True
        ),
        0x0001: ZCLAttributeDef("app_version", type=t.uint8_t, access="r"),
        0x0002: ZCLAttributeDef("stack_version", type=t.uint8_t, access="r"),
        0x0003: ZCLAttributeDef("hw_version", type=t.uint8_t, access="r"),
        0x0004: ZCLAttributeDef(
            "manufacturer", type=t.LimitedCharString(32), access="r"
        ),
        0x0005: ZCLAttributeDef("model", type=t.LimitedCharString(32), access="r"),
        0x0006: ZCLAttributeDef("date_code", type=t.LimitedCharString(16), access="r"),
        0x0007: ZCLAttributeDef(
            "power_source", type=PowerSource, access="r", mandatory=True
        ),
        0x0008: ZCLAttributeDef(
            "generic_device_class", type=GenericDeviceClass, access="r"
        ),
        # Lighting is the only non-reserved device type
        0x0009: ZCLAttributeDef(
            "generic_device_type", type=GenericLightingDeviceType, access="r"
        ),
        0x000A: ZCLAttributeDef("product_code", type=t.LVBytes, access="r"),
        0x000B: ZCLAttributeDef("product_url", type=t.CharacterString, access="r"),
        0x000C: ZCLAttributeDef(
            "manufacturer_version_details", type=t.CharacterString, access="r"
        ),
        0x000D: ZCLAttributeDef("serial_number", type=t.CharacterString, access="r"),
        0x000E: ZCLAttributeDef("product_label", type=t.CharacterString, access="r"),
        # Basic Device Settings
        0x0010: ZCLAttributeDef(
            "location_desc", type=t.LimitedCharString(16), access="rw"
        ),
        0x0011: ZCLAttributeDef("physical_env", type=PhysicalEnvironment, access="rw"),
        0x0012: ZCLAttributeDef("device_enabled", type=t.Bool, access="rw"),
        0x0013: ZCLAttributeDef("alarm_mask", type=AlarmMask, access="rw"),
        0x0014: ZCLAttributeDef(
            "disable_local_config", type=DisableLocalConfig, access="rw"
        ),
        0x4000: ZCLAttributeDef("sw_build_id", type=t.CharacterString, access="r"),
        # 0xFFFD: foundation.ZCL_CLUSTER_REVISION_ATTR,
        0xFFFD: ZCL_CLUSTER_REVISION_ATTR,  # did not import zcl.foundation, just copied in the missing references at top
        # 0xFFFE: foundation.ZCL_REPORTING_STATUS_ATTR,
        0xFFFE: ZCL_REPORTING_STATUS_ATTR,
    }
    server_commands: dict[int, ZCLCommandDef] = {
        0x00: ZCLCommandDef("reset_fact_default", {}, False)
    }
    client_commands: dict[int, ZCLCommandDef] = {}


