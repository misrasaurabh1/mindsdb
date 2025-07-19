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
        raise ValueError('sql query is None')

    length = len(sql)
    out = []
    i = 0

    # State variables
    IN_NONE, IN_SQ, IN_DQ, IN_BQ = 0, 1, 2, 3
    state = IN_NONE

    while i < length:
        c = sql[i]
        if state == IN_NONE:
            if c == "'":
                out.append(c)
                state = IN_SQ
            elif c == '"':
                out.append(c)
                state = IN_DQ
            elif c == '`':
                out.append(c)
                state = IN_BQ
            elif c == '/' and i+1 < length and sql[i+1] == '*':
                # skip /* ... */
                i += 2
                while i+1 < length and not (sql[i] == '*' and sql[i+1] == '/'):
                    i += 1
                if i+1 < length:
                    i += 2
                else:
                    i += 1
                continue
            elif c == '-' and i+1 < length and sql[i+1] == '-':
                # skip -- ... \n
                i += 2
                while i < length and sql[i] != '\n':
                    i += 1
                continue
            elif c == '#':
                # skip # ... \n
                i += 1
                while i < length and sql[i] != '\n':
                    i += 1
                continue
            else:
                out.append(c)
        elif state == IN_SQ:
            out.append(c)
            if c == '\\' and i+1 < length:
                out.append(sql[i+1])
                i += 1
            elif c == "'":
                state = IN_NONE
        elif state == IN_DQ:
            out.append(c)
            if c == '\\' and i+1 < length:
                out.append(sql[i+1])
                i += 1
            elif c == '"':
                state = IN_NONE
        elif state == IN_BQ:
            out.append(c)
            if c == '\\' and i+1 < length:
                out.append(sql[i+1])
                i += 1
            elif c == '`':
                state = IN_NONE
        i += 1

    sql = ''.join(out)

    # Trailing semicolon and all whitespace
    sql = sql.rstrip()
    if sql.endswith(';'):
        sql = sql[:-1].rstrip()

    return sql.strip(' \n\t')
