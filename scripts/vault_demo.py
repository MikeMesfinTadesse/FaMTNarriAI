"""Read the ElevenLabs key from Vault (dev server).
Usage: VAULT_TOKEN=<read-only token> python scripts/vault_demo.py
"""
import os
import hvac

client = hvac.Client(url=os.getenv("VAULT_ADDR", "http://localhost:8200"),
                     token=os.environ["VAULT_TOKEN"])
secret = client.secrets.kv.v2.read_secret_version(
    path="famt", mount_point="secret", raise_on_deleted_version=True)
key = secret["data"]["data"]["ELEVEN_API_KEY"]
print("ElevenLabs key loaded, length:", len(key))
