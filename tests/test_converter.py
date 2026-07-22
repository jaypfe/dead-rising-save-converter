from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from dr2otr_save_converter.cli import main as cli_main
from dr2otr_save_converter.converter import convert_and_write, convert_xbox_to_pc
from dr2otr_save_converter.format import PC_NATIVE, XBOX, update_checksum, validate
from dr2otr_save_converter.schema import (
    FIELD2C_ITEM_STARTS,
    HEADER_SANDBOX_RANGE,
    HEADER_U32_STARTS,
    ITEM116_PLATFORM_RANGES,
    PLAYER_U32_STARTS,
    STORY_END,
    STORY_U16_STARTS,
    STORY_U32_STARTS,
)


def write_numeric(
    data: bytearray,
    base: int,
    offset: int,
    value: int,
    length: int,
    byte_order: str,
) -> None:
    data[base + offset : base + offset + length] = value.to_bytes(
        length,
        byte_order,
    )


def update_all_checksums(data: bytearray, layout: object) -> None:
    for section in layout.sections_for_size(len(data)):
        update_checksum(data, layout, section)


def build_xbox_save() -> bytes:
    assert XBOX.sandbox is not None
    data = bytearray(XBOX.sandbox.required_end)

    header_values = (8, 172716, 152400, 1, 1, 14, 0x12345678, 0x00014054)
    for offset, value in zip(HEADER_U32_STARTS, header_values, strict=True):
        write_numeric(data, XBOX.header.data_offset, offset, value, 4, "big")
    sandbox_start, sandbox_end = HEADER_SANDBOX_RANGE
    data[
        XBOX.header.data_offset + sandbox_start : XBOX.header.data_offset + sandbox_end
    ] = bytes(range(1, sandbox_end - sandbox_start + 1))

    for index, offset in enumerate(PLAYER_U32_STARTS):
        write_numeric(
            data,
            XBOX.player.data_offset,
            offset,
            (0x10203040 + index * 0x01010101) & 0xFFFFFFFF,
            4,
            "big",
        )
    for offset, value in zip((0, 4, 8), header_values[:3], strict=True):
        write_numeric(data, XBOX.player.data_offset, offset, value, 4, "big")

    for index, offset in enumerate(STORY_U32_STARTS):
        write_numeric(
            data,
            XBOX.story.data_offset,
            offset,
            (0x01020304 + index * 0x00010001) & 0xFFFFFFFF,
            4,
            "big",
        )
    for offset in STORY_U16_STARTS:
        write_numeric(data, XBOX.story.data_offset, offset, 0x1234, 2, "big")

    item_start = XBOX.story.data_offset + FIELD2C_ITEM_STARTS[0]
    data[item_start] = 1
    item_name = b"SyntheticKnifeGloves"
    data[item_start + 1 : item_start + 1 + len(item_name)] = item_name
    platform_values = (b"XBOX", bytes.fromhex("00a1454b"), b"RAW!")
    for (relative_start, relative_end), value in zip(
        ITEM116_PLATFORM_RANGES,
        platform_values,
        strict=True,
    ):
        assert len(value) == relative_end - relative_start
        data[item_start + relative_start : item_start + relative_end] = value

    data[XBOX.sandbox.data_offset : XBOX.sandbox.data_end] = bytes(
        (index * 17 + 3) & 0xFF for index in range(XBOX.sandbox.data_length)
    )
    update_all_checksums(data, XBOX)
    assert validate(data, XBOX) == []
    return bytes(data)


def build_pc_template(*, active_item: bool = True, sandbox: bool = False) -> bytes:
    if sandbox:
        assert PC_NATIVE.sandbox is not None
        size = PC_NATIVE.sandbox.required_end
    else:
        size = PC_NATIVE.story.required_end
    data = bytearray(size)
    data[PC_NATIVE.player.platform_offset : PC_NATIVE.player.platform_end] = bytes(
        [0xA5]
    ) * PC_NATIVE.player.platform_length
    data[PC_NATIVE.story.platform_offset : PC_NATIVE.story.platform_end] = bytes(
        [0x5A]
    ) * PC_NATIVE.story.platform_length

    if active_item:
        # Deliberately use a different slot than the synthetic Xbox inventory.
        # Conversion must not assume matching inventory patterns.
        item_start = PC_NATIVE.story.data_offset + FIELD2C_ITEM_STARTS[1]
        data[item_start] = 1
        name = b"NativeTemplateItem"
        data[item_start + 1 : item_start + 1 + len(name)] = name
        platform_values = (bytes(4), bytes.fromhex("12345678"), bytes(4))
        for (relative_start, relative_end), value in zip(
            ITEM116_PLATFORM_RANGES,
            platform_values,
            strict=True,
        ):
            data[item_start + relative_start : item_start + relative_end] = value

    update_all_checksums(data, PC_NATIVE)
    assert validate(data, PC_NATIVE) == []
    return bytes(data)


class ConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xbox_data = build_xbox_save()
        cls.pc_data = build_pc_template()

    def write_inputs(self, root: Path) -> tuple[Path, Path]:
        xbox = root / "xbox.DSF"
        pc = root / "pc-template.DSF"
        xbox.write_bytes(self.xbox_data)
        pc.write_bytes(self.pc_data)
        return xbox, pc

    def test_schema_totals(self) -> None:
        self.assertEqual(len(PLAYER_U32_STARTS), 331)
        self.assertEqual(len(STORY_U32_STARTS), 8765)
        self.assertEqual(len(STORY_U16_STARTS), 1)
        self.assertEqual(STORY_END, 108894)

    def test_conversion_preserves_semantics_and_omits_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            xbox_path, pc_path = self.write_inputs(Path(directory))
            result = convert_xbox_to_pc(xbox_path, pc_path)

        self.assertEqual(validate(result.data, PC_NATIVE), [])
        self.assertEqual(len(result.data), PC_NATIVE.story.required_end)
        header = result.data[
            PC_NATIVE.header.data_offset : PC_NATIVE.header.data_end
        ]
        sandbox_start, sandbox_end = HEADER_SANDBOX_RANGE
        self.assertEqual(header[sandbox_start:sandbox_end], bytes(21))
        self.assertEqual(int.from_bytes(header[1:5], "little"), 8)
        self.assertEqual(int.from_bytes(header[5:9], "little"), 172716)
        self.assertEqual(int.from_bytes(header[9:13], "little"), 152400)

        story = result.data[PC_NATIVE.story.data_offset : PC_NATIVE.story.data_end]
        item_start = FIELD2C_ITEM_STARTS[0]
        self.assertEqual(story[item_start], 1)
        self.assertEqual(
            story[item_start + 1 : item_start + 1 + len(b"SyntheticKnifeGloves")],
            b"SyntheticKnifeGloves",
        )
        self.assertEqual(
            story[item_start + 0x48 : item_start + 0x4C],
            bytes.fromhex("12345678"),
        )
        self.assertNotIn(bytes.fromhex("00a1454b"), result.data)
        self.assertEqual(result.audit["status"], "offline-validated")
        self.assertTrue(result.audit["sandbox_omitted"])
        self.assertFalse(result.audit["reverse_conversion_supported"])
        pointer_safety = result.audit["pointer_safety"]
        self.assertEqual(pointer_safety["active_item_token_records"], 1)
        self.assertEqual(pointer_safety["known_xbox_item_token_records"], 0)
        self.assertNotEqual(
            pointer_safety["native_token_occurrences"],
            pointer_safety["template_native_token_occurrences"],
        )

    def test_write_is_new_only_and_audit_avoids_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, pc_path = self.write_inputs(root)
            output = root / "converted.DSF"
            written = convert_and_write(xbox_path, pc_path, output)
            audit_text = written.audit_path.read_text(encoding="utf-8")
            audit = json.loads(audit_text)

            self.assertEqual(output.read_bytes(), written.result.data)
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(),
                audit["output"]["sha256"],
            )
            self.assertNotIn(str(root), audit_text)
            with self.assertRaises(FileExistsError):
                convert_and_write(xbox_path, pc_path, output)

    def test_refuses_input_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, pc_path = self.write_inputs(root)
            with self.assertRaises(ValueError):
                convert_and_write(xbox_path, pc_path, xbox_path)

    def test_requires_active_pc_item_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, _ = self.write_inputs(root)
            pc_path = root / "pc-empty.DSF"
            pc_path.write_bytes(build_pc_template(active_item=False))
            with self.assertRaisesRegex(ValueError, "no active inventory item"):
                convert_xbox_to_pc(xbox_path, pc_path)

    def test_accepts_story_only_xbox_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path = root / "xbox-story-only.DSF"
            xbox_path.write_bytes(self.xbox_data[: XBOX.story.required_end])
            pc_path = root / "pc-template.DSF"
            pc_path.write_bytes(self.pc_data)
            result = convert_xbox_to_pc(xbox_path, pc_path)
            self.assertEqual(validate(result.data, PC_NATIVE), [])

    def test_rejects_invalid_source_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, pc_path = self.write_inputs(root)
            damaged = bytearray(xbox_path.read_bytes())
            damaged[XBOX.story.data_offset + 0x200] ^= 0x80
            xbox_path.write_bytes(damaged)
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                convert_xbox_to_pc(xbox_path, pc_path)

    def test_refuses_full_pc_sandbox_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, _ = self.write_inputs(root)
            pc_path = root / "pc-full.DSF"
            pc_path.write_bytes(build_pc_template(sandbox=True))
            with self.assertRaisesRegex(ValueError, "story-only"):
                convert_xbox_to_pc(xbox_path, pc_path)

    def test_cli_writes_output_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xbox_path, pc_path = self.write_inputs(root)
            output = root / "cli-output.DSF"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = cli_main(
                    [
                        "xbox-to-pc",
                        "--xbox-save",
                        str(xbox_path),
                        "--pc-template",
                        str(pc_path),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(status, 0, stderr.getvalue())
            self.assertTrue(output.exists())
            self.assertTrue(Path(str(output) + ".audit.json").exists())
            self.assertIn("status=offline-validated", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
