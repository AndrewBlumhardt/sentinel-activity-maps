"""
Azure Static Web App API endpoint to proxy threat intelligence data from blob storage.
Uses managed identity to access private storage account.
"""
import azure.functions as func
import logging
import json
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
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
    storage_url = os.environ.get('STORAGE_ACCOUNT_URL', '')
    container_name = os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    
    if not storage_url:
        logger.error('STORAGE_ACCOUNT_URL not configured')
        return func.HttpResponse(
            '{"error": "Storage not configured"}',
            status_code=500,
            mimetype='application/json'
        )
    
    try:
        # Use managed identity to access blob storage
        logger.info(f'Creating blob service client for {storage_url}')
        
        # Step 1: Create credential
        try:
            credential = ManagedIdentityCredential()
            logger.info('✅ Step 1: ManagedIdentityCredential created')
        except Exception as e:
            error_msg = f'❌ Step 1 FAILED: ManagedIdentityCredential creation - {type(e).__name__}: {str(e)}'
            logger.error(error_msg)
            return func.HttpResponse(
                json.dumps({"error": error_msg, "step": 1}),
                status_code=500,
                mimetype='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )
        
        # Step 2: Create BlobServiceClient
        try:
            blob_service_client = BlobServiceClient(account_url=storage_url, credential=credential)
            logger.info('✅ Step 2: BlobServiceClient created')
        except Exception as e:
            error_msg = f'❌ Step 2 FAILED: BlobServiceClient creation - {type(e).__name__}: {str(e)}'
            logger.error(error_msg)
          Step 3: Get blob client
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        logger.info(f'✅ Step 3: Blob client created for {container_name}/{blob_name}')
        
        # Step 4: Check if blob exists (this is where auth actually happens)
        logger.info('Step 4: Checking if blob exists (authenticating)...')
        try:
            exists = blob_client.exists()
            logger.info(f'✅ Step 4: Blob exists check result: {exists}')
        except Exception as e:
            error_msg = f'❌ Step 4 FAILED: Authentication/exists check - {type(e).__name__}: {str(e)}'
            logger.error(error_msg)
            return func.HttpResponse(
                json.dumps({
                    "error": error_msg,
                    "step": 4,
                    "hint": "This usually means managed identity doesn't have Storage Blob Data Reader role or role hasn't propagated yet"
                }),
                status_code=500,
                mimetype='application/json',
                headers={'Access-Control-Allow-Origin': '*'}
            )f blob exists
        logger.info('Checking if blob exists...')
        try:
            exists = blob_client.exists()
            logger.info(f'Blob exists check result: {exists}')
        except Exception as e:
            logger.error(f'Failed to check if blob exists: {e}')
            raise
            
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
