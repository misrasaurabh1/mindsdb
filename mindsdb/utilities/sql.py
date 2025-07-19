def _is_in_quotes(pos: int, quote_positions: list[tuple[int, int]]) -> bool:
    """
    Check if a position is within any quoted string.

    Args:
        pos (int): The position to check.
        quote_positions (list[tuple[int, int]]): A list of tuples, each containing the start and
                                                 end positions of a quoted string.

    Returns:
        bool: True if the position is within any quoted string, False otherwise.
    """
    return any(start < pos < end for start, end in quote_positions)


def clear_sql(sql: str) -> str:
    """Remove comments (--, /**/, and oracle-stype #) and trailing ';' from sql
    Note: written mostly by LLM

    Args:
        sql (str): The SQL query to clear.

    Returns:
        str: The cleared SQL query.
    """
    if sql is None:
        raise ValueError("sql query is None")

    sql_len = len(sql)
    quote_positions = []
    for quote_char in ("'", '"', "`"):
        i = 0
        while i < sql_len:
            if sql[i] == quote_char and (i == 0 or sql[i - 1] != "\\"):
                start = i
                i += 1
                while i < sql_len and (sql[i] != quote_char or sql[i - 1] == "\\"):
                    i += 1
                if i < sql_len:
                    quote_positions.append((start, i))
            i += 1

    # Precompute mask for O(1) quote lookup
    quote_mask = _build_quote_mask(sql, quote_positions, sql_len)

    # Remove /* ... */ comments
    result = []
    i = 0
    append = result.append
    while i < sql_len:
        # Fast path -- only check for /* if not in quote
        if i + 1 < sql_len and sql[i] == "/" and sql[i + 1] == "*" and not quote_mask[i]:
            i += 2
            # Skip until we find */
            while i + 1 < sql_len:
                if sql[i] == "*" and sql[i + 1] == "/":
                    i += 2
                    break
                i += 1
            # If no ending */, just skip to end
            else:
                i = sql_len
        else:
            append(sql[i])
            i += 1

    sql2 = "".join(result)
    sql2_len = len(sql2)
    # Build a new quote mask for the possibly changed string (may not need, but for correctness)
    # But comments can't appear inside quoted regions, so using old mask is OK

    # Remove -- and # comments
    result = []
    i = 0
    append = result.append
    while i < sql2_len:
        ch = sql2[i]
        if i + 1 < sql2_len and ch == "-" and sql2[i + 1] == "-" and not quote_mask[i]:
            # skip to end of line
            i += 2
            while i < sql2_len and sql2[i] != "\n":
                i += 1
        elif ch == "#" and not quote_mask[i]:
            i += 1
            while i < sql2_len and sql2[i] != "\n":
                i += 1
        else:
            append(ch)
            i += 1

    sql3 = "".join(result)

    # Remove trailing ";"
    sql3 = sql3.rstrip()
    if sql3 and sql3[-1] == ";":
        sql3 = sql3[:-1].rstrip()

    return sql3.strip(" \n\t")


def _build_quote_mask(sql: str, quote_positions: list[tuple[int, int]], length: int) -> memoryview:
    """
    Build a mask of positions that are inside a quoted region for O(1) lookup.
    """
    import array

    # array of char, default False
    mask = array.array("B", (0,) * length)
    for start, end in quote_positions:
        # Mark positions inside quotes: start < i < end (exclusive both ends?)
        for i in range(start + 1, end):
            mask[i] = 1
    return memoryview(mask)
