"""
TSV writer for structured data export.
Handles formatting of query results into tab-separated values.
"""
import io
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TSVWriter:
    """Writes query results to TSV format."""
    
    @staticmethod
    def format_value(value: Any) -> str:
        """
        Format a single value for TSV output.
        
        Args:
            value: The value to format
            
        Returns:
            Formatted string value
        """
        if value is None:
            return ""
        
        # Handle datetime objects
        if isinstance(value, datetime):
            return value.isoformat()
        
        # Convert to string and escape tabs/newlines
        str_value = str(value)
        str_value = str_value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
        return str_value
    
    @staticmethod
    def write_tsv(rows: List[Dict[str, Any]], columns: List[str] = None) -> str:
        """
        Convert rows to TSV format.
        
        Args:
            rows: List of dictionaries representing rows
            columns: Optional column order (uses first row keys if not provided)
            
        Returns:
            TSV formatted string
        """
        if not rows:
            logger.warning("No rows to write")
            return ""
        
        # Determine columns from first row if not provided
        if columns is None:
            columns = list(rows[0].keys())
        
        output = io.StringIO()
        
        # Write header
        header = '\t'.join(columns)
        output.write(header + '\n')
        
        # Write data rows
        for row in rows:
            values = [TSVWriter.format_value(row.get(col)) for col in columns]
            line = '\t'.join(values)
            output.write(line + '\n')
        
        result = output.getvalue()
        output.close()
        
        logger.info(f"Generated TSV with {len(rows)} rows and {len(columns)} columns")
        return result
    
    @staticmethod
    def parse_tsv(content: str) -> List[Dict[str, Any]]:
        """
        Parse TSV content into list of dictionaries.
        
        Args:
            content: TSV formatted string
            
        Returns:
            List of row dictionaries
        """
        lines = content.strip().split('\n')
        if not lines:
            return []
        
        # Parse header
        columns = lines[0].split('\t')
        
        # Parse data rows
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split('\t')
            row = {columns[i]: values[i] if i < len(values) else "" for i in range(len(columns))}
            rows.append(row)
        
        logger.info(f"Parsed TSV with {len(rows)} rows and {len(columns)} columns")
        return rows
