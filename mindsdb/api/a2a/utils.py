def to_serializable(obj):
    # Fast-path for primitives
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    # Fast-path for dicts (appears most in profiling)
    if isinstance(obj, dict):
        # Avoid recomputing method lookups in tight loops
        get = obj.get
        items = obj.items
        return {k: to_serializable(v) for k, v in items()}
    # Pydantic v2: (rare, don't instantiate repeatedly)
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return to_serializable(model_dump(exclude_none=True))
    # Pydantic v1: (rare)
    dict_method = getattr(obj, "dict", None)
    if callable(dict_method):
        return to_serializable(dict_method(exclude_none=True))
    # Custom classes with __dict__ (should not requery hasattr)
    if hasattr(obj, "__dict__"):
        # Use vars() directly; skip private attrs in tight loop
        return {k: to_serializable(v) for k, v in vars(obj).items() if not k.startswith("_")}
    # Lists, Tuples, Sets
    # Avoid isinstance(obj, (list, tuple, set)) in tight loop
    # Use Sequence but exclude str to avoid catching strings
    if isinstance(obj, (list, tuple, set)):
        return [to_serializable(v) for v in obj]
    # Fallback: string
    return str(obj)
