import boto3
from typing import Dict, Tuple, Text, Optional

# Internal cache for clients, indexed by parameters.
_client_cache: Dict[Tuple[Text, Text, Text, Text, Optional[Text]], boto3.client] = {}


def create_amazon_bedrock_client(
    client: Text,
    aws_access_key_id: Text,
    aws_secret_access_key: Text,
    region_name: Text,
    aws_session_token: Optional[Text] = None,
) -> boto3.client:
    """
    Create an Amazon Bedrock client via boto3.

    Parameters
    ----------
    client : Text
        The type of client to create. It can be 'bedrock' or 'bedrock-runtime'.

    aws_access_key_id : Text
        The AWS access key ID.

    aws_secret_access_key : Text
        The AWS secret access key.

    region_name : Text
        The AWS region name.

    aws_session_token : Text, Optional
        The AWS session token. Optional, but required for temporary security credentials.

    Returns
    -------
    boto3.client
        Amazon Bedrock client.
    """
    if client not in ("bedrock", "bedrock-runtime"):
        raise ValueError("The client must be 'bedrock' or 'bedrock-runtime'")

    key = (client, aws_access_key_id, aws_secret_access_key, region_name, aws_session_token)
    cached_client = _client_cache.get(key)
    if cached_client is not None:
        return cached_client

    new_client = boto3.client(
        client,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
        aws_session_token=aws_session_token,
    )
    _client_cache[key] = new_client
    return new_client
