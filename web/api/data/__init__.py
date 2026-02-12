"""
Azure Static Web App API endpoint to proxy threat intelligence data from blob storage.
Uses connection string (SWA managed identity has limitations with Python Azure SDK).
"""
import azure.functions as func
import logging
import json
from azure.storage.blob import BlobServiceClient
import os

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns threat intelligence GeoJSON data from blob storage.
    Route parameter 'filename' determines which file to fetch.
    """
    logger.info(f'Data API endpoint called: {req.method}')
    
    # Handle CORS preflight  
    if req.method == 'OPTIONS':
        return func.HttpResponse(
            status_code=200,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
    
    # Get filename from route parameter
    filename = req.route_params.get('filename')
    if not filename:
        return func.HttpResponse(
            '{"error": "No filename specified"}',
            status_code=400,
            mimetype='application/json'
        )
    
    # Add .geojson extension if not present
    if not filename.endswith('.geojson'):
        blob_name = f'{filename}.geojson'
    else:
        blob_name = filename
    
    logger.info(f'Requesting blob: {blob_name}')
    
    # Get storage configuration
    # Note: SWA managed identity has limitations with azure-identity Python SDK
    # Using connection string is more reliable in SWA environment
    connection_string = os.environ.get('STORAGE_CONNECTION_STRING', '')
    container_name = os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    
    if not connection_string:
        logger.error('STORAGE_CONNECTION_STRING not configured')
        return func.HttpResponse(
            json.dumps({"error": "Storage not configured - STORAGE_CONNECTION_STRING missing"}),
            status_code=500,
            mimetype='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    try:
        # Create BlobServiceClient with connection string
        logger.info(f'Creating blob service client for container: {container_name}')
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        logger.info('✅ BlobServiceClient created')
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        logger.info(f'✅ Blob client created for {container_name}/{blob_name}')
        
        # Check if blob exists
        logger.info('Checking if blob exists...')
        exists = blob_client.exists()
        logger.info(f'✅ Blob exists: {exists}')
            
        if not exists:
            # List available blobs to help with debugging
            logger.info('Blob not found, listing available blobs...')
            try:
                container_client = blob_service_client.get_container_client(container_name)
                blobs = [blob.name for blob in container_client.list_blobs()]
                logger.error(f'Blob not found: {blob_name}. Available blobs: {blobs}')
                return func.HttpResponse(
                    f'{{"error": "File not found: {blob_name}", "available_files": {json.dumps(blobs)}}}',
                    status_code=404,
                    mimetype='application/json',
                    headers={'Access-Control-Allow-Origin': '*'}
                )
            except Exception as e:
                logger.error(f'Failed to list blobs: {e}')
                return func.HttpResponse(
                    f'{{"error": "File not found: {blob_name}", "list_error": "{str(e)}"}}',
                    status_code=404,
                    mimetype='application/json',
                    headers={'Access-Control-Allow-Origin': '*'}
                )
        
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
