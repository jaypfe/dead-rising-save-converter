"""Extracted Xbox 360 payload to native-PC Story Mode conversion for DR2 OTR.

This module only produces a new offline artifact. It never finds or replaces a
live save, changes Steam configuration, or launches the game.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .format import (
    PC_NATIVE,
    XBOX,
    duplicate_checksum,
    read,
    stored_checksum,
    update_checksum,
    validate,
)
from .schema import (
    FIELD04_ITEM_STARTS,
    FIELD2C_ITEM_STARTS,
    FIELD30_ITEM_STARTS,
    HEADER_LENGTH,
    HEADER_SANDBOX_RANGE,
    HEADER_U32_STARTS,
    ITEM116_PLATFORM_RANGES,
    ITEM116_SIZE,
    ITEM116_STARTS,
    ITEM116_U32,
    PLAYER_LENGTH,
    PLAYER_U32_STARTS,
    STORY_END,
    STORY_U16_STARTS,
    STORY_U32_STARTS,
    convert_player_endian,
    convert_story_endian,
    schema_byte_sets,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def logical(data: bytes, section_name: str, *, xbox: bool) -> bytes:
    layout = XBOX if xbox else PC_NATIVE
    section = getattr(layout, section_name)
    if section is None:
        raise ValueError(f"{layout.name} has no {section_name} section")
    return data[section.data_offset : section.data_end]


def convert_header(xbox_header: bytes, pc_header: bytes) -> bytes:
    if len(xbox_header) != HEADER_LENGTH or len(pc_header) != HEADER_LENGTH:
        raise ValueError("unexpected header payload length")
    sandbox_start, sandbox_end = HEADER_SANDBOX_RANGE
    if pc_header[sandbox_start:sandbox_end] != bytes(sandbox_end - sandbox_start):
        raise ValueError("native PC template is not a story-only save")

    output = bytearray(xbox_header)
    for offset in HEADER_U32_STARTS:
        output[offset : offset + 4] = xbox_header[offset : offset + 4][::-1]
    # The Xbox input may contain a sandbox section.  The native template is a
    # story-only container, so retain its cleared sandbox metadata and omit the
    # separate sandbox payload rather than advertising data that is not copied.
    output[sandbox_start:sandbox_end] = pc_header[sandbox_start:sandbox_end]
    return bytes(output)


def pc_item_platform_template(pc_story: bytes) -> dict[tuple[int, int], bytes]:
    """Require one stable active-item PC value for each platform-only span."""

    result: dict[tuple[int, int], bytes] = {}
    active_starts = [start for start in FIELD2C_ITEM_STARTS if pc_story[start] == 1]
    if not active_starts:
        raise ValueError("native PC template has no active inventory item template")
    for relative_start, relative_end in ITEM116_PLATFORM_RANGES:
        values = {
            pc_story[start + relative_start : start + relative_end]
            for start in active_starts
        }
        if len(values) != 1:
            shown = ", ".join(sorted(value.hex() for value in values))
            raise ValueError(
                "native PC inventory records disagree on platform range "
                f"0x{relative_start:x}:0x{relative_end:x}: {shown}"
            )
        result[(relative_start, relative_end)] = values.pop()
    return result


def decode_item_name(record: bytes) -> str:
    # Xbox and PC both reserve one presence byte followed by a 63-byte name.
    raw = record[1:0x40].split(b"\0", 1)[0]
    return raw.decode("ascii")


def apply_item_platform_policy(
    converted_story: bytearray,
    xbox_story: bytes,
    pc_story: bytes,
) -> dict[str, object]:
    """Replace ignored Xbox runtime scratch while retaining real item state."""

    platform_template = pc_item_platform_template(pc_story)
    active_names: list[str] = []
    active_starts: list[str] = []
    inactive_starts: list[str] = []
    inventory_starts = set(FIELD2C_ITEM_STARTS)

    numeric_relative_bytes = {
        byte
        for offset in ITEM116_U32
        for byte in range(offset, offset + 4)
    }
    platform_relative_bytes = {
        byte
        for start, end in ITEM116_PLATFORM_RANGES
        for byte in range(start, end)
    }
    if numeric_relative_bytes & platform_relative_bytes:
        raise AssertionError("item numeric and platform fields overlap")

    for start in ITEM116_STARTS:
        source = xbox_story[start : start + ITEM116_SIZE]
        if len(source) != ITEM116_SIZE:
            raise ValueError(f"truncated Xbox item record at 0x{start:x}")

        if source[0] == 0:
            # Inactive records contain ignored stack/heap scratch.  Preserve a
            # same-position PC record as the ABI-safe baseline, but retain the
            # source's typed numeric defaults so semantic validation remains
            # exact even when an inactive slot carries nonzero counters.
            template = pc_story[start : start + ITEM116_SIZE]
            if len(template) != ITEM116_SIZE:
                raise ValueError(f"truncated PC item template at 0x{start:x}")
            converted_story[start : start + ITEM116_SIZE] = template
            converted_story[start] = 0
            for relative in ITEM116_U32:
                converted_story[start + relative : start + relative + 4] = source[
                    relative : relative + 4
                ][::-1]
            inactive_starts.append(f"0x{start:x}")
            continue

        if source[0] != 1:
            raise ValueError(
                f"unsupported item presence value {source[0]} at 0x{start:x}"
            )
        if start not in inventory_starts:
            context = (
                "field 0x04"
                if start in FIELD04_ITEM_STARTS
                else "field 0x30"
                if start in FIELD30_ITEM_STARTS
                else "unknown"
            )
            raise ValueError(
                f"active item record at 0x{start:x} uses unvalidated {context} context"
            )

        name = decode_item_name(source)
        if not name:
            raise ValueError(f"active item record at 0x{start:x} has no name")
        for (relative_start, relative_end), value in platform_template.items():
            converted_story[
                start + relative_start : start + relative_end
            ] = value
        active_names.append(name)
        active_starts.append(f"0x{start:x}")

    return {
        "record_count": len(ITEM116_STARTS),
        "active_count": len(active_names),
        "active_names": active_names,
        "active_starts": active_starts,
        "inactive_count": len(inactive_starts),
        "inactive_starts": inactive_starts,
        "platform_ranges_relative": [list(item) for item in ITEM116_PLATFORM_RANGES],
        "platform_template_hex": {
            f"0x{start:x}:0x{end:x}": value.hex()
            for (start, end), value in platform_template.items()
        },
    }


def convert_story(
    xbox_story: bytes,
    pc_story: bytes,
) -> tuple[bytes, dict[str, object]]:
    if len(xbox_story) != STORY_END or len(pc_story) != STORY_END:
        raise ValueError("unexpected story payload length")
    endian_only = convert_story_endian(xbox_story)
    output = bytearray(endian_only)
    item_audit = apply_item_platform_policy(output, xbox_story, pc_story)
    allowed_adjustments: set[int] = set()
    for start in ITEM116_STARTS:
        if xbox_story[start] == 0:
            allowed_adjustments.update(range(start, start + ITEM116_SIZE))
        else:
            for relative_start, relative_end in ITEM116_PLATFORM_RANGES:
                allowed_adjustments.update(
                    range(start + relative_start, start + relative_end)
                )
    adjusted = {
        offset
        for offset, (before, after) in enumerate(zip(endian_only, output, strict=True))
        if before != after
    }
    unexpected = adjusted - allowed_adjustments
    if unexpected:
        shown = ", ".join(f"0x{offset:x}" for offset in sorted(unexpected)[:20])
        raise ValueError(f"story changed outside item platform policy: {shown}")
    item_audit["adjusted_byte_count"] = len(adjusted)
    item_audit["unexpected_adjusted_bytes"] = []
    return bytes(output), item_audit


def semantic_field_check(
    section_name: str,
    xbox_payload: bytes,
    pc_payload: bytes,
    u32_starts: tuple[int, ...],
    u16_starts: tuple[int, ...] = (),
) -> None:
    for offset in u32_starts:
        xbox_value = int.from_bytes(xbox_payload[offset : offset + 4], "big")
        pc_value = int.from_bytes(pc_payload[offset : offset + 4], "little")
        if xbox_value != pc_value:
            raise ValueError(
                f"{section_name} semantic mismatch at 0x{offset:x}: "
                f"Xbox 0x{xbox_value:08x}, PC 0x{pc_value:08x}"
            )
    for offset in u16_starts:
        xbox_value = int.from_bytes(xbox_payload[offset : offset + 2], "big")
        pc_value = int.from_bytes(pc_payload[offset : offset + 2], "little")
        if xbox_value != pc_value:
            raise ValueError(
                f"{section_name} semantic mismatch at 0x{offset:x}: "
                f"Xbox 0x{xbox_value:04x}, PC 0x{pc_value:04x}"
            )


def write_new(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        if isinstance(data, str):
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                created = True
                handle.write(data)
        else:
            with path.open("xb") as handle:
                created = True
                handle.write(data)
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ConversionResult:
    data: bytes
    audit: dict[str, object]


@dataclass(frozen=True)
class WrittenConversion:
    output_path: Path
    audit_path: Path
    result: ConversionResult


def convert_xbox_to_pc(xbox_save: Path, pc_template: Path) -> ConversionResult:
    """Convert one extracted Xbox 360 payload to a native-PC Story artifact."""

    xbox_save = Path(xbox_save)
    pc_template = Path(pc_template)
    xbox_file = read(xbox_save, XBOX)
    pc_template_file = read(pc_template, PC_NATIVE)
    supported_xbox_sizes = {XBOX.story.required_end}
    if XBOX.sandbox is not None:
        supported_xbox_sizes.add(XBOX.sandbox.required_end)
    if len(xbox_file) not in supported_xbox_sizes:
        shown = ", ".join(str(size) for size in sorted(supported_xbox_sizes))
        raise ValueError(
            f"unsupported Xbox save size {len(xbox_file)}; expected {shown}"
        )
    if len(pc_template_file) != PC_NATIVE.story.required_end:
        raise ValueError(
            "native PC template must be a story-only save with no Sandbox payload"
        )

    xbox_header = logical(xbox_file, "header", xbox=True)
    xbox_player = logical(xbox_file, "player", xbox=True)
    xbox_story = logical(xbox_file, "story", xbox=True)
    pc_header = logical(pc_template_file, "header", xbox=False)
    pc_story = logical(pc_template_file, "story", xbox=False)
    if len(xbox_player) != PLAYER_LENGTH:
        raise ValueError("unexpected Xbox player payload length")

    header = convert_header(xbox_header, pc_header)
    player = convert_player_endian(xbox_player)
    story, item_audit = convert_story(xbox_story, pc_story)

    candidate = bytearray(pc_template_file)
    for name, payload in (("header", header), ("player", player), ("story", story)):
        section = getattr(PC_NATIVE, name)
        candidate[section.data_offset : section.data_end] = payload

    checksum_audit: dict[str, dict[str, str]] = {}
    for section in PC_NATIVE.sections_for_size(len(candidate)):
        computed = update_checksum(candidate, PC_NATIVE, section)
        checksum_audit[section.name] = {
            "policy": section.checksum_policy,
            "computed": f"0x{computed:08x}",
            "stored": f"0x{stored_checksum(candidate, PC_NATIVE, section):08x}",
            "duplicate": f"0x{duplicate_checksum(candidate, PC_NATIVE, section):08x}",
        }
    errors = validate(candidate, PC_NATIVE)
    if errors:
        raise ValueError(f"candidate failed native PC validation: {'; '.join(errors)}")
    if len(candidate) != len(pc_template_file):
        raise ValueError("candidate size differs from native PC template")

    final_header = logical(candidate, "header", xbox=False)
    final_player = logical(candidate, "player", xbox=False)
    final_story = logical(candidate, "story", xbox=False)
    semantic_field_check("header", xbox_header, final_header, HEADER_U32_STARTS)
    semantic_field_check("player", xbox_player, final_player, PLAYER_U32_STARTS)
    semantic_field_check(
        "story", xbox_story, final_story, STORY_U32_STARTS, STORY_U16_STARTS
    )

    allowed_changes: set[int] = set()
    for section in PC_NATIVE.sections_for_size(len(candidate)):
        allowed_changes.update(range(section.data_offset, section.data_end))
        allowed_changes.update(
            range(section.checksum_offset, section.checksum_offset + 4)
        )
        allowed_changes.update(
            range(section.duplicate_offset, section.duplicate_offset + 4)
        )
    unexpected_container_changes = [
        offset
        for offset, (before, after) in enumerate(
            zip(pc_template_file, candidate, strict=True)
        )
        if before != after and offset not in allowed_changes
    ]
    if unexpected_container_changes:
        shown = ", ".join(f"0x{offset:x}" for offset in unexpected_container_changes[:20])
        raise ValueError(f"candidate changed native PC container/platform data: {shown}")

    xbox_runtime_token = bytes.fromhex("00 a1 45 4b")
    platform_template_hex = item_audit.get("platform_template_hex")
    if not isinstance(platform_template_hex, dict):
        raise RuntimeError("item audit has no platform template")
    native_runtime_token_hex = platform_template_hex.get("0x48:0x4c")
    if not isinstance(native_runtime_token_hex, str):
        raise RuntimeError("item audit has no native runtime token")
    native_runtime_token = bytes.fromhex(native_runtime_token_hex)
    if native_runtime_token == bytes(4):
        raise ValueError("native PC item template has a null runtime token")
    runtime_start, runtime_end = ITEM116_PLATFORM_RANGES[1]
    known_xbox_item_token_records = [
        start
        for start in ITEM116_STARTS
        if final_story[start + runtime_start : start + runtime_end]
        == xbox_runtime_token
    ]
    active_item_token_records = [
        start
        for start in ITEM116_STARTS
        if xbox_story[start] == 1
        and final_story[start + runtime_start : start + runtime_end]
        == native_runtime_token
    ]
    if len(active_item_token_records) != item_audit["active_count"]:
        raise ValueError("not every active item received the native PC runtime token")
    pointer_audit = {
        "known_xbox_token_occurrences": candidate.count(xbox_runtime_token),
        "known_xbox_item_token_records": len(known_xbox_item_token_records),
        "native_runtime_token_hex": native_runtime_token.hex(),
        "native_token_occurrences": candidate.count(native_runtime_token),
        "template_native_token_occurrences": pc_template_file.count(native_runtime_token),
        "active_item_token_records": len(active_item_token_records),
    }
    if known_xbox_item_token_records:
        raise ValueError("candidate retains an Xbox runtime token in an item record")

    decoded_header = {
        "level": int.from_bytes(final_header[1:5], "little"),
        "pp": int.from_bytes(final_header[5:9], "little"),
        "money": int.from_bytes(final_header[9:13], "little"),
        "day": int.from_bytes(final_header[13:17], "little"),
        "hour": int.from_bytes(final_header[17:21], "little"),
        "minute": int.from_bytes(final_header[21:25], "little"),
    }
    if tuple(
        int.from_bytes(final_player[offset : offset + 4], "little")
        for offset in (0, 4, 8)
    ) != (decoded_header["level"], decoded_header["pp"], decoded_header["money"]):
        raise ValueError("converted player summary disagrees with converted header")

    numeric_story_bytes, raw_story_bytes = schema_byte_sets(
        STORY_U32_STARTS,
        STORY_U16_STARTS,
        STORY_END,
    )
    audit = {
        "status": "offline-validated",
        "adapter_validation": "story-mode-live-round-trip-tested",
        "warning": (
            "Back up the live save and disable Steam Cloud before manually "
            "testing this output. The tool never installs it."
        ),
        "adapter": "dead-rising-2-off-the-record-xbox360-to-native-pc",
        "adapter_version": 1,
        "inputs": {
            "xbox_save": {
                "name": xbox_save.name,
                "size": len(xbox_file),
                "sha256": sha256(xbox_file),
            },
            "pc_template": {
                "name": pc_template.name,
                "size": len(pc_template_file),
                "sha256": sha256(pc_template_file),
            },
        },
        "output": {
            "size": len(candidate),
            "sha256": sha256(candidate),
        },
        "decoded_header": decoded_header,
        "schema": {
            "header_u32": len(HEADER_U32_STARTS),
            "player_u32": len(PLAYER_U32_STARTS),
            "story_u32": len(STORY_U32_STARTS),
            "story_u16": len(STORY_U16_STARTS),
            "story_numeric_bytes": len(numeric_story_bytes),
            "story_raw_bytes": len(raw_story_bytes),
            "story_coverage": [0, STORY_END],
        },
        "items": item_audit,
        "checksums": checksum_audit,
        "pointer_safety": pointer_audit,
        "unexpected_container_changes": [],
        "native_platform_bytes_preserved": True,
        "story_converted": True,
        "sandbox_omitted": True,
        "reverse_conversion_supported": False,
    }
    return ConversionResult(bytes(candidate), audit)


def convert_and_write(
    xbox_save: Path,
    pc_template: Path,
    output_path: Path,
    audit_path: Path | None = None,
) -> WrittenConversion:
    """Convert and write two new artifacts without replacing any existing file."""

    xbox_save = Path(xbox_save).resolve()
    pc_template = Path(pc_template).resolve()
    output_path = Path(output_path).resolve()
    if audit_path is None:
        audit_path = output_path.with_name(output_path.name + ".audit.json")
    else:
        audit_path = Path(audit_path).resolve()

    if output_path == audit_path:
        raise ValueError("output and audit paths must differ")
    if output_path in {xbox_save, pc_template} or audit_path in {
        xbox_save,
        pc_template,
    }:
        raise ValueError("artifact path must not replace an input")
    for path in (output_path, audit_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing artifact: {path}")

    result = convert_xbox_to_pc(xbox_save, pc_template)
    audit = dict(result.audit)
    output_audit = result.audit.get("output")
    if not isinstance(output_audit, dict):
        raise RuntimeError("conversion audit has no output record")
    audit["output"] = {
        **output_audit,
        "name": output_path.name,
    }
    audit_text = json.dumps(audit, indent=2, sort_keys=True) + "\n"

    created_output = False
    created_audit = False
    try:
        write_new(output_path, result.data)
        created_output = True
        write_new(audit_path, audit_text)
        created_audit = True
    except Exception:
        if created_audit:
            audit_path.unlink()
        if created_output:
            output_path.unlink()
        raise

    written_result = ConversionResult(result.data, audit)
    return WrittenConversion(output_path, audit_path, written_result)
