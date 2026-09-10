# Celfras Standard Protocol — Part I: The Standard

This part defines the wire protocol that every Celfras product implements: how
bytes are framed on the link, how a request is answered, what the core commands
are, and what an implementation has to do to be conforming. It is self-contained.
A device or a host can be written against this part alone, without access to any
product's source.

Part II is a record, not a requirement. It documents how individual products
filled in the parts this standard leaves to the product — identifier maps,
optional command groups, layer-specific error codes. Nothing in Part II relaxes
anything in Part I.

## 1. Scope

### 1.1 What this part defines

- The transport a conforming link runs on (§2).
- The frame format, its integrity check, and the receiver's validation rules (§3).
- The request/response model, the status byte, and the core error space (§4).
- Operating modes, and which commands are answered in each (§5).
- The core command set and the standardised command groups (§6, §7, §8).
- The opcode space, what is reserved, and how a product extends it (§9).
- A conformance checklist (§10).

### 1.2 What it deliberately does not define

Anything a product legitimately differs on: the identifier maps behind the
variable and parameter commands (§8), which telemetry field bits carry a real
reading (§7.2), the meaning of a tuning identifier (§6.4), and every threshold
value a product bakes in. Also, explicitly, the *implementation* of the
transport — see §2.

### 1.3 Roles

**Host** — the PC-side tool. It issues requests and consumes responses and
unsolicited frames.

**Device** — the product firmware. It answers requests and may emit unsolicited
frames.

**Bridge** — an optional relay that sits inline on the same link. It answers the
opcodes reserved to it (§9.2) and forwards everything else to the device
untouched. A bridge is transparent to a conforming host and device.

Exactly one host and one device participate in a link. A bridge, if present,
does not change the frame format in either direction.

### 1.4 Requirement language

**MUST** / **MUST NOT** — absolute requirements of this standard. An
implementation that violates one is not conforming.
**SHOULD** — a requirement that may be departed from only for a stated reason;
a product that departs records it in Part II.
**MAY** — genuinely optional.

### 1.5 Byte order and notation

All multi-byte fields are little-endian and unsigned unless a table says
otherwise. Bit 0 is the least significant bit. `u8`, `u16` and `u32` denote
unsigned integers of that width. Byte values are written in hexadecimal.

## 2. Transport

The link is asynchronous serial: 8 data bits, no parity, one stop bit, no flow
control. The default rate is 1 Mbaud. A product MAY document a different rate,
but both ends MUST agree on it out of band — nothing in the protocol negotiates
it.

The link is full duplex, and both directions carry the same frame format (§3).
The device MAY send an unsolicited frame at any time (§7); a host that cannot
tolerate one arriving between its own request and the matching response is not
conforming.

**The transport backend is not part of this standard.** Whether a device serves
its UART by DMA, by a per-byte interrupt, or by polling is an implementation
choice: nothing on the wire distinguishes them, and no host may depend on which
one is in use. The reference implementation ships a DMA backend and carries an
interrupt backend selectable at build time; the two are byte-for-byte identical
on the link, and both are conforming. Statements about ring buffers, transmit
queues, interrupt priorities or DMA channels belong to a product's own
documentation, never to this standard.

Because the framing in §3.4 is self-synchronising, a receiver MUST recover from
a truncated or corrupt frame without an out-of-band reset, and MUST accept
frames that arrive back to back with no inter-frame gap. A device MUST NOT
require an idle gap, a line break, or a preamble before a frame.

## 3. Frame format

### 3.1 The decoded frame

Every frame, in either direction, has this layout once the framing of §3.4 has
been removed:

```
[LEN u16 LE][CMD u8][SEQ u8][PAYLOAD ...][CRC16 u16 LE]
```

| Field | Width | Meaning |
|---|---|---|
| `LEN` | u16 LE | Number of bytes that follow it: `1 (CMD) + 1 (SEQ) + len(PAYLOAD) + 2 (CRC16)`. |
| `CMD` | u8 | The opcode. A response carries the same opcode as the request it answers. |
| `SEQ` | u8 | Correlation token, see §3.5. |
| `PAYLOAD` | `LEN - 4` | Command-specific, and may be empty. For a response it is always `[STATUS][DATA...]`, see §4. |
| `CRC16` | u16 LE | Integrity check, see §3.3. |

