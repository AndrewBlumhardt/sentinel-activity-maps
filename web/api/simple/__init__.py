import azure.functions as func
import logging

logger = logging.getLogger(__name__)

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Simple test endpoint"""
    logger.info('Simple endpoint called')
    return func.HttpResponse(
        '{"status": "ok", "message": "Simple endpoint works"}',
        status_code=200,
        mimetype='application/json',
        headers={'Access-Control-Allow-Origin': '*'}
    )
