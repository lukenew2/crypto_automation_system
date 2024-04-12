import json
import boto3
import os
from botocore.exceptions import ClientError
from decimal import Decimal
from datetime import datetime, timezone


class APIKeyManager:
    """
    Class that retrieves and manages API keys.

    Args:
        secret_name (str): The name of the secret in AWS Secrets Manager.

    Attributes:
        secret_name (str): The name of the secret in AWS Secrets Manager.
        api_key (str): The retrieved API key.
        api_secret (str): The retrieved API secret.
    """
    def __init__(self, secret_name: str):
        """
        Initializes the APIKeyManager object with the provided secret name.

        Args:
            secret_name: The name of the secret in AWS Secrets Manager.
            Defaults to None. 
        """
        self.secret_name = secret_name
        self.api_key = None
        self.api_secret = None

    def _retrieve_api_keys(self):
        """
        Retrieves API keys from AWS Secrets Manager.

        If the API keys have already been retrieved, this method does nothing.
        """
        try:
            secret_string = boto3.client("secretsmanager").get_secret_value(
                SecretId=self.secret_name
            )
            secrets = secret_string.get("SecretString")
            if secrets:
                secrets_dict = json.loads(secrets)
                self.api_key = secrets_dict.get("api-key")
                self.api_secret = secrets_dict.get("api-secret")
        except ClientError as e:
            print("Error retrieving API keys:", e)

    def get_api_key(self):
        """
        Retrieves the API key.

        If the API key has not been retrieved yet, this method retrieves it from AWS Secrets Manager.

        Returns:
            str: The API key.
        """
        if not self.api_key:
            self._retrieve_api_keys()
        return self.api_key

    def get_api_secret(self):
        """
        Retrieves the API secret.

        If the API secret has not been retrieved yet, this method retrieves it from AWS Secrets Manager.

        Returns:
            str: The API secret.
        """
        if not self.api_secret:
            self._retrieve_api_keys()
        return self.api_secret


class DynamoDBManager:
    """
    Class for managing connections to DynamoDB and related operations.
    """

    def __init__(self):
        """
        Initializes the DynamoDBManager.
        """
        self._client = None

    def _get_client(self):
        """
        Establishes connection to DynamoDB if no connection has been made.
        """
        if self._client is None:
            self._client = boto3.resource("dynamodb")
        return self._client

    def get_table(self, table_name: str):
        """
        Establishes connection to DynamoDB table.

        Args:
            table_name: Name of table in DynamoDB.

        Returns:
            DynamoDB table resource object.
        """
        try:
            client = self._get_client()
            table = client.Table(table_name)
            return table
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ValueError(f"DynamoDB table '{table_name}' not found.") from e
            elif e.response['Error']['Code'] == 'InternalServerError':
                raise RuntimeError(
                    "Internal server error occurred while accessing DynamoDB."
                ) from e
            else:
                raise e
            
def get_env_var(name: str, default_value: bool | None = None) -> bool:
    """Gets environment variable and returns as boolean."""
    true_ = ("true", "True")
    false_ = ("false", "False")  
    value: str | None = os.environ.get(name, None)
    if value is None:
        if default_value is None:
            raise ValueError(f'Variable `{name}` not set!')
        else:
            value = str(default_value)
    if value.lower() not in true_ + false_:
        raise ValueError(f'Invalid value `{value}` for variable `{name}`')
    return value in true_

def load_strategy_config():
    """Load strategy configuration from file."""
    try:
        with open("chalicelib/strategy_config.json") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError("Strategy configuration file not found.") from e
    except json.JSONDecodeError as e:
        raise ValueError("Error parsing JSON in strategy configuration file.") from e

def get_strategy_config():
    """Get configuration dict for trading strategy."""
    return load_strategy_config()

def convert_floats_to_decimals(data):
    """
    Recursively converts float values and numbers formatted as strings to 
    Decimal in a dictionary.

    Args:
        data: Dictionary containing float values and numbers formatted as 
        strings.

    Returns:
        Dictionary with float values and numbers formatted as strings converted 
        to Decimal.
    """
    if isinstance(data, dict):
        return {key: convert_floats_to_decimals(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_floats_to_decimals(item) for item in data]
    elif isinstance(data, float) or (isinstance(data, str) and data.replace(".", "", 1).isdigit()):
        return Decimal(str(data))
    else:
        return data

def get_utc_now_rounded():
    """Gets current time in utc rounded down to the hour."""
    utcnow = datetime.now(timezone.utc)
    return utcnow.replace(minute=0, second=0, microsecond=0)