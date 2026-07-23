# Format and conversion boundary

The converter's Xbox input is the inner game-owned `DCSAV01.DSF` payload. Xenia
exposes this payload as a normal host file. A save copied from a retail Xbox 360
is normally wrapped in a signed STFS package; version 0.1 does not extract,
reassemble, or resign that outer package.

The extracted Xbox-format and native-PC files contain the same logical header,
player, and Story Mode payloads in different game-level containers. Xbox
numeric serializer fields are big-endian; PC fields are little-endian. Raw
flags, strings, padding, and opaque byte arrays are not globally byte-swapped.
The source format has been live-tested through Xenia. An inner payload extracted
from retail hardware is expected to have the same structure, but has not yet
received an independent live test.

The supported Story Mode schema covers:

- 57-byte header: eight `u32` fields plus raw metadata.
- 2,065-byte player payload: 331 `u32` fields and 741 endian-neutral bytes.
- 108,894-byte Story payload: 8,765 `u32` fields, one `u16` field, and 73,832
  endian-neutral bytes.

The embedded Story table is a compressed list of numeric field offsets. Its
decoded table has an integrity hash checked at import time. It was derived from
serializer behavior and contains no game content.

## Item records

A common 116-byte item record contains ten numeric fields. Three four-byte
ranges are platform-local rather than portable. Inactive records can also hold
ignored runtime scratch. The converter therefore:

1. endian-converts the proven numeric fields;
2. uses same-position PC records for inactive-slot ABI data;
3. learns the three platform-local values from active items in the user's PC
   template; and
4. fails closed if an active item appears in a component context not covered by
   the live-tested policy.

## Native-PC template

The template supplies the PC container, platform blocks, and item runtime data.
It must be a native Steam PC save containing Story Mode but no Sandbox payload.
The output retains the template's container/platform bytes and replaces only
the header, player, Story data, and their checksum fields.

## Unsupported sections

Sandbox Mode is a separate 85,590-byte payload with independent checksum and
header metadata. Its schema has not yet received the same field-by-field and
live round-trip validation, so version 0.1 clears Sandbox metadata and omits the
payload.

Reverse conversion is also intentionally absent. Reversing byte order alone is
not enough: an Xbox/Xenia output needs its own validated platform-template
policy, container assembly, and live save/reload proof.
