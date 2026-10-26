"""Explicit Windows Credential Manager backend; no plaintext fallback."""

import hashlib
import sys


class WindowsVault:
    def __init__(self, state_dir):
        self.service = "CrowdQuestAI-" + hashlib.sha256(str(state_dir).encode()).hexdigest()[:20]

    def _backend(self):
        if sys.platform != "win32":
            raise RuntimeError("Live credentials require Windows Credential Manager")
        from keyring.backends.Windows import WinVaultKeyring

        return WinVaultKeyring()

    def get(self, name):
        try:
            return self._backend().get_password(self.service, name)
        except Exception:  # noqa: BLE001 -- never expose backend credential exceptions
            raise RuntimeError("CREDENTIAL_STORE_UNAVAILABLE") from None

    def set(self, name, value):
        try:
            self._backend().set_password(self.service, name, value)
        except Exception:  # noqa: BLE001 -- no plaintext fallback
            raise RuntimeError("CREDENTIAL_STORE_UNAVAILABLE") from None

    def delete(self, name):
        try:
            backend = self._backend()
            if backend.get_password(self.service, name) is not None:
                backend.delete_password(self.service, name)
        except Exception:  # noqa: BLE001 -- fixed safe diagnostics only
            raise RuntimeError("CREDENTIAL_STORE_UNAVAILABLE") from None