The total decoded frame length is `2 + LEN`. The shortest legal frame is
therefore six bytes: `LEN` (two) + `CMD` + `SEQ` + `CRC16` (two), with an empty
payload.

### 3.2 What LEN counts

`LEN` counts everything **after** the `LEN` field itself, and that includes the
two CRC bytes. It does **not** count itself. A receiver MUST check `LEN` against
the length it actually decoded and MUST discard any frame where the two
disagree — the check is for equality, not for a lower bound.

### 3.3 The integrity check

`CRC16` is **CRC-16/CCITT-FALSE**:

| Parameter | Value |
|---|---|
| Width | 16 bits |
| Polynomial | `0x1021` |
| Initial value | `0xFFFF` |
| Input reflected | no |
| Output reflected | no |
| Final XOR | none |

**What it covers:** the decoded frame from the first byte of `LEN` through the
last byte of `PAYLOAD`. The two CRC bytes themselves are excluded. It is
computed over the decoded frame, never over the encoded bytes of §3.4.

This is the most common interoperability mistake, and two independent things
have to be right: the CRC variant, and its coverage. Check the variant first,
against these vectors:

| Input | CRC16 |
|---|---|
| `31 32 33 34 35 36 37 38 39` (ASCII `"123456789"`) | `0x29B1` |
| `01 00` | `0x2E3E` |
| (empty) | `0xFFFF` |

`0x29B1` over `"123456789"` is the published check value for this variant. An
implementation that produces anything else has the wrong variant — reflection
and a final XOR are the usual culprits — and no adjustment of the coverage will
fix it. Once the variant is confirmed, check the coverage against the worked
frame in §3.6.

### 3.4 Framing

The decoded frame is COBS-encoded (Consistent Overhead Byte Stuffing), and a
single `0x00` byte is appended as the frame delimiter:

```
wire bytes = COBS_encode(decoded frame) + 0x00
```

COBS guarantees the encoded bytes contain no `0x00`, so the delimiter is
unambiguous. The delimiter is **not** part of the encoded data and is **not**
covered by the CRC.

A receiver MUST treat `0x00` as an unconditional frame boundary: accumulate
bytes until one arrives, decode what accumulated, then start a new frame. This
is what makes the link self-synchronising — after any corruption, the next
`0x00` restores frame alignment. A receiver MUST discard a zero-length or
otherwise undecodable accumulation rather than treating it as a frame.

### 3.5 SEQ

`SEQ` correlates a response with its request.

- A response to a request MUST echo that request's `SEQ` verbatim.
- An unsolicited device-to-host frame — one that answers no request — MUST use
  `SEQ = 0`.
- `SEQ` is opaque to the device. A device MUST NOT interpret it, validate it, or
  require it to change between requests. Allocating `SEQ` values, and detecting
  duplicates or gaps, is entirely the host's business.

A host that pipelines requests MUST use `SEQ` to match responses, and MUST NOT
assume responses arrive in the order the requests were sent.

Because `SEQ = 0` is how an unsolicited frame identifies itself, a host SHOULD
NOT issue requests with `SEQ = 0` on a link where streaming (§7) is in use: a
host-initiated stop and a device-initiated stop for the same command would
otherwise be indistinguishable (§7.2).

### 3.6 A worked frame

A complete `CMD_PING` request with `SEQ = 0x07` and no payload. Every byte below
is computed, not illustrative.

Decoded frame — six bytes:

```
04 00 01 07 E7 0D
```

| Byte(s) | Value | Field |
|---|---|---|
| 0-1 | `04 00` | `LEN` = 4 — `CMD` + `SEQ` + zero payload bytes + `CRC16` |
| 2 | `01` | `CMD` — the opcode from §6.1 |
| 3 | `07` | `SEQ` — the host's correlation token; the response echoes it |
| — | — | `PAYLOAD` — empty for this command |
| 4-5 | `E7 0D` | `CRC16` = `0x0DE7`, little-endian |

The CRC is computed over bytes 0-3, `04 00 01 07` — **including** the two `LEN`
bytes and **excluding** the two CRC bytes. An implementation that starts at
`CMD` instead gets a different value, and its frames are dropped without an
error reply (§3.7).

