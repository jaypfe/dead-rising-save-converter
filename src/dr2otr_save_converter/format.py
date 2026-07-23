"""Low-level helpers for Dead Rising 2: Off the Record save containers.

This module intentionally contains only the container offsets and checksum
algorithm verified for the extracted Xbox 360 and native-PC formats.
It does not attempt to convert the mixed-endian logical payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ByteOrder = Literal["big", "little"]
ChecksumPolicy = Literal["computed", "zero"]


@dataclass(frozen=True)
class Section:
    name: str
    checksum_offset: int
    data_offset: int
    data_length: int
    platform_length: int
    duplicate_offset: int
    checksum_policy: ChecksumPolicy = "computed"

    @property
    def data_end(self) -> int:
        return self.data_offset + self.data_length

    @property
    def platform_offset(self) -> int:
        return self.data_end

    @property
    def platform_end(self) -> int:
        return self.platform_offset + self.platform_length

    @property
    def required_end(self) -> int:
        return max(
            self.checksum_offset + 4,
            self.data_end,
            self.platform_end,
            self.duplicate_offset + 4,
        )


@dataclass(frozen=True)
class Layout:
    name: str
    byte_order: ByteOrder
    header: Section
    player: Section
    story: Section
    sandbox: Section | None

    def sections_for_size(self, size: int) -> tuple[Section, ...]:
        sections = [self.header, self.player, self.story]
        if self.sandbox is not None and size >= self.sandbox.required_end:
            sections.append(self.sandbox)
        return tuple(sections)


XBOX = Layout(
    name="xbox360",
    byte_order="big",
    header=Section("header", 0x00000, 0x00004, 57, 0, 0x0003D),
    player=Section("player", 0x01388, 0x0138C, 2065, 0, 0x01B9D),
    story=Section("story", 0x09C40, 0x09C44, 108894, 0, 0x245A2),
    sandbox=Section("sandbox", 0x29810, 0x29814, 85590, 0, 0x3E66A),
)


PC_NATIVE = Layout(
    name="pc-native",
    byte_order="little",
    header=Section("header", 0x00000, 0x00160, 57, 0, 0x00199),
    player=Section(
        "player", 0x018CC, 0x018D0, 2065, 348, 0x0223D, "zero"
    ),
    story=Section(
        "story", 0x0A184, 0x0A188, 108894, 348, 0x24C42, "zero"
    ),
    sandbox=Section(
        "sandbox", 0x29D54, 0x29D58, 85590, 348, 0x3ED0A, "zero"
    ),
)


def _reverse_byte(value: int) -> int:
    value = ((value & 0xF0) >> 4) | ((value & 0x0F) << 4)
    value = ((value & 0xCC) >> 2) | ((value & 0x33) << 2)
    return ((value & 0xAA) >> 1) | ((value & 0x55) << 1)


def checksum(data: bytes) -> int:
    """Return the game's verified CRC-32 variant.

    Parameters are width 32, polynomial 0xEDB88320, initial value 0, final
    xor 0, reflected input bytes, and no reflected output.
    """

    result = 0
    for byte in data:
        result ^= _reverse_byte(byte) << 24
        for _ in range(8):
            if result & 0x80000000:
                result = ((result << 1) & 0xFFFFFFFF) ^ 0xEDB88320
            else:
                result = (result << 1) & 0xFFFFFFFF
    return result


def stored_checksum(data: bytes, layout: Layout, section: Section) -> int:
    return int.from_bytes(
        data[section.checksum_offset : section.checksum_offset + 4],
        layout.byte_order,
    )


def duplicate_checksum(data: bytes, layout: Layout, section: Section) -> int:
    return int.from_bytes(
        data[section.duplicate_offset : section.duplicate_offset + 4],
        layout.byte_order,
    )


def computed_checksum(data: bytes, section: Section) -> int:
    return checksum(data[section.data_offset : section.data_end])


def validate(data: bytes, layout: Layout) -> list[str]:
    errors: list[str] = []
    for section in layout.sections_for_size(len(data)):
        if section.required_end > len(data):
            errors.append(f"{section.name}: section exceeds file size")
            continue
        stored = stored_checksum(data, layout, section)
        duplicate = duplicate_checksum(data, layout, section)
        computed = computed_checksum(data, section)
        if stored != duplicate:
            errors.append(
                f"{section.name}: checksum copies differ "
                f"(0x{stored:08x} != 0x{duplicate:08x})"
            )
        if section.checksum_policy == "computed" and stored != computed:
            errors.append(
                f"{section.name}: checksum mismatch "
                f"(stored 0x{stored:08x}, computed 0x{computed:08x})"
            )
        if section.checksum_policy == "zero" and stored != 0:
            errors.append(
                f"{section.name}: native PC checksum slot is not zero "
                f"(stored 0x{stored:08x})"
            )
    return errors


def update_checksum(data: bytearray, layout: Layout, section: Section) -> int:
    value = computed_checksum(data, section)
    stored_value = value if section.checksum_policy == "computed" else 0
    encoded = stored_value.to_bytes(4, layout.byte_order)
    data[section.checksum_offset : section.checksum_offset + 4] = encoded
    data[section.duplicate_offset : section.duplicate_offset + 4] = encoded
    return value


def read(path: Path, layout: Layout) -> bytes:
    data = path.read_bytes()
    errors = validate(data, layout)
    if errors:
        detail = "\n  ".join(errors)
        raise ValueError(f"{path} is not a valid {layout.name} save:\n  {detail}")
    return data
