"""
Azure Blob Storage client with Managed Identity authentication.
Handles reading/writing TSV files, metadata, and blob-based locking.
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

logger = logging.getLogger(__name__)


class BlobStorageClient:
    """Client for Azure Blob Storage operations with locking support."""
    
    def __init__(self, account_url: str = None, datasets_container: str = None, locks_container: str = None):
        """
        Initialize the Blob Storage client.
        
        Args:
            account_url: Storage account URL (defaults to env var)
            datasets_container: Container for dataset files (defaults to env var)
            locks_container: Container for lock/metadata files (defaults to env var)
        """
        self.account_url = account_url or os.getenv('STORAGE_ACCOUNT_URL')
        self.datasets_container = datasets_container or os.getenv('STORAGE_CONTAINER_DATASETS', 'datasets')
        self.locks_container = locks_container or os.getenv('STORAGE_CONTAINER_LOCKS', 'locks')
        
        if not self.account_url:
            raise ValueError("STORAGE_ACCOUNT_URL must be provided or set in environment")
        
        # Use DefaultAzureCredential for MI authentication
        try:
            self.credential = DefaultAzureCredential()
            self.service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=self.credential
            )
            logger.info(f"Blob Storage client initialized for {self.account_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Blob Storage client: {e}")
            raise
    
    def write_tsv(self, filename: str, content: str) -> None:
        """
        Write TSV content to blob storage.
        
        Args:
            filename: Name of the file (e.g., 'signin-failures.tsv')
            content: TSV content as string
        """
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.datasets_container,
                blob=filename
            )
            
            # Set content type for TSV
            content_settings = ContentSettings(content_type='text/tab-separated-values')
            
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )
            
            logger.info(f"Successfully wrote {len(content)} bytes to {filename}")
        except Exception as e:
            logger.error(f"Failed to write TSV to {filename}: {e}")
            raise
    
    def read_tsv(self, filename: str) -> Optional[str]:
        """
        Read TSV content from blob storage.
        
        Args:
            filename: Name of the file to read
            
        Returns:
            TSV content as string, or None if not found
        """
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.datasets_container,
                blob=filename
            )
            
            downloader = blob_client.download_blob()
            content = downloader.readall().decode('utf-8')
            
            logger.info(f"Successfully read {len(content)} bytes from {filename}")
            return content
        except ResourceNotFoundError:
            logger.warning(f"File {filename} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to read TSV from {filename}: {e}")
            raise
    
    def write_metadata(self, source_id: str, metadata: Dict[str, Any]) -> None:
        """
        Write metadata JSON for a data source.
        
        Args:
            source_id: Data source identifier
            metadata: Metadata dictionary to write
        """
        filename = f"{source_id}-metadata.json"
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.locks_container,
                blob=filename
            )
            
            content = json.dumps(metadata, indent=2, default=str)
            content_settings = ContentSettings(content_type='application/json')
            
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )
            
            logger.info(f"Successfully wrote metadata for {source_id}")
        except Exception as e:
            logger.error(f"Failed to write metadata for {source_id}: {e}")
            raise
    
    def read_metadata(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Read metadata JSON for a data source.
        
        Args:
            source_id: Data source identifier
            
        Returns:
            Metadata dictionary, or None if not found
        """
        filename = f"{source_id}-metadata.json"
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.locks_container,
                blob=filename
            )
            
            downloader = blob_client.download_blob()
            content = downloader.readall().decode('utf-8')
            metadata = json.loads(content)
            
            logger.info(f"Successfully read metadata for {source_id}")
            return metadata
        except ResourceNotFoundError:
            logger.info(f"Metadata for {source_id} not found (first run)")
            return None
        except Exception as e:
            logger.error(f"Failed to read metadata for {source_id}: {e}")
            raise
    
    def acquire_lock(self, source_id: str, lease_duration: int = 60) -> Optional[str]:
        """
        Acquire a blob lease as a distributed lock.
        
        Args:
            source_id: Data source identifier
            lease_duration: Lease duration in seconds (15-60, or -1 for infinite)
            
        Returns:
            Lease ID if acquired, None if already locked
        """
        lock_filename = f"{source_id}.lock"
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.locks_container,
                blob=lock_filename
            )
            
            # Create lock blob if it doesn't exist
            try:
                blob_client.upload_blob(b"", overwrite=False)
            except ResourceExistsError:
                pass  # Blob already exists
            
            # Try to acquire lease
            lease_client = blob_client.acquire_lease(lease_duration)
            lease_id = lease_client.id
            
            logger.info(f"Acquired lock for {source_id} (lease: {lease_id})")
            return lease_id
        
        except Exception as e:
            logger.warning(f"Failed to acquire lock for {source_id}: {e}")
            return None
    
    def release_lock(self, source_id: str, lease_id: str) -> bool:
        """
        Release a blob lease lock.
        
        Args:
            source_id: Data source identifier
            lease_id: Lease ID to release
            
        Returns:
            True if released successfully
        """
        lock_filename = f"{source_id}.lock"
        try:
            blob_client = self.service_client.get_blob_client(
                container=self.locks_container,
                blob=lock_filename
            )
            
            lease_client = blob_client.from_blob_lease(lease_id)
            lease_client.release()
            
            logger.info(f"Released lock for {source_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to release lock for {source_id}: {e}")
            return False