On the wire, after COBS encoding and the delimiter — eight bytes:

```
02 04 05 01 07 E7 0D 00
```

| Byte(s) | Value | Meaning |
|---|---|---|
| 0 | `02` | COBS group code: one non-zero byte follows, and a zero stood here |
| 1 | `04` | `LEN` low byte |
| 2 | `05` | COBS group code: four non-zero bytes follow |
| 3-6 | `01 07 E7 0D` | `CMD`, `SEQ`, `CRC16` — carried unchanged |
| 7 | `00` | Frame delimiter — not COBS data, not covered by the CRC |

Note what COBS did: the one `0x00` in the decoded frame (the `LEN` high byte)
was removed and encoded as a group boundary. That is the whole mechanism.

### 3.7 Receiver validation, in order

A receiver MUST apply these checks, in this order, and MUST discard the frame on
the first failure:

1. COBS decode succeeds and yields at least six bytes.
2. The CRC over the decoded frame, excluding its last two bytes, equals the
   `CRC16` those two bytes carry.
3. `LEN` equals the decoded length minus two.

A frame that fails any of these MUST be discarded **silently**. The device MUST
NOT answer it. The `CMD` and `SEQ` of a frame that failed its integrity check
cannot be trusted, so there is no opcode to answer under and no token to answer
with; a reply would be a guess, addressed to a request that may never have been
sent. (`ERR_BAD_CRC` in §4.3 exists for a layer that *can* attribute a bad
frame — a relay reporting on the link it forwards — not for the endpoint that
received it.)

Only after all three checks pass is the frame *accepted*. Acceptance is what
feeds the link-liveness clock of §5.3, whatever the opcode turns out to be.

## 4. Requests, responses and errors

### 4.1 The model

The protocol is request/response, with an unsolicited side channel.

- Every request the device processes produces **exactly one** response frame,
  carrying the same `CMD` and the same `SEQ`.
- A device MUST NOT answer a request twice, and MUST NOT leave a processed
  request unanswered — with one exception, the silent-drop mode of §5.2.
- Unsolicited device-to-host frames (§7) carry `SEQ = 0` and answer nothing.
- The device is not required to process requests concurrently, and a host MUST
  NOT assume it does.

### 4.2 The status byte

A response payload is always `[STATUS u8][DATA ...]`.

| STATUS | Meaning |
|---|---|
| `0x00` | OK. `DATA` is the command's result, and may be empty. |
| `0x01` | ERR. `DATA[0]` is an error code (§4.3). Further `DATA` bytes are permitted and are error-code specific. |
| `0x02` | Reserved. No conforming device emits it. |

A host MUST treat any status other than `0x00` as a failure, and MUST NOT
desynchronise on an unrecognised status value: consume the frame, report the
failure, carry on. Status `0x02` in particular is reserved rather than free —
an earlier revision of this protocol declared it as a second error status — so a
receiver has to tolerate it arriving even though nothing sends it.

A device MUST send `[0x01][error code]` rather than a bare `[0x01]`: a host
cannot distinguish a bare error from a truncated one.

### 4.3 The core error space

Error codes `0x00` to `0x0F` are the **core space**. It is defined here and
nowhere else, and it contains exactly these codes:

{{table:errors}}

A product MUST NOT define a new code in `0x00`-`0x0F`, and MUST NOT give an
existing one a second meaning. These are the codes a host can interpret without
knowing what it is talking to.

Note the shape of the two most common ones. `ERR_BAD_LEN` means the payload was
too short for the command to be executed at all, decided before any value in it
was examined. `ERR_BAD_ARGS` means the payload was long enough but something in
it was out of range, unknown, or not writable. A device MUST NOT answer
`ERR_BAD_ARGS` for a short payload or `ERR_BAD_LEN` for a bad value — a host
uses the difference to tell a mis-built frame from a mis-chosen value.

### 4.4 The extension space

Codes `0x10` and above are an **extension space**, and this standard assigns
nothing in it. A code there means whatever the layer that sent it says it means,
and it is interpretable only once the host knows which layer answered.

