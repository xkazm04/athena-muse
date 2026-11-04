"""A project's apps by kind (ADR 0025), and a device's apps offered to paired devices (ADR 0026).

- ``store``: the ``apps`` and ``app_remotes`` tables, plus the website/local_page origins that stay in
  ``spaces.apps`` (their kind is derived: a loopback host is local_page). WP1.
- ``client``: the app transports, Streamable HTTP on loopback and stdio child processes, and the probe
  that lists an app's tools with their class. WP2.
- ``tools``: the tools she is offered for a project's apps (``<slug>__<tool>``, and
  ``<slug>_on_<device>__<tool>`` for a paired device's instance) and their dispatch under
  ``app_read`` / ``app_act`` / ``app_fetch``. WP2 (local) and WP3 (remote).
- ``athena.peer.apps``: the offering device's ``/peer/apps*`` routes and the caller side. WP3.
"""
