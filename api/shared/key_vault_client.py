"""
Azure Key Vault integration for secrets management.
"""
import os
import logging
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """Client for retrieving secrets from Azure Key Vault."""
    
    def __init__(self, vault_name: Optional[str] = None):
        """
        Initialize Key Vault client.
        
        Args:
            vault_name: Name of the Key Vault (without .vault.azure.net)
        """
        self.vault_name = vault_name
        self._client = None
        
        if vault_name:
            try:
                vault_url = f"https://{vault_name}.vault.azure.net"
                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=vault_url, credential=credential)
                logger.info(f"Key Vault client initialized for {vault_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Key Vault client: {e}")
                self._client = None
    
    def get_secret(self, secret_name: str, fallback_env_var: Optional[str] = None) -> Optional[str]:
        """
        Get secret from Key Vault, with fallback to environment variable.
        
        Args:
            secret_name: Name of the secret in Key Vault
            fallback_env_var: Environment variable name to fallback to
            
        Returns:
            Secret value or None
        """
        # Try Key Vault first
        if self._client:
            try:
                secret = self._client.get_secret(secret_name)
                logger.info(f"Retrieved secret '{secret_name}' from Key Vault")
                return secret.value
            except Exception as e:
                logger.warning(f"Failed to get secret '{secret_name}' from Key Vault: {e}")
        
        # Fallback to environment variable
        if fallback_env_var:
            value = os.environ.get(fallback_env_var)
            if value:
                logger.info(f"Using secret '{secret_name}' from environment variable {fallback_env_var}")
                return value
        
        logger.warning(f"Secret '{secret_name}' not found in Key Vault or environment")
        return None