This is not hypothetical. The bridge layer (§9.2) uses `0x11`-`0x15` for its SWD
operations, `0x20`, `0x21` and `0xE1` for flash operations, and `0x30`-`0x35`
for its own firmware update. Those meanings are the bridge's; they are
documented with the bridge in Part II, and they say nothing about what a
different layer might assign to the same numbers. A device and a bridge on one
link can both use `0x30` for unrelated things without conflict, because the
frame says which of them answered.

Rules a product MUST follow when it needs its own error codes:

1. Allocate at `0x10` or above. Never in the core space.
2. Document the allocation in Part II, against the layer that owns it.
3. Assume nothing about numbers outside your own layer — a code is not free
   just because some other layer does not use it.

## 5. Operating modes

### 5.1 The modes

A device is always in exactly one operating mode. `CMD_SET_MODE` (§6.1) is what
changes it.

{{table:op_modes}}

A device MUST boot into `OPMODE_NORMAL`. A device MUST answer `CMD_SET_MODE`
with `ERR_BAD_ARGS` for a mode value it does not implement, rather than ignoring
it or selecting a neighbouring mode.

A reserved mode that a device accepts without acting on is still acknowledged as
OK — the acknowledgement means "the value is recognised", not "the mode did
something".

### 5.2 What NORMAL answers

`OPMODE_NORMAL` is the boot default, and it is deliberately quiet: it isolates
the device's own timing from host traffic until a host asks for it.

In `OPMODE_NORMAL` a device MUST process, and answer, exactly these commands:
`CMD_PING`, `CMD_INFO`, `CMD_GET_VERSION`, `CMD_SET_MODE`, `CMD_DBG_ONLINE` and
`CMD_RESET` (§6.1, §6.2). Every other opcode — assigned, unassigned or
unimplemented alike — MUST be **silently dropped**: no response at all, not even
an error, and no action taken.

The note against `OPMODE_NORMAL` in the mode table above abbreviates that
list; `CMD_GET_VERSION` is answered in `OPMODE_NORMAL` too, and the six
commands named here are the normative set.

This is the one place in this standard where a well-formed request goes
unanswered, and both ends have to understand it the same way. A host that gets
no answer in `OPMODE_NORMAL` has not found a broken device; it has found a
device nobody has asked to leave the boot mode. `CMD_SET_MODE` is processed in
every mode, and is the only way out.

`CMD_PING`, `CMD_INFO` and `CMD_GET_VERSION` are answered in every mode by
design: identifying a device and checking that it is alive must never require
changing its state.

### 5.3 Link liveness

While in any mode other than `OPMODE_NORMAL`, a device MUST return itself to
`OPMODE_NORMAL` if no frame is accepted (§3.7) for longer than the link-liveness
interval, `ONLINE_TIMEOUT_MS`. The timer is reset by **any** accepted frame, not
by one specific opcode.

A host that intends to stay out of `OPMODE_NORMAL` MUST therefore send
*something* within every such interval. `CMD_DBG_ONLINE` exists as the cheapest
choice — it takes no payload and does nothing else — but any accepted frame
serves.

The purpose is not liveness reporting. It is that a mode other than the boot
default may have suspended some of the device's own protective behaviour, and a
pulled cable must not leave it suspended. A conforming device MUST make the
revert unconditional: it cannot depend on the host acknowledging anything,
because the failure being defended against is the host being gone.

The interval's value is a product constant, reported in Part II.

## 6. The core command set

The tables in this section are generated from the authoritative opcode
definitions. Request and response shapes are given in the tables; the prose
gives the rules around them.

### 6.1 Identity, mode and liveness

{{table:opcodes:core}}

Every command in this group MUST be implemented by every conforming device, and
every one of them is answered in every operating mode.

- **`CMD_PING`** — the liveness probe. Its response payload is fixed text; a
  host SHOULD check the status byte rather than parse the text.
- **`CMD_INFO`** — a human-readable identity string. It is free text, and its
  content is product-defined. A host MUST NOT parse it to make a decision;
  `CMD_GET_VERSION` exists for that.
- **`CMD_SET_MODE`** — see §5.
- **`CMD_DBG_ONLINE`** — a no-op whose only effect is resetting the liveness
  timer of §5.3.
