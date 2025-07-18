import importlib
from threading import Lock

from mindsdb.interfaces.storage.model_fs import HandlerStorage


def func_call_process(name: str, args: dict, integration_id: int, module_path: str) -> None:
    module = importlib.import_module(module_path)

    # Propagate import error if present
    if module.import_error is not None:
        raise module.import_error

    # Fast check, else return early
    if not hasattr(module.Handler, "function_call"):
        return None

    # Use cached HandlerStorage
    engine_storage = _get_handler_storage(integration_id)
    try:
        # Create handler and do function_call
        return module.Handler(engine_storage=engine_storage, model_storage=None).function_call(name, args)
    except NotImplementedError:
        return None
    except Exception as e:
        raise e


def _get_handler_storage(integration_id):
    # Thread-safe cache to avoid recreating HandlerStorage for same integration_id
    with _handler_storage_lock:
        if integration_id not in _handler_storage_cache:
            _handler_storage_cache[integration_id] = HandlerStorage(integration_id)
        return _handler_storage_cache[integration_id]


_handler_storage_cache = {}

_handler_storage_lock = Lock()
