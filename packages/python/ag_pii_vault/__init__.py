"""
pii-vault — PII tokenization SDK and proxy for AI pipelines.

Quick start::

    from ag_pii_vault import SafeOpenAI

    client = SafeOpenAI(api_key="sk-...", vault_key="my-vault-secret")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Summarise the case for John Smith, john@acme.com"}],
    )
    # John Smith and john@acme.com never left your infrastructure.
"""

from importlib.metadata import version as _version

from .vault         import LocalVault, Vault
from .hosted_vault  import HostedVault, QuotaExceededError
from .detector      import Detector
from .tokenizer     import Tokenizer
from .providers     import SafeOpenAI, SafeAnthropic

__version__ = _version("ag-pii-vault")
__all__ = [
    "LocalVault", "Vault", "HostedVault", "QuotaExceededError",
    "Detector", "Tokenizer", "SafeOpenAI", "SafeAnthropic",
]