- **`CMD_GET_VERSION`** — the machine-readable identity. One opcode answers more
  than one question, through a leading selector byte, and the response echoes
  the selector so that a reply is self-describing: readable out of a log, and
  matchable by a host that pipelined both requests. Two selectors are defined by
  this standard, one for the **firmware build** on the device and one for the
  **command-set version** it implements (§9.3). A device MUST answer
  `ERR_BAD_ARGS` for a selector it does not implement, and MUST NOT answer with
  a different selector's value.

A host SHOULD read the command-set version before relying on any opcode outside
this group.

### 6.2 Device control

{{table:opcodes:device}}

`CMD_RESET` is the command in this group required of every device, and it is
answered in every mode. A device MUST send its response **before** resetting,
and MUST allow that response to leave the transmit path first; no frame follows
the reset. A host MUST treat the link as re-initialised afterwards — the device
comes back in `OPMODE_NORMAL` (§5.1).

The remaining opcodes in this group are the standardised places for a product's
own activation and heating control. A product that does not implement one MUST
answer it per §9.1 rather than acknowledging it, and MUST NOT reuse one of these
opcodes for an unrelated function.

### 6.3 Register access

{{table:opcodes:register}}

An optional group, for products that expose a peripheral or companion-chip
register file. Register addresses and their contents are entirely
product-defined. A product with no register file MUST answer this group per
§9.1.

### 6.4 Tuning

{{table:opcodes:tuning}}

An optional group for host-driven calibration, in which the device runs its real
production control algorithm under host-controlled timing so that a bench can
measure it. The standard fixes the **shape**, not the content:

- `CMD_TUNING_START` opens a session; a second one while a session is active
  MUST be refused with `ERR_NOT_READY`.
- While a session is active, the device emits report frames unsolicited at the
  requested cadence, with `SEQ = 0`, in the field layout of §7.2.
- `CMD_TUNING_END` closes a session and is **dual-purpose**, exactly as
  `CMD_LOG_BURST_STOP` is (§7.2): host-initiated, it echoes the request's `SEQ`
  and is idempotent; device-initiated — on the session's duration elapsing, or
  because the device ended the run itself — it arrives with `SEQ = 0`. A host
  MUST handle both arrival paths as the same session-ended event.
- The device MAY end a session early for its own reasons. A host MUST NOT assume
  a session runs for its full requested duration, and MUST NOT assume every
  session yields at least one report frame.
- The parameter commands in this group address a calibration table by a tuple of
  indices. Every index MUST be bounds-checked against the real dimension of the
  table it addresses, and a violation MUST be `ERR_BAD_ARGS` — never a clamp,
  and never a silent write to a neighbouring cell.

Which tuning identifiers exist, what each one sweeps, what the index tuple means
for each, and which suspensions of a product's own protective behaviour a
session implies, are all product-defined and recorded in Part II.

### 6.5 Display

{{table:opcodes:display}}

An optional group. A product with no host-controllable display answers it per
§9.1.

## 7. Log and telemetry streaming

Both mechanisms in this section send device-to-host frames that answer no
request. All of them carry `SEQ = 0` (§3.5).

### 7.1 Text log

{{table:opcodes:log}}

A pull-based handshake for free-text diagnostics, shaped so that the device's
log output cannot flood the link:

1. The host sends `CMD_LOG_START`.
2. The device acknowledges, and only then arms logging. The acknowledgement is
   queued ahead of anything that follows it, so the host always sees the ack
   before any log content.
3. The device sends the next log line as one `CMD_LOG_FRAME` carrying the text,
   followed by one `CMD_LOG_STOP`.
4. The host re-issues `CMD_LOG_START` for the next line.

A host MUST tolerate `CMD_LOG_STOP` arriving with no `CMD_LOG_FRAME` before it:
that means the device had nothing to say. A host MUST NOT assume the text is
NUL-terminated, and MUST take the payload length as authoritative.

A host MUST also tolerate a device that keeps emitting frames without a further
`CMD_LOG_START` — the disarm step is what bounds the stream to one line, and a
product may deliberately leave it armed for continuous telemetry. A host that
needs the stream to stop MUST have a way to disarm it: `CMD_SET_MODE` selecting
`OPMODE_NORMAL` always does, and a product may also expose logging as a
parameter slot (§8).

Text logging is for diagnostics. Anything sampled at a fixed cadence belongs in
§7.2 instead — text formatting and parsing at those rates is exactly the cost
the binary path exists to avoid.

