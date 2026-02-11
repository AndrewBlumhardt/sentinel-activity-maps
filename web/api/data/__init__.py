"""
Azure Static Web App API endpoint to proxy threat intelligence data from blob storage.
Uses managed identity to access private storage account.
"""
import azure.functions as func
import logging
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import os

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns threat intelligence GeoJSON data from blob storage.
    """
    logger.info('Data API endpoint called')
    
    # Get storage configuration
    storage_url = os.environ.get('STORAGE_ACCOUNT_URL', '')
    container_name = os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    blob_name = 'threat-intel-indicators.geojson'
    
    if not storage_url:
        logger.error('STORAGE_ACCOUNT_URL not configured')
        return func.HttpResponse(
            '{"error": "Storage not configured"}',
            status_code=500,
            mimetype='application/json'
        )
    
    try:
        # Use managed identity to access blob storage
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url=storage_url, credential=credential)
        
        # Get the blob client
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        # Download the blob
        logger.info(f'Downloading blob: {container_name}/{blob_name}')
        blob_data = blob_client.download_blob()
        content = blob_data.readall()
        
        logger.info(f'Successfully retrieved {len(content)} bytes')
        
        return func.HttpResponse(
            body=content,
            mimetype='application/json',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=300',  # Cache for 5 minutes
                'Content-Type': 'application/json'
            }
        )
        
    except Exception as e:
        logger.error(f'Error retrieving blob data: {e}')
        return func.HttpResponse(
            f'{{"error": "Failed to retrieve data: {str(e)}"}}',
            status_code=500,
            mimetype='application/json',
            headers={
                'Access-Control-Allow-Origin': '*'
            }
        )
