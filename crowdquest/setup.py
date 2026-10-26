"""Interactive local configuration. Never supply secrets in command arguments."""

import json
from getpass import getpass

from .config import ROOT, Settings, default_state_dir
from .secrets import WindowsVault


def main():
    directory = default_state_dir()
    if directory.is_relative_to(ROOT):
        raise ValueError("Private configuration must be outside the repository")
    print("Configure the Twitch application registered to your own channel.")
    print("Exact OAuth redirect: http://localhost:8000/auth/twitch/callback")
    print("Only requested scope: user:read:chat. Do not paste credentials into chat.")
    values = Settings(
        state_dir=directory,
        client_id=input("Twitch Client ID: ").strip(),
        owner_login=input("Confirmed owned test channel login: ").strip().lower(),
    )
    if not values.configured:
        raise ValueError("Client ID and owned channel are required")
    secret = getpass("Twitch Client Secret (hidden, saved to Windows Credential Manager): ")
    if not 1 <= len(secret) <= 2048:
        raise ValueError("A client secret is required")
    vault = WindowsVault(directory)
    vault.set("client-secret", secret)
    # Reconfiguration invalidates stored tokens so an old channel is never inherited.
    vault.delete("tokens")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(
        json.dumps(
            {"client_id": values.client_id, "owner_login": values.owner_login, "port": values.port},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Saved local configuration. Start CrowdQuest, then use Connect Twitch in the browser.")


if __name__ == "__main__":
    main()
