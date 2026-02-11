"""
Health check endpoint to verify API is running and configuration is correct.
"""
import azure.functions as func
import logging
import os
import json

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns health status and configuration details.
    """
    logger.info('Health check endpoint called')
    
    # Check environment variables
    storage_url = os.environ.get('STORAGE_ACCOUNT_URL', '')
    container_name = os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    
    health_data = {
        'status': 'healthy',
        'api_version': '1.0',
        'configuration': {
            'storage_configured': bool(storage_url),
            'storage_url': storage_url if storage_url else 'NOT_SET',
            'container_name': container_name
        },
        'environment_keys': list(os.environ.keys())
    }
    
    # Try to import Azure SDK modules
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
        health_data['azure_sdk'] = 'loaded'
    except Exception as e:
        health_data['azure_sdk'] = f'error: {str(e)}'
    
    return func.HttpResponse(
        body=json.dumps(health_data, indent=2),
        mimetype='application/json',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        }
    )
