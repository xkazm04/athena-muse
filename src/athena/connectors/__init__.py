"""Connected accounts: Gmail and Notion, sealed in a vault under the daemon's data dir (ADR 0008).

Ported from athena-portable without its MCP client (WP2): the vault and its seal (DPAPI or the
keyring), sign in with Google through a loopback flow on the person's own Google client, a pasted
Notion key, and a probe before any credential is kept. Until then each route answers 501.
"""

from __future__ import annotations
