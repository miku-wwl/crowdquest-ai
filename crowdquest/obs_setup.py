"""Interactive private configuration. Never reads or changes OBS security settings."""

import sys
import warnings
from getpass import GetPassWarning, getpass

from .obs import admin_directory
from .secrets import WindowsVault


def main():
    if not sys.stdin.isatty():
        print("INTERACTIVE_TERMINAL_REQUIRED. Run setup yourself in a private local terminal.")
        return 1
    print("OBS must already have WebSocket v5 and authentication enabled by you.")
    print("These credentials are separate from Twitch and AIG. Inputs are hidden.")
    vault = WindowsVault(admin_directory())
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Existing OBS WebSocket password: ")
            admin = getpass("Choose a separate local Admin passphrase (16-256 characters): ")
            confirmation = getpass("Confirm Admin passphrase: ")
    except (GetPassWarning, EOFError, KeyboardInterrupt):
        print("HIDDEN_INPUT_UNAVAILABLE. Nothing was saved.")
        return 1
    if not password or not 16 <= len(admin) <= 256 or admin != confirmation or admin == password:
        print(
            "Configuration rejected: use a nonempty OBS password and a distinct matching Admin passphrase."
        )
        return 1
    try:
        vault.set("obs_ws_password", password)
        vault.set("admin_password", admin)
    except RuntimeError:
        print("CREDENTIAL_STORE_UNAVAILABLE. No plaintext fallback is permitted.")
        return 1
    print("Saved to Windows Credential Manager. Start a new server process to load configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
