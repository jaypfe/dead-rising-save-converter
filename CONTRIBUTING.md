# Contributing

Please open an issue before expanding the supported games, platforms, save
sections, or conversion directions. Each change needs a finite format boundary
and reproducible validation.

Never commit:

- personal or downloaded save files;
- extracted game assets or archives;
- executables, XEX images, disassembly dumps, keys, or platform credentials;
- absolute user-specific paths; or
- third-party source copied into this repository.

Tests must generate synthetic fixtures at runtime. A new conversion path should
prove, in order:

1. complete field coverage derived from serializer behavior;
2. platform-local field handling;
3. container and checksum validity;
4. load behavior in the target game; and
5. save, close, and reload behavior in the target game.

Run before submitting:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```
