"""
Test endpoint to diagnose blob storage authentication
"""
import azure.functions as func
import logging
import json
import os

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Test endpoint to diagnose authentication issues"""
    logger.info('Test endpoint called')
    
    result = {
        "status": "testing",
        "steps": []
    }
    
    # Step 1: Check environment
    storage_url = os.environ.get('STORAGE_ACCOUNT_URL', '')
    container_name = os.environ.get('STORAGE_CONTAINER_DATASETS', 'datasets')
    result["steps"].append(f"1. Storage URL: {storage_url}")
    result["steps"].append(f"2. Container: {container_name}")
    
    # Step 2: Try importing Azure SDK
    try:
        from azure.identity import ManagedIdentityCredential
        result["steps"].append("3. ✅ ManagedIdentityCredential imported")
    except Exception as e:
        result["steps"].append(f"3. ❌ ManagedIdentityCredential import failed: {e}")
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    # Step 3: Try creating credential
    try:
        credential = ManagedIdentityCredential()
        result["steps"].append("4. ✅ ManagedIdentityCredential created")
    except Exception as e:
        result["steps"].append(f"4. ❌ Credential creation failed: {e}")
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    # Step 4: Try importing BlobServiceClient
    try:
        from azure.storage.blob import BlobServiceClient
        result["steps"].append("5. ✅ BlobServiceClient imported")
    except Exception as e:
        result["steps"].append(f"5. ❌ BlobServiceClient import failed: {e}")
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    # Step 5: Try creating BlobServiceClient
    try:
        blob_service_client = BlobServiceClient(account_url=storage_url, credential=credential)
        result["steps"].append("6. ✅ BlobServiceClient created")
    except Exception as e:
        result["steps"].append(f"6. ❌ BlobServiceClient creation failed: {e}")
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    # Step 6: Try getting container client
    try:
        container_client = blob_service_client.get_container_client(container_name)
        result["steps"].append("7. ✅ Container client created")
    except Exception as e:
        result["steps"].append(f"7. ❌ Container client creation failed: {e}")
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    # Step 7: Try listing blobs (this is where auth actually happens)
    try:
        blob_list = list(container_client.list_blobs(max_results=5))
        result["steps"].append(f"8. ✅ Listed {len(blob_list)} blobs")
        result["blobs"] = [blob.name for blob in blob_list]
        result["status"] = "success"
    except Exception as e:
        result["steps"].append(f"8. ❌ Blob listing failed: {e}")
        result["error_type"] = type(e).__name__
        result["error_details"] = str(e)
        return func.HttpResponse(json.dumps(result, indent=2), mimetype='application/json', status_code=500)
    
    return func.HttpResponse(
        json.dumps(result, indent=2),
        mimetype='application/json',
        headers={'Access-Control-Allow-Origin': '*'}
    )
