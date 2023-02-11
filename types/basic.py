from __future__ import annotations
import enum
import sys
import typing

# CALLABLE_T = typing.TypeVar("CALLABLE_T", bound=typing.Callable)
T = typing.TypeVar("T")


class Bits(list):
    @classmethod
    def from_bitfields(cls, fields):
        instance = cls()

        # Little endian, so [11, 1000, 00] will be packed as 00_1000_11
        for field in fields[::-1]:
            instance.extend(field.bits())

        return instance

    def serialize(self) -> bytes:
        if len(self) % 8 != 0:
            raise ValueError(f"Cannot serialize {len(self)} bits into bytes: {self}")

        serialized_bytes = []

        for index in range(0, len(self), 8):
            byte = 0x00

            for bit in self[index: index + 8]:
                byte <<= 1
                byte |= bit

            serialized_bytes.append(byte)

        return bytes(serialized_bytes)

    @classmethod
    def deserialize(cls, data) -> tuple[Bits, bytes]:
        bits: list[int] = []

        for byte in data:
            bits.extend((byte >> i) & 1 for i in range(7, -1, -1))

        return cls(bits), b""


NOT_SET = object()


# noinspection PyStringFormat
class FixedIntType(int):
    _signed = None
    _bits = None
    _size = None  # Only for backwards compatibility, not set for smaller ints
    _byteorder = None

    min_value: int
    max_value: int

    def __new__(cls, *args, **kwargs):
        if cls._signed is None or cls._bits is None:
            raise TypeError(f"{cls} is abstract and cannot be created")

        n = super().__new__(cls, *args, **kwargs)

        if not cls.min_value <= n <= cls.max_value:
            raise ValueError(
                f"{int(n)} is not an {'un' if not cls._signed else ''}signed"
                f" {cls._bits} bit integer"
            )

        return n

    def _hex_repr(self):
        assert self._bits % 4 == 0
        return f"0x{{:0{self._bits // 4}X}}".format(int(self))

    def _bin_repr(self):
        return f"0b{{:0{self._bits}b}}".format(int(self))

    def __init_subclass__(
        cls, signed=NOT_SET, bits=NOT_SET, repr=NOT_SET, byteorder=NOT_SET
    ) -> None:
        super().__init_subclass__()

        if signed is not NOT_SET:
            cls._signed = signed

        if bits is not NOT_SET:
            cls._bits = bits

            if bits % 8 == 0:
                cls._size = bits // 8
            else:
                cls._size = None

        if cls._bits is not None and cls._signed is not None:
            if cls._signed:
                cls.min_value = -(2 ** (cls._bits - 1))
                cls.max_value = 2 ** (cls._bits - 1) - 1
            else:
                cls.min_value = 0
                cls.max_value = 2**cls._bits - 1

        if repr == "hex":
            assert cls._bits % 4 == 0
            cls.__str__ = cls.__repr__ = cls._hex_repr
        elif repr == "bin":
            cls.__str__ = cls.__repr__ = cls._bin_repr
        elif not repr:
            cls.__str__ = super().__str__
            cls.__repr__ = super().__repr__
        elif repr is not NOT_SET:
            raise ValueError(f"Invalid repr value {repr!r}. Must be either hex or bin")

        if byteorder is not NOT_SET:
            cls._byteorder = byteorder
        elif cls._byteorder is None:
            cls._byteorder = "little"

        # XXX: The enum module uses the first class with __new__ in its __dict__ as the
        #      member type. We have to ensure this is true for every subclass.
        if "__new__" not in cls.__dict__:
            cls.__new__ = cls.__new__

        # XXX: The enum module sabotages pickling using the same logic.
        if "__reduce_ex__" not in cls.__dict__:
            cls.__reduce_ex__ = cls.__reduce_ex__

    def bits(self) -> Bits:
        return Bits([(self >> n) & 0b1 for n in range(self._bits - 1, -1, -1)])

    @classmethod
    def from_bits(cls, bits: Bits) -> tuple[FixedIntType, Bits]:
        if len(bits) < cls._bits:
            raise ValueError(f"Not enough bits to decode {cls}: {bits}")

        n = 0

        for bit in bits[-cls._bits:]:
            n <<= 1
            n |= bit & 1

        if cls._signed and n >= 2 ** (cls._bits - 1):
            n -= 2**cls._bits

        return cls(n), bits[: -cls._bits]

    def serialize(self) -> bytes:
        if self._bits % 8 != 0:
            raise TypeError(f"Integer type with {self._bits} bits is not byte aligned")

        return self.to_bytes(self._bits // 8, self._byteorder, signed=self._signed)

    @classmethod
    def deserialize(cls, data: bytes) -> tuple[FixedIntType, bytes]:
        if cls._bits % 8 != 0:
            raise TypeError(f"Integer type with {cls._bits} bits is not byte aligned")

        byte_size = cls._bits // 8

        if len(data) < byte_size:
            raise ValueError(f"Data is too short to contain {byte_size} bytes")

        r = cls.from_bytes(data[:byte_size], cls._byteorder, signed=cls._signed)
        data = data[byte_size:]
        return r, data


class uint_t(FixedIntType, signed=False):
    pass


class uint8_t(uint_t, bits=8):
    pass


class uint16_t(uint_t, bits=16):
    pass


# def bitmap_factory(int_type: CALLABLE_T) -> CALLABLE_T:
def bitmap_factory(int_type):
    """
    Mixins are broken by Python 3.8.6 so we must dynamically create the enum with the
    appropriate methods but with only one non-Enum parent class.
    """

    if sys.version_info >= (3, 11):

        class _NewEnum(int_type, enum.ReprEnum, enum.Flag, boundary=enum.KEEP):
            pass

    else:

        class _NewEnum(int_type, enum.Flag):
            # Rebind classmethods to our own class
            _missing_ = classmethod(enum.IntFlag._missing_.__func__)
            _create_pseudo_member_ = classmethod(
                enum.IntFlag._create_pseudo_member_.__func__
            )

            __or__ = enum.IntFlag.__or__
            __and__ = enum.IntFlag.__and__
            __xor__ = enum.IntFlag.__xor__
            __ror__ = enum.IntFlag.__ror__
            __rand__ = enum.IntFlag.__rand__
            __rxor__ = enum.IntFlag.__rxor__
            __invert__ = enum.IntFlag.__invert__

    return _NewEnum


class bitmap8(bitmap_factory(uint8_t)):
    pass


# def enum_factory(int_type: CALLABLE_T, undefined: str = "undefined") -> CALLABLE_T:
def enum_factory(int_type, undefined: str = "undefined"):
    """Enum factory."""

    # noinspection PyProtectedMember
    class _NewEnum(int_type, enum.Enum):  # , metaclass=_IntEnumMeta):
        @classmethod
        def _missing_(cls, value):
            new = cls._member_type_.__new__(cls, value)

            if cls._bits % 8 == 0:
                name = f"{undefined}_{new._hex_repr().lower()}"
            else:
                name = f"{undefined}_{new._bin_repr()}"

            new._name_ = name.format(value)
            new._value_ = value
            return new

        def __format__(self, format_spec: str) -> str:
            if format_spec:
                # Allow formatting the integer enum value
                return self._member_type_.__format__(self, format_spec)
            else:
                # Otherwise, format it as its string representation
                return object.__format__(repr(self), format_spec)

    return _NewEnum


class enum8(enum_factory(uint8_t)):  # noqa: N801
    pass


class CharacterString(str):
    _prefix_length = 1

    def serialize(self) -> bytes:
        if len(self) >= pow(256, self._prefix_length) - 1:
            raise ValueError("String is too long")
        return len(self).to_bytes(
            self._prefix_length, "little", signed=False
        ) + self.encode("utf8")

    @classmethod
    def deserialize(cls: type[T], data: bytes) -> tuple[T, bytes]:
        if len(data) < cls._prefix_length:
            raise ValueError("Data is too short")

        length = int.from_bytes(data[: cls._prefix_length], "little")

        if len(data) < cls._prefix_length + length:
            raise ValueError("Data is too short")

        raw = data[cls._prefix_length : cls._prefix_length + length]
        text = raw.split(b"\x00")[0].decode("utf8", errors="replace")

        # FIXME: figure out how to get this working: `T` is not behaving as expected in
        # the classmethod when it is not bound.
        r = cls(text)  # type:ignore[call-arg]
        r.raw = raw
        return r, data[cls._prefix_length + length :]


def LimitedCharString(max_len):  # noqa: N802
    class LimitedCharString(CharacterString):
        _max_len = max_len

        def serialize(self) -> bytes:
            if len(self) > self._max_len:
                raise ValueError(f"String is too long (>{self._max_len})")
            return super().serialize()

    return LimitedCharString