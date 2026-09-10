# Reference implementation — coming soon

The DUT-side command-set handler will be published here: a portable core
(COBS framing, CRC16-CCITT-FALSE, frame dispatch) that needs only a byte
put/get from your UART, plus one buildable example project.

It is being optimised and bench-verified first, then restructured to match
the CFS-ECIG-SUITE layer conventions (`drv_*` / `svc_*` / `app_*`) so it
reads the same way as the rest of the platform.
