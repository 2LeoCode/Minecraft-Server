from abc import ABC, abstractmethod
from dataclasses import dataclass
from data_types import Identifier, Slot, Position
import json
import struct
import re


@dataclass(slots=True)
class EncoderParseResult[T]:
  value: T
  size: int


class Encoder[T](ABC):

  @staticmethod
  @abstractmethod
  def parse(data: bytes) -> EncoderParseResult[T]:
    ...


  @staticmethod
  @abstractmethod
  def serialize(value: T) -> bytes:
    ...


class BooleanEncoder(Encoder[bool]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=bool(data[0]),
      size=1
    )

  @staticmethod
  def serialize(value: bool):
    return value.to_bytes(1)


class ByteEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=int.from_bytes(data[:1], signed=True),
      size=1
    )

  @staticmethod
  def serialize(value: int):
    if not -128 <= value <= 127:
      raise ValueError(f"ByteEncoder: Serialization error: {value} is not in range [-128, 127]")
    return value.to_bytes(1, signed=True)


class UnsignedByteEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=int.from_bytes(data[:1], signed=False),
      size=1
    )

  @staticmethod
  def serialize(value: int):
    if not 0 <= value <= 255:
      raise ValueError(f"UnsignedByteEncoder: Serialization Error: {value} is not in range [0, 255]")
    return value.to_bytes(1, signed=False)


class ShortEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=int.from_bytes(data[:2], byteorder="big", signed=True),
      size=2
    )


  @staticmethod
  def serialize(value: int):
    if not -32768 <= value <= 23767:
      raise ValueError(f"ShortEncoder: Serialization error: {value} is not in range [-32768, 32767]")
    return value.to_bytes(2, byteorder="big", signed=True)


class UnsignedShortEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      int.from_bytes(data[:2], byteorder="big", signed=False),
      size=2
    )

  @staticmethod
  def serialize(value: int):
    if not 0 <= value <= 65535:
      raise ValueError(f"UnsignedShortEncoder: Serialization error {value} is not in range [0, 65535]")
    return value.to_bytes(2, byteorder="big", signed=False)


class IntEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=int.from_bytes(data[:4], byteorder="big", signed=True),
      size=4
    )

  @staticmethod
  def serialize(value: int):
    if not -2147483648 <= value <= 2147483647:
      raise ValueError(f"IntEncoder: Serialization error: {value} is not in range [-2147483648, 2147483647]")
    return value.to_bytes(4, byteorder="big", signed=True)


class LongEncoder(Encoder[int]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=int.from_bytes(data[:8], byteorder="big", signed=True),
      size=8
    )

  @staticmethod
  def serialize(value: int):
    if not -9223372036854775808 <= value <= 9223372036854775807:
      raise ValueError(f"LongEncoder: Serialization error: {value} is not in range [-9223372036854775808, 9223372036854775807]")
    return value.to_bytes(8, byteorder="big", signed=True)


class FloatEncoder(Encoder[float]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=struct.unpack(">f", data)[0],
      size=4
    )
    

  @staticmethod
  def serialize(value: float):
    return struct.pack(">f", value)


class DoubleEncoder(Encoder[float]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=struct.unpack(">d", data)[0],
      size=8
    )

  @staticmethod
  def serialize(value: float):
    return struct.pack(">d", value)


class StringEncoder(Encoder[str]):

  @staticmethod
  def parse(data: bytes):
    length = VarIntEncoder.parse(data)
    if not 0 <= length.value <= 32767:
      raise ValueError(f"StringEncoder: Parsing error: Invalid length {length.value}")
    value = ""
    i = 0
    while len(value) < length.value:
      for c_len in range(1, 4):
        try:
          c = data[i:i + c_len].decode("utf-8")
        except UnicodeDecodeError:
          continue
        else:
          value += c
          i += c_len
          break
    return EncoderParseResult(
      value=value,
      size=length.size + len(value.encode("utf-8"))
    )

  @staticmethod
  def serialize(value: str):
    if not 1 <= (length := len(value)) <= 32767:
      raise ValueError(f"StringEncoder: Serialization error: Invalid string length {length}")
    return VarIntEncoder.serialize(length) + value.encode("utf-8")


class TextComponentEncoder(Encoder[str]):

  @staticmethod
  def parse(data: bytes) -> str:
    return NotImplemented

  @staticmethod
  def serialize(value: str) -> bytes:
    return NotImplemented


