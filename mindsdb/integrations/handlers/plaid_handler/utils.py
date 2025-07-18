def parse_transaction(res: list):
    # Use list comprehension for speedup, call correct to_dict for each obj
    return [obj.to_dict() for obj in res]
