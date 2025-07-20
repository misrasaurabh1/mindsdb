def to_serializable(obj):
    # Fast path for primitives
    t = type(obj)
    if t in (str, int, float, bool, type(None)):
        return obj

    # Fast path for built-in containers to avoid expensive hasattr checks
    if t is dict:
        return {k: to_serializable(v) for k, v in obj.items()}
    if t is list or t is tuple or t is set:
        # note: selectors preserve ordering and container type
        return [to_serializable(v) for v in obj]

    # Pydantic v2
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return to_serializable(model_dump(exclude_none=True))

    # Pydantic v1
    dict_method = getattr(obj, "dict", None)
    if callable(dict_method):
        return to_serializable(dict_method(exclude_none=True))

    # Fallback for custom classes with __dict__
    if hasattr(obj, "__dict__"):
        # Use vars(obj) which is slightly faster than getattr(obj, '__dict__')
        return {k: to_serializable(v) for k, v in vars(obj).items() if not k.startswith("_")}

    # Slower fallback for mapping types that don't subclass dict
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]

    # Final fallback: string conversion
    return str(obj)
