"""
Azure Static Web App API endpoint to retrieve configuration securely.
"""
import azure.functions as func
import json
import os
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns configuration for the web app, including Azure Maps key from Key Vault.
    """
    logger.info('Config API endpoint called')
    
    # Get Key Vault name from environment
    kv_name = os.environ.get('KEY_VAULT_NAME')
    
    config = {
        'azureMapsKey': '',
        'storageAccountUrl': os.environ.get('STORAGE_ACCOUNT_URL', ''),
        'datasetsContainer': os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    }
    
    # Try to get Azure Maps key from Key Vault
    if kv_name:
        try:
            vault_url = f"https://{kv_name}.vault.azure.net"
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            
            # Try to get the Azure Maps key
            try:
                secret = client.get_secret('AZURE-MAPS-SUBSCRIPTION-KEY')
                config['azureMapsKey'] = secret.value
                logger.info('Retrieved Azure Maps key from Key Vault')
            except Exception as e:
                logger.warning(f'Could not retrieve Azure Maps key from Key Vault: {e}')
        except Exception as e:
            logger.error(f'Failed to connect to Key Vault: {e}')
    
    # Fallback to app settings if Key Vault fails
    if not config['azureMapsKey']:
        config['azureMapsKey'] = os.environ.get('AZURE_MAPS_SUBSCRIPTION_KEY', '')
        if config['azureMapsKey']:
            logger.info('Using Azure Maps key from app settings')
    
    return func.HttpResponse(
        body=json.dumps(config),
        mimetype='application/json',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
    )
