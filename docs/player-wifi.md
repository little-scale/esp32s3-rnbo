# Player Wi-Fi

> **Current intake:** create C++ with Max’s [Minimal Export](native-export.md), then compile/package it in Studio. `.rnbopat` is drawing data only. Hardware interfaces below are retained; earlier patch/compiler measurements apply only to their recorded builds.

RNBO Studio can provision a stable player over USB, then use an authenticated
connection on the local network for package loads and live controls. Player
installation and updates still require USB. There is one self-contained Main
patch; effects stay inside it. See the [Studio instructions](../host/studio/README.md)
for installation, compilation and package loading.

## Setup

1. In Studio, install/update the matching player over USB, then connect using USB.
2. Open **Wi-Fi setup · via USB** and choose **Scan nearby networks**. Audio pauses
   during the scan. It returns at most 24 visible, unique UTF-8 network names,
   strongest first. Scanning does not save settings or join a network.
3. Select a personal/open network, enter its password, and choose **Save Wi-Fi &
   pair**. Hidden UTF-8 names can be entered manually. Enterprise, WEP, WAPI and
   other unsupported authentication forms are excluded from scan results;
   unrepresentable/control-character names are skipped.
4. Wait for a connected status and address. Select the saved player under
   **Wi-Fi**, then connect. Keep the board powered when disconnecting USB.

Studio generates a random 32-byte pairing key. Network credentials travel over
USB only; the password is cleared from the page after sending. The board saves
its credentials and key in a player-owned NVS blob. Studio keeps the pairing key
and numeric address privately under ignored `build/private/studio/`, without
saving the network name or password on the computer. Credentials and keys are
not returned in player status or included in public evidence.

The computer and board need a reachable local IPv4 connection. Studio uses the
saved private address; it does not discover players across the network. If DHCP
changes the address, use **IP address override**, or connect over USB to refresh
the pairing. **Forget Wi-Fi** requires USB and removes the board settings and
that player's local pairing. It does not erase saved Main packages.

## Transport and security

The player listens on TCP port **8789**, serving one client at a time. This is
station mode only: there is no setup access point or Internet service. HMAC-SHA256
authenticates commands and replies and binds them to fresh server/client nonces
and ordered sequence numbers. It provides integrity and replay protection,
**not encryption**. Package contents, metadata and controls remain observable to
someone able to inspect network traffic. Use a trusted LAN; do not expose the
port to the Internet. Native packages remain trusted executable code, without
memory isolation.

Each connection begins with a JSON hello containing `protocol:"rnbo-wifi-v1"`,
`nonce` and `device_id`. The server nonce is 32 random bytes expressed as 64
lowercase hex characters. The client supplies its own fresh nonce:

```text
{client_nonce, auth}
auth = HMAC-SHA256(key, UTF8("RNBO-WIFI1 AUTH " + server_nonce + " " + client_nonce))
```

After `{"authenticated":true}`, requests use `{seq,command,mac}` with consecutive
integer sequences starting at 1. Replies use `{seq,response,mac}`; `response` is
the exact JSON reply text carried as a JSON string. MACs cover these exact UTF-8
messages and are encoded as lowercase hex:

```text
RNBO-WIFI1 REQUEST <server_nonce> <client_nonce> <decimal_seq> <command>
RNBO-WIFI1 RESPONSE <server_nonce> <client_nonce> <decimal_seq> <response>
```

Commands are printable ASCII, at most 8,191 bytes before the newline. Framing,
JSON fields, sequences and MACs are checked before dispatch. Invalid input closes
the connection. Nonce and sequence binding prevents reuse of an earlier session;
the fresh client nonce also prevents replaying an entire old server transcript
to the host. MAC comparisons use a constant-time digest comparison.

Wi-Fi scan, setup and forget are USB-only commands. Package transfers retain
their transport/session owner until completion, abort or timeout. The network
task queues commands to the control owner; it does not run DSP or manipulate a
live image. A timed-out mutating command is not automatically repeated. Reconnect
and inspect the saved/running identity before deciding to retry.

## Audio and recovery

Credential writes, scans, driver startup and package maintenance occur while the
audio/DMA owner is parked. Wi-Fi driver storage is RAM, driver NVS is disabled,
and PHY calibration storage is disabled. Only the explicit provisioning operation
writes the credential blob. Unconfigured boot loads no radio driver or TCP task.
When boot is verifying a Main, saved Wi-Fi waits until that preparation guard
clears through healthy audio blocks; an empty player has no Main verification to
wait for. Radio startup is kept outside the unverified Main's guard window.
Reconnect attempts use a bounded backoff. Network work is on core 0; it does not
establish real-time audio headroom or gapless replacement.

An early configured-player trial repeatedly overflowed the **2,304-byte
`sys_evt` stack** while retrying a disconnected network. That fault is retained.
The correction reduces the application Wi-Fi event callback to a small scalar
mailbox update, moves formatting/socket work out of the event task, and reserves
**8,192 bytes** for the system event task. The compiled application callback has
a 32-byte local frame and only critical-section entry/exit calls; this is not a
bound on the complete system handler chain.

The corrected XIAO image has complete application readback and running-identity
verification. A 35-sample, 34.5-second observation of repeated connection failures
recorded no reboot or DSP fault, and the temporary test settings were removed.
Actual on-board scans succeeded, with three networks visible in the final Studio
trial. The running package remained active through maintenance. The AMOLED image
compiles; its device trial remains pending.

A real network association and pairing subsequently passed. The current `bbb`
package was reloaded using authenticated Wi-Fi with **no USB serial handles
open**: its generation advanced, package/source identity matched, audio frames
advanced and player firmware identity stayed unchanged. The USB cable supplied
power; physically disconnecting that power cable was not part of this test.
Wireless volume and state-preserving Pause/Resume passed, and an incorrect
pairing key was rejected. Audio was left muted for overnight work.

The sanitized [Wi-Fi evidence](../evidence/player-wifi.json) records these gates
separately. No AMOLED network execution, encrypted transport or exhaustive
power-interruption claim is made.
