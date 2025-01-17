import json
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

class APIKeyManager:
    """Manages retrieval of API credentials from AWS Secrets Manager."""
    
    def __init__(self, secret_name: str):
        self._secret_name = secret_name
        self._credentials: Optional[Dict[str, str]] = None
        
    def _load_credentials(self) -> None:
        """Fetch credentials from AWS Secrets Manager if not already loaded."""
        if self._credentials is not None:
            return
            
        try:
            response = boto3.client("secretsmanager").get_secret_value(
                SecretId=self._secret_name
            )
            secret_string = response.get("SecretString")
            if not secret_string:
                raise ValueError("No secret string found in response")
                
            self._credentials = json.loads(secret_string)
            
        except (ClientError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to retrieve credentials: {str(e)}") from e
    
    @property
    def api_key(self) -> str:
        """The API key from secrets manager."""
        self._load_credentials()
        return self._credentials["api-key"]
    
    @property
    def api_secret(self) -> str:
        """The API secret from secrets manager."""
        self._load_credentials()
        return self._credentials["api-secret"]

class DynamoDBManager:
    """Manages connections and operations for AWS DynamoDB."""
    
    def __init__(self):
        self._resource = None
    
    @property
    def _db_resource(self) -> Any:
        """Lazily initialize and return DynamoDB resource."""
        if self._resource is None:
            self._resource = boto3.resource("dynamodb")
        return self._resource
    
    def get_table(self, table_name: str) -> Any:
        """
        Get a DynamoDB table resource. Caches the table reference.
        
        Args:
            table_name: Name of the DynamoDB table.
            
        Returns:
            DynamoDB Table resource.
            
        Raises:
            ValueError: If table doesn't exist.
            RuntimeError: If AWS has internal server errors.
        """
        try:
            table = self._db_resource.Table(table_name)
            return table
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                raise ValueError(
                    f"DynamoDB table '{table_name}' not found"
                ) from e
            if error_code == 'InternalServerError':
                raise RuntimeError(
                    "AWS internal server error while accessing DynamoDB"
                ) from e
            raise 