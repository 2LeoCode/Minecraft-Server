from dataclasses import dataclass


@dataclass(slots=True)
class Identifier:
  namespace: str
  name: str


@dataclass(slots=True)
class Slot[T]:
  present: bool
  item_id: int | None = None
  item_count: int | None = None
  nbt: T | None = None


@dataclass(slots=True)
class Position:
  x: int
  y: int
  z: int
