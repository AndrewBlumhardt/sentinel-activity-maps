"""
Log Analytics client with Managed Identity authentication.
Executes KQL queries against Azure Monitor Log Analytics workspace.
"""
import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from azure.core.exceptions import HttpResponseError

logger = logging.getLogger(__name__)


class LogAnalyticsClient:
    """Client for querying Azure Log Analytics with Managed Identity."""
    
    def __init__(self, workspace_id: str = None):
        """
        Initialize the Log Analytics client.
        
        Args:
            workspace_id: Log Analytics workspace ID (defaults to env var)
        """
        self.workspace_id = workspace_id or os.getenv('LOG_ANALYTICS_WORKSPACE_ID')
        if not self.workspace_id:
            raise ValueError("LOG_ANALYTICS_WORKSPACE_ID must be provided or set in environment")
        
        # Use DefaultAzureCredential for flexibility (MI in Azure, Azure CLI locally)
        try:
            self.credential = DefaultAzureCredential()
            self.client = LogsQueryClient(self.credential)
            logger.info("Log Analytics client initialized with DefaultAzureCredential")
        except Exception as e:
            logger.error(f"Failed to initialize Log Analytics client: {e}")
            raise
    
    def execute_query(self, kql_query: str, timespan: timedelta = None) -> List[Dict[str, Any]]:
        """
        Execute a KQL query against the workspace.
        
        Args:
            kql_query: The KQL query to execute
            timespan: Optional timespan for the query (default: last 24 hours)
            
        Returns:
            List of result rows as dictionaries
            
        Raises:
            Exception: If query fails
        """
        if timespan is None:
            timespan = timedelta(hours=24)
        
        try:
            logger.info(f"Executing query against workspace {self.workspace_id}")
            logger.debug(f"Query: {kql_query[:200]}...")  # Log first 200 chars
            
            # Set server timeout to 10 minutes for large queries
            response = self.client.query_workspace(
                workspace_id=self.workspace_id,
                query=kql_query,
                timespan=timespan,
                server_timeout=600  # 10 minutes for large result sets
            )
            
            if response.status == LogsQueryStatus.SUCCESS:
                # Convert to list of dictionaries
                results = []
                if response.tables:
                    table = response.tables[0]
                    # Handle both column objects and string column names
                    columns = [col.name if hasattr(col, 'name') else str(col) for col in table.columns]
                    
                    for row in table.rows:
                        row_dict = {columns[i]: row[i] for i in range(len(columns))}
                        results.append(row_dict)
                    
                    logger.info(f"Query returned {len(results)} rows")
                    return results
                else:
                    logger.info("Query returned no tables")
                    return []
            
            elif response.status == LogsQueryStatus.PARTIAL:
                logger.warning(f"Query partially succeeded with error: {response.partial_error}")
                # Still return partial results if available
                results = []
                if response.partial_data and response.partial_data.tables:
                    table = response.partial_data.tables[0]
                    # Handle both column objects and string column names
                    columns = [col.name if hasattr(col, 'name') else str(col) for col in table.columns]
                    for row in table.rows:
                        row_dict = {columns[i]: row[i] for i in range(len(columns))}
                        results.append(row_dict)
                return results
            
            else:
                raise Exception(f"Query failed with status: {response.status}")
        
        except HttpResponseError as e:
            logger.error(f"HTTP error executing query: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test the connection to Log Analytics.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple test query
            test_query = "print test='connection_test'"
            response = self.client.query_workspace(
                workspace_id=self.workspace_id,
                query=test_query,
                timespan=timedelta(minutes=1)
            )
            return response.status == LogsQueryStatus.SUCCESS
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
