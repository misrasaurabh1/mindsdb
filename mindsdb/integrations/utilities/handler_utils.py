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
    lname = api_name.lower()

    if lname == "vllm":
        return "EMPTY"

    using = create_args.get("using")
    if using:
        # 1, 1.5
        key1 = f"{lname}_api_key"
        if key1 in using:
            return using[key1]
        if "api_key" in using:
            return using["api_key"]

    # 2, 2.5
    key2 = f"{lname}_api_key"
    if key2 in create_args:
        return create_args[key2]
    if "api_key" in create_args:
        return create_args["api_key"]

    # 3, 3.5
    params = create_args.get("params")
    if params:
        if key2 in params:
            return params[key2]
        if "api_key" in params:
            return params["api_key"]

    # 4, 4.5
    if engine_storage is not None:
        connection_args = engine_storage.get_connection_args()
        if key2 in connection_args:
            return connection_args[key2]
        if "api_key" in connection_args:
            return connection_args["api_key"]

    # 5. Try lower and upper envvars in one pass for best performance
    env_key = f"{lname}_api_key"
    env = os.environ
    api_key = env.get(env_key) or env.get(f"{api_name.upper()}_API_KEY")
    if api_key:
        return api_key

    # 6: config singleton/cached key
    api_key = _get_config_api_key(api_name)
    if api_key:
        return api_key

    # 7: create_args["api_keys"] mapping
    api_keys = create_args.get("api_keys")
    if api_keys and api_name in api_keys:
        return api_keys[api_name]

    # Strict handling & error
    if strict:
        provider_upper = api_name.upper()
        api_key_env_var = f"{provider_upper}_API_KEY"
        api_key_arg = f"{lname}_api_key"
        error_message = (
            f"API key for {api_name} not found. Please provide it using one of the following methods:\n"
            f"1. Set the {api_key_env_var} environment variable\n"
            f"2. Provide it as '{api_key_arg}' parameter or 'api_key' parameter when creating an agent using the CREATE AGENT syntax\n"
            f"   Example: CREATE AGENT my_agent USING model='gpt-4', provider='{api_name}', {api_key_arg}='your-api-key';\n"
            f"   Or: CREATE AGENT my_agent USING model='gpt-4', provider='{api_name}', api_key='your-api-key';\n"
        )
        raise Exception(error_message)
    return None


def _get_config_instance():
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def _get_config_api_key(api_name):
    # Get/cached config[api_name] lookup
    key = api_name.lower()
    if key in _config_api_keys:
        return _config_api_keys[key]
    config = _get_config_instance()
    api_cfg = config.get(api_name, {})
    api_key = api_cfg.get(f"{key}_api_key")
    _config_api_keys[key] = api_key
    return api_key


_config_instance = None

_config_api_keys = {}
