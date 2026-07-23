# Dead Rising 2: Off the Record save converter

Convert an extracted **Story Mode** `DCSAV01.DSF` payload from the Xbox 360
version of *Dead Rising 2: Off the Record* into a native Steam PC save. The
conversion has been live-tested with a payload created and exposed by Xenia.

The converter is deliberately conservative: it validates both inputs, writes a
new file, refuses to overwrite anything, and emits a JSON audit. It never finds
or installs a live save and never launches Steam, Xenia, or the game.

## Current support

| Direction | Story Mode | Sandbox Mode |
| --- | --- | --- |
| Extracted Xbox 360-format payload to native PC | Supported | Not yet supported; omitted |
| Native PC to Xbox 360 format | Not yet supported | Not yet supported |

This is specific to *Off the Record* (Xbox title ID `4343081F`, Steam app
`45770`). It is not a universal Dead Rising or Xbox save converter. It accepts
the inner game payload, not a retail console's signed STFS package. Extract the
inner `DCSAV01.DSF` first. A retail-console payload is expected to use the same
Xbox format, but that source has not yet received an independent live test.

The Story Mode adapter completed one real end-to-end test on July 22, 2026: a
converted save loaded on PC, was overwritten by the PC game, closed cleanly,
and then reloaded with the expected progression, inventory, and controls. That
is strong evidence for the tested format, not a guarantee for every save. Keep
backups.

## Requirements

- Python 3.11 or newer; no third-party Python packages are required.
- Your own extracted Xbox 360-format `DCSAV01.DSF` payload. Xenia exposes this
  file directly; a retail Xbox 360 save must first be extracted from its signed
  STFS package. The [Xenia Canary FAQ](https://github.com/xenia-canary/xenia-canary/wiki/FAQ#how-do-i-use-xenia-vfs-dump)
  documents `xenia-vfs-dump` as one STFS-content extraction option.
- Your own **native-PC, Story-Mode-only** save to use as a platform template.
- At least one carried item in the PC template. The converter learns small
  platform-local item fields from that record instead of hard-coding a pointer
  from one executable build.

No saves, game binaries, extracted assets, keys, or third-party tools are
included in this repository.

## Install

From a checkout:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Or run directly without installation:

```sh
PYTHONPATH=src python -m dr2otr_save_converter --help
```

## Convert

First, back up both saves and disable Steam Cloud for the game while testing.
Then write the conversion to a new path:

```sh
dr2otr-save xbox-to-pc \
  --xbox-save /path/to/extracted-xbox/DCSAV01.DSF \
  --pc-template /path/to/native-pc/DCSAV01.DSF \
  --output /path/to/output/converted-DCSAV01.DSF
```

The command also writes `converted-DCSAV01.DSF.audit.json`. Neither output may
already exist. The audit records file names, sizes, hashes, schema coverage,
converted summary values, item handling, and validation results without
recording absolute input paths.

Typical source locations are:

- Xenia: `content/<profile>/4343081F/00000001/DCSAV01.DSF/DCSAV01.DSF`
- Retail Xbox 360: extract the signed STFS package and supply its inner
  `DCSAV01.DSF`. The converter does not modify, reassemble, or resign the STFS
  package.
- Proton/Steam:
  `userdata/<steam-id>/45770/remote/<gfwl-id>/DCSAV01.DSF`

Paths vary by installation. Do not copy the result over the live PC save until
you have made a separate backup. On the first test, load and inspect the result
before saving. If it looks correct, save, close the game, and reload once more
to prove that the PC game can round-trip the converted state.

## Safety behavior

- Validates the supported extracted Xbox-format payload and native-PC container
  layouts.
- Verifies section checksums and duplicate checksum fields.
- Converts only serializer-derived numeric fields.
- Preserves endian-neutral data and native-PC container/platform regions.
- Replaces ignored Xbox item runtime scratch with values learned from the PC
  template.
- Fails closed on unsupported active item contexts, unexpected sizes, a PC
  template containing Sandbox Mode, missing platform template data, or an
  existing output.
- Clears Sandbox metadata and emits a Story-Mode-only PC file.

See [docs/FORMAT.md](docs/FORMAT.md) for the technical boundary.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Tests build deterministic synthetic containers at runtime. The repository does
not use copyrighted or personal save fixtures.

## Roadmap

- Type and validate the separate 85,590-byte Sandbox payload.
- Add Sandbox conversion using a user-supplied full native-PC template.
- Research and independently validate native-PC to Xenia conversion.

Contributions should include reproducible validation without committing saves,
extracted game data, executable code, or user-specific paths.
