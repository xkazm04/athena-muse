"""Connected accounts: Gmail and Notion, sealed in a vault under the daemon's data dir (ADR 0008).

Ported from athena-portable without its MCP client and its catalog seam (`port.py`):

- `spec` and `builtin/*.json`: a connector is data, the hosts it may dial, its probe and its tools.
- `seal`: where a credential rests: DPAPI on Windows, the keyring elsewhere (the `connectors`
  extra), an owner-only file without it, memory with no data dir.
- `vault`: the one door: every outbound call, the probe that admits a credential, the switches.
- `oauth`: Google's sign-in on the person's own Google client, over a one-shot loopback listener.
- `health`: a verdict on a credential, or an attempt that reached none.
- `service`: one connector's tools under the writes switch, the allow-list and the fence; and the
  one door that sends a twin's mail to any recipient.
- `providers`: the request shapes of Gmail and Notion, pure.
- `part`: the daemon's `connectors` part, worded for the screen; `routes`: its HTTP surface.
- `_manifest` and `_fence`: the few pieces of athena-portable's contracts and fence these need.
"""

from __future__ import annotations