### 7.2 Binary telemetry bursts

{{table:opcodes:burst}}

A fixed-width binary stream for time-series measurement.

**Starting a session.** `CMD_LOG_BURST_START` takes a field bitmask, a report
period and a duration. The period MUST lie within
`[BURST_PERIOD_MS_MIN, BURST_PERIOD_MS_MAX]`, and the duration, if non-zero,
within `[BURST_DURATION_MS_MIN, BURST_DURATION_MS_MAX]`; a value outside either
range MUST be refused with `ERR_BAD_ARGS`, not clamped. A duration of
`BURST_DURATION_MS_INFINITE` (zero) means the session runs until the host stops
it. All four bounds are protocol constants whose values are given in Part II.

**The field mask** selects up to `BURST_MAX_FIELDS` signals, one bit each, from
the standard `LOG_FIELD_*` family. Which bits a given product has wired to a
real reading is product-defined; a device MUST accept a bit it has not wired
without error and MUST report that field as zero, so that a host built against a
later product does not fail against an older one.

**Frame layout.** Each `CMD_LOG_BURST_FRAME` carries a `u32` timestamp followed
by one `u16` per bit **set in the requested mask**, in ascending bit order —
bit 0's value first, regardless of which bits are set. The mask is not repeated
in the frame: the host MUST decode using the mask it sent. A device MUST NOT
reorder the values, and MUST NOT omit one.

**Stopping.** `CMD_LOG_BURST_STOP` is dual-purpose, and this is the shape the
tuning group reuses (§6.4):

- *Host-initiated* — a request. The device stops any active session and answers
  with the request's own `SEQ`. It MUST be idempotent: stopping a session that
  is not running is OK, not an error. This is the only way to end an
  infinite-duration session, and it also cancels a finite one early.
- *Device-initiated* — unsolicited, `SEQ = 0`, sent when a non-zero duration
  elapses.

Both carry the same payload. A host MUST resolve its session state from either.

**Concurrency.** Sampling MUST NOT block command dispatch: ordinary traffic,
including the host's own stop request, has to keep flowing while a session is
active. A device that runs its sweep inside the command handler cannot be
stopped, and is not conforming.

## 8. Variables and parameters

{{table:opcodes:var_par}}

Two families of commands give indexed access to device state, in three widths
each. The distinction is what they reach:

- **`CMD_VAR*`** — the **variable** map: live runtime state. Mostly a read-only
  view of what the firmware is actually doing (state, measurements, timers,
  gauges) rather than a second copy of it, plus a small writable group of
  host-supplied inputs that stand in for something the device would otherwise
  read from its own hardware.
- **`CMD_PAR*`** — the **parameter** map: the device's configuration and
  threshold store.

Both families share one shape. `SET` takes `[id u8][value]`; `GET` takes
`[id u8]` and answers `[OK][value]`; and the value is a `u8`, `u16` or `u32`,
little-endian, according to the command's width. The three widths are three
separate identifier spaces — `id 3` of the 8-bit space and `id 3` of the 16-bit
space are unrelated slots.

Required behaviour:

- An `id` at or beyond the width's table size MUST be answered `ERR_BAD_ARGS`,
  before any dispatch is attempted.
- A `SET` to a read-only slot MUST be answered `ERR_BAD_ARGS`. It MUST NOT store
  the value, and MUST NOT answer OK — a host cannot tell a silently ignored
  write from a successful one.
- A `SET` with a value outside the slot's accepted range MUST be answered
  `ERR_BAD_ARGS`. A device MUST NOT mask or clamp the value into range: a host
  asking for something impossible has a bug, and a clamp hands it
  plausible-looking readings instead of the error that would surface it.
- A writable slot MUST be backed by real storage that the device reads back. A
  slot that reads through to state it does not own MUST reject `SET`.

### 8.1 The identifier maps are product-defined, and this is load-bearing

This standard defines the commands, the widths and the error behaviour. It does
**not** define which slot number means which quantity. Those maps are assigned
per product, and are recorded in Part II.

They are **not** portable between products, and the protocol cannot defend
against using the wrong one. A slot number valid on one product is very likely
valid on another and addresses a completely different field — so the device
performs the wrong write and answers **OK**. There is no error to observe, at
any layer. Therefore:

