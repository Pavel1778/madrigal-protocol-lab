# Synthetic live capture

A capture of a real TCP exchange on loopback, produced by the stand in
`scripts/run_synthetic_stand.py`. Unlike `corpus_capture_*`, which are built by
writing packets directly, this exchange went through a real TCP stack: a client
and a server exchanged bytes over real sockets.

## Contents

| File | Description |
| ---- | ----------- |
| `synthetic_live.pcapng` | The recorded loopback exchange, one session. |
| `synthetic_live_journal.md` | Action journal for the recorded transactions. |

## How to run it again

```
python -m scripts.run_synthetic_stand
```

The stand starts a server and a client on loopback, relays the exchange through
a recording observer, verifies the capture through the capture engine, and only
then writes the files. Nothing here needs root; it never leaves loopback.

## Protocol

Different from the generated corpus on purpose:

- the length field is little-endian, not big-endian;
- every message carries a transaction id byte;
- the command values are 0x21 read, 0x22 set, 0x23 measure.

Request: `command, txid, len_lo, len_hi, payload`.
Response: `command | 0x80, txid, len_lo, len_hi, body`.

The two datasets therefore share no byte layout, so a rule written against one
is not accidentally right for the other.

## Recording method

The usual capture tools need elevated privileges. Instead, the stand relays the
client-server exchange through a recording observer in the same process. Every
forwarded chunk is a real TCP segment; the observer notes its time and direction
and rebuilds the capture from those segments, presenting the exchange as a
single session between the client port and the server port.