class JSONTextComponentEncoder[T](Encoder[T]):

  @staticmethod
  def parse(data: bytes):
    if not 1 <= (size := len(data)) <= 262144 * 3 + 3:
      raise ValueError(f"JSONTextComponentEncoder: Parsing error: Expected [1, 262144 * 3 + 3] bytes, got {size}")
    string = StringEncoder.parse(data)
    return EncoderParseResult(
      value=json.loads(string.value),
      size=string.size
    )

  @staticmethod
  def serialize(value: T):
    return StringEncoder.serialize(json.dumps(value))


class IdentifierEncoder(Encoder[Identifier]):

  @staticmethod
  def parse(data: bytes):
    string = StringEncoder.parse(data)
    if not ":" in string.value:
      string.value = f"minecraft:{string.value}"
      string.size += 10
    if re.match(r"^[a-z0-9_\-.]+:[a-z0-9_\-./]+$", string.value) is None:
      raise ValueError(f"IdentifierEncoder: Parsing error: '{string.value}' is not a valid identifier")
    namespace, name = string.value.split(":")
    return EncoderParseResult(
      value=Identifier(namespace, name),
      size=string.size
    )


  @staticmethod
  def serialize(value: Identifier):
    return StringEncoder.serialize(f"{value.namespace}:{value.name}")


class VarIntEncoder(Encoder[int]):
  SEGMENT_BITS = 0x7f
  CONTINUE_BIT = 0x80

  @staticmethod
  def parse(data: bytes):
    value = 0
    position = 0
    size = 0

    while True:
      current_byte = ByteEncoder.parse(data[size:]).value
      value |= (current_byte & VarIntEncoder.SEGMENT_BITS) << position
      if (current_byte & VarIntEncoder.CONTINUE_BIT) == 0:
        break
      size += 1
      position += 7
      if position >= 32:
        raise ValueError("VarIntEncoder: Parsing error: VarInt is too big")
    return EncoderParseResult(
      value=value,
      size=size
    )

  @staticmethod
  def serialize(value: int):
    data = b""
    while (value & ~VarIntEncoder.SEGMENT_BITS):
      data += ByteEncoder.serialize((value & VarIntEncoder.SEGMENT_BITS) | VarIntEncoder.CONTINUE_BIT)
      value = (value % 0x10000000) >> 7
    return data + ByteEncoder.serialize(value)


class VarLongEncoder(Encoder[int]):
  SEGMENT_BITS = 0x7f
  CONTINUE_BIT = 0x80

  @staticmethod
  def parse(data: bytes):
    value = 0
    position = 0
    size = 0

    while True:
      current_byte = ByteEncoder.parse(data[size:]).value
      value |= (current_byte & VarLongEncoder.SEGMENT_BITS) << position
      if (current_byte & VarLongEncoder.CONTINUE_BIT) == 0:
        break
      size += 1
      position += 7
      if position >= 64:
        raise ValueError("VarLongEncoder: Parsing error: VarLong is too big")
    return EncoderParseResult(
      value=value,
      size=size
    )

  @staticmethod
  def serialize(value: int):
    data = b""
    while (value & ~VarLongEncoder.SEGMENT_BITS):
      data += ByteEncoder.serialize((value & VarLongEncoder.SEGMENT_BITS) | VarLongEncoder.CONTINUE_BIT)
      value = (value % 0x10000000000000000) >> 7
    return data + ByteEncoder.serialize(value)


class EntityMetadataEncoder(Encoder[None]):

  @staticmethod
  def parse(data: bytes):
    return NotImplemented

  @staticmethod
  def serialize(value: None):
    return NotImplemented


class SlotEncoder[T](Encoder[Slot[T]]):

  @staticmethod
  def parse(data: bytes):
    return NotImplemented

  @staticmethod
  def serialize(value: Slot[T]):
    return NotImplemented

class PositionEncoder(Encoder[Position]):

  @staticmethod
  def parse(data: bytes):
    return EncoderParseResult(
      value=Position(
        x=int.from_bytes(data[:4], byteorder="big", signed=True) & 0xffffffc0,
        y=int.from_bytes(data[3:7], byteorder="big", signed=True) & 0xffffff0,
        z=int.from_bytes(data[6:8], byteorder="big", signed=True) & 0xfff
      ),
      size=8
    )

  @staticmethod
  def serialize(value: Position):
    return (value.x << 38 | value.y << 12 | value.z).to_bytes(8, byteorder="big", signed=True)
    


class AngleEncoder(Encoder[int]):
  
  @staticmethod
  def parse(data: bytes):
    return UnsignedByteEncoder.parse(data)

  @staticmethod
  def serialize(value: int):
    return UnsignedByteEncoder.serialize(value)