- A host MUST establish which product, and which command-set version, it is
  talking to (`CMD_INFO`, `CMD_GET_VERSION`) before issuing any `VAR`/`PAR`
  access, and MUST use that product's own map.
- A product MUST assign new slots by appending. Renumbering an existing slot
  changes what an unchanged host writes, and is a MAJOR command-set change
  (§9.3).

## 9. Opcode space, reservations and evolution

### 9.1 Unassigned and unimplemented opcodes

Outside `OPMODE_NORMAL`, a device MUST answer **every** opcode it does not act
on with `[ERR][ERR_BAD_ARGS]`. That covers both cases equally: an opcode this
standard has not assigned, and one it has assigned that this product does not
implement. Silence is not a conforming answer — a host has to be able to tell an
unsupported command from a dead link.

The single exception is the silent-drop behaviour of `OPMODE_NORMAL` (§5.2).

`ERR_UNKNOWN` exists in the core error space for this purpose, and a device MAY
use it where it can distinguish an unrecognised opcode from a bad argument. A
host MUST accept either code as "this device will not do that".

### 9.2 Band reservation

The opcode byte is split into two bands, and the split is what lets one physical
link carry two conversations:

| Band | Owner |
|---|---|
| `0x00`-`0xBF` | The device (the product firmware). New commands grow upward within it. |
| `0xC0`-`0xFF` | **Reserved to the bridge layer.** A product MUST NOT define a command here. |

A bridge routes on the opcode byte alone: at `0xC0` and above it answers the
frame itself, and below `0xC0` it forwards the original encoded bytes to the
device untouched. A product command defined at `0xC0` or above would therefore
be unreachable whenever a bridge is inline — and the failure is silent. There is
no error to observe: the bridge consumes the frame and answers it, the device
never sees it, and the host gets a plausible reply from the wrong device.

The reservation is one band for the whole layer, not one board's band. Every
bridge implementation declares the same table.

Within the device's own band, opcodes are grouped, and a product SHOULD place a
new command in the group that matches its function:

| Base | Group |
|---|---|
| `0x00` | Identity, mode, liveness (§6.1) |
| `0x10` | Device control (§6.2) |
| `0x20` | Register access (§6.3) |
| `0x30` | Text log (§7.1) |
| `0x40` | Binary telemetry (§7.2) |
| `0x50` | Variables and parameters (§8) |
| `0x60` | Display (§6.5) |
| `0x70` | Tuning (§6.4) |

### 9.3 Versioning

The **command-set version** is a `MAJOR.MINOR.PATCH` triple naming this
standard's opcode map — the whole map, both bands. It is not any firmware's
build number, and it moves independently of one.

- **MAJOR** changes when an existing opcode changes its number or its meaning. A
  host built against the older table would otherwise reach a different handler
  and get a plausible answer, which is precisely the failure the version exists
  to make detectable.
- **MINOR** changes when opcodes are added and every existing one still means
  what it did.
- **PATCH** is for changes with no effect on the wire.

Every implementation on a link — device firmware, bridge firmware, host tool —
reports the same command-set version, and a difference between any two of them
is a mispaired system, not a tolerable skew. A host SHOULD read it
(`CMD_GET_VERSION` with the command-set selector, §6.1) before relying on any
opcode outside §6.1, and SHOULD refuse to proceed on a MAJOR mismatch.

Where a version number is duplicated — and it always is, across firmwares and
host tools in more than one repository — every copy has to be counted and moved
together. Part II lists the copies for the products it covers.

## 10. Conformance checklist

A conforming **device** answers yes to all of these.

**Transport and framing**

| Item | Requirement | See |
|---|---|---|
| 1 | The serial link is 8 data bits, no parity, one stop bit, no flow control, at the agreed rate. | 2 |
| 2 | No inter-frame gap, break or preamble is required of the host, and back-to-back frames are accepted. | 2 |
| 3 | Every frame is COBS-encoded with a trailing `0x00` delimiter, and `0x00` is treated as an unconditional frame boundary on receive. | 3.4 |
| 4 | `LEN` counts `CMD` + `SEQ` + payload + CRC, and is checked for equality against the decoded length. | 3.2 |
| 5 | The CRC is CRC-16/CCITT-FALSE and reproduces `0x29B1` over `"123456789"`. | 3.3 |
| 6 | The CRC covers the decoded frame from the first `LEN` byte through the last payload byte, and excludes the CRC bytes themselves. | 3.3 |
| 7 | A frame failing COBS decode, the CRC check or the `LEN` check is discarded silently, with no response. | 3.7 |

