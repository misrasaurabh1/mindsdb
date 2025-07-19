import os
from typing import Dict

from mindsdb.interfaces.storage.model_fs import HandlerStorage
from mindsdb.utilities.config import Config

"""Contains utilities to be used by handlers."""


def get_api_key(
    api_name: str,
    create_args: Dict[str, str],
    engine_storage: HandlerStorage = None,
    strict: bool = True,
):
    """Gets the API key needed to use an ML Handler.

    Args:
        api_name (str): Name of the API (e.g. openai, anthropic)
        create_args (Dict[str, str]): Args user passed to the created model with USING keyword
        engine_storage (HandlerStorage): Engine storage for the ML handler
        strict (bool): Whether or not to require the API key

    Returns:
        api_key (str): The API key

    API_KEY preference order:
        1. provided at inference
        2. provided at model creation
        3. provided at engine creation
        4. api key env variable
        5. api_key setting in config.json
    """
    if api_name == "vllm":
        return "EMPTY"

    using_args = create_args.get("using", {})
    params_args = create_args.get("params", {}) if create_args.get("params") is not None else {}
    conn_args = engine_storage.get_connection_args() if engine_storage is not None else {}

    # Preference order, batched/short-circuit for performance
    # 1, 1.5
    key = using_args.get(f"{api_name.lower()}_api_key") or using_args.get("api_key")
    if key:
        return key
    # 2, 2.5
    key = create_args.get(f"{api_name.lower()}_api_key") or create_args.get("api_key")
    if key:
        return key
    # 3, 3.5
    key = params_args.get(f"{api_name.lower()}_api_key") or params_args.get("api_key")
    if key:
        return key
    # 4, 4.5
    key = conn_args.get(f"{api_name.lower()}_api_key") or conn_args.get("api_key")
    if key:
        return key
    # 5
    key = os.getenv(f"{api_name.lower()}_api_key") or os.getenv(f"{api_name.upper()}_API_KEY")
    if key:
        return key
    # 6
    api_cfg = Config().get(api_name, {})
    key = api_cfg.get(f"{api_name.lower()}_api_key")
    if key:
        return key
    # 7
    key = create_args.get("api_keys", {}).get(api_name)
    if key:
        return key

    if strict:
        provider_upper = api_name.upper()
        api_key_env_var = f"{provider_upper}_API_KEY"
        api_key_arg = f"{api_name.lower()}_api_key"
        error_message = (
            f"API key for {api_name} not found. Please provide it using one of the following methods:\n"
            f"1. Set the {api_key_env_var} environment variable\n"
            f"2. Provide it as '{api_key_arg}' parameter or 'api_key' parameter when creating an agent using the CREATE AGENT syntax\n"
            f"   Example: CREATE AGENT my_agent USING model='gpt-4', provider='{api_name}', {api_key_arg}='your-api-key';\n"
            f"   Or: CREATE AGENT my_agent USING model='gpt-4', provider='{api_name}', api_key='your-api-key';\n"
        )
        raise Exception(error_message)
    return None