**Requests and responses**

| Item | Requirement | See |
|---|---|---|
| 8 | Each processed request produces exactly one response, echoing its `CMD` and its `SEQ`. | 4.1 |
| 9 | Unsolicited frames carry `SEQ = 0`. | 3.5 |
| 10 | `SEQ` is never interpreted or validated by the device. | 3.5 |
| 11 | Every response payload begins with a status byte, and an error response carries an error code in `DATA[0]`. | 4.2 |
| 12 | Core error codes are used only for core conditions, and any product-specific code is at `0x10` or above. | 4.3, 4.4 |
| 13 | `ERR_BAD_LEN` is used for a short payload and `ERR_BAD_ARGS` for a bad value, never interchangeably. | 4.3 |

**Modes**

| Item | Requirement | See |
|---|---|---|
| 14 | The device boots into `OPMODE_NORMAL`. | 5.1 |
| 15 | `CMD_SET_MODE` is processed in every mode, and an unimplemented mode value is refused with `ERR_BAD_ARGS`. | 5.1 |
| 16 | In `OPMODE_NORMAL`, `CMD_PING`, `CMD_INFO`, `CMD_GET_VERSION`, `CMD_SET_MODE`, `CMD_DBG_ONLINE` and `CMD_RESET` are answered, and everything else is dropped silently. | 5.2 |
| 17 | Any non-default mode reverts to `OPMODE_NORMAL` after `ONLINE_TIMEOUT_MS` with no accepted frame, unconditionally. | 5.3 |

**Commands**

| Item | Requirement | See |
|---|---|---|
| 18 | Every command in §6.1 is implemented, and answered in every mode. | 6.1 |
| 19 | `CMD_GET_VERSION` echoes its selector, answers `ERR_BAD_ARGS` for a selector it does not implement, and reports the version of §9.3 under the command-set selector. | 6.1 |
| 20 | `CMD_RESET` responds before resetting. | 6.2 |
| 21 | Every opcode the device does not act on is answered `[ERR][ERR_BAD_ARGS]` outside `OPMODE_NORMAL`. | 9.1 |
| 22 | No command is defined at `0xC0` or above. | 9.2 |

**Streaming**

| Item | Requirement | See |
|---|---|---|
| 23 | Log frames and telemetry frames are emitted with `SEQ = 0`. | 7 |
| 24 | A burst period or duration outside its permitted range is refused with `ERR_BAD_ARGS`, not clamped. | 7.2 |
| 25 | A burst frame carries one `u16` per set mask bit, in ascending bit order, and an unwired bit reports zero rather than erroring. | 7.2 |
| 26 | A stop or end command is idempotent, echoes the request's `SEQ` when host-initiated, and is also emitted unsolicited with `SEQ = 0` when the device ends the session itself. | 6.4, 7.2 |
| 27 | Command dispatch keeps working while a streaming session is active. | 7.2 |

**Variables and parameters**

| Item | Requirement | See |
|---|---|---|
| 28 | An out-of-range identifier is refused with `ERR_BAD_ARGS`. | 8 |
| 29 | A write to a read-only slot is refused with `ERR_BAD_ARGS` and stores nothing. | 8 |
| 30 | An out-of-range value is refused, never clamped or masked. | 8 |
| 31 | Slot numbering is append-only, and any renumbering is accompanied by a MAJOR command-set version change. | 8.1, 9.3 |

A conforming **host** additionally answers yes to these.

| Item | Requirement | See |
|---|---|---|
| 32 | It matches responses by `SEQ`, and does not assume request ordering. | 3.5 |
| 33 | It tolerates an unsolicited frame arriving at any time, including between its own request and the matching response. | 2, 7 |
| 34 | It tolerates an unrecognised status byte without losing frame synchronisation. | 4.2 |
| 35 | It reads the device's identity and command-set version before using any identifier map, and uses that product's own map. | 8.1 |
