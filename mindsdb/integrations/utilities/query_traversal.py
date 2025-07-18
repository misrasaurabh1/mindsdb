from mindsdb_sql_parser import ast


def query_traversal(node, callback, is_table=False, is_target=False, parent_query=None, stack=None):
    """
    :param node: element
    :param callback: function applied to every element
    :param is_table: it is table in query
    :param is_target: it is the target in select
    :param parent_query: current query (select/update/create/...) where we are now
    :return:
       new element if it is needed to be replaced
       or None to keep element and traverse over it

    Usage:
    Create callback function to check or replace nodes
    Example:
    ```python
    def remove_predictors(node, is_table, **kwargs):
        if is_table and isinstance(node, Identifier):
            if is_predictor(node):
                return Constant(None)

    utils.query_traversal(ast_query, remove_predictors)
    ```

    """

    # Avoid expensive list copying if depth is not needed.
    if stack is None:
        stack2 = [node]
    else:
        stack2 = [node] + stack

    res = callback(
        node,
        is_table=is_table,
        is_target=is_target,
        parent_query=parent_query,
        callstack=stack if stack is not None else [],
    )

    if res is not None:
        return res  # early replacement

    # Fast dispatch, prefer local var ref to instance checking
    node_type = type(node)
    if node_type is ast.Select:
        # Recurse on from_table (tables are rare, fast-path None)
        if node.from_table is not None:
            val = query_traversal(node.from_table, callback, is_table=True, parent_query=node, stack=stack2)
            if val is not None:
                node.from_table = val

        # Targets: optimize to single pass if all None, else inplace modify
        node.targets = _traverse_list(
            node.targets, query_traversal, callback, parent_query=node, is_target=True, stack=stack2
        )

        # CTE
        if node.cte is not None:
            node.cte = [
                query_traversal(cte.query, callback, parent_query=node, stack=stack2) or cte for cte in node.cte
            ]

        # Where
        if node.where is not None:
            val = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.where = val

        # Group By, Having, Order By
        if node.group_by is not None:
            node.group_by = _traverse_list(node.group_by, query_traversal, callback, parent_query=node, stack=stack2)
        if node.having is not None:
            val = query_traversal(node.having, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.having = val
        if node.order_by is not None:
            node.order_by = _traverse_list(node.order_by, query_traversal, callback, parent_query=node, stack=stack2)

    elif node_type in (ast.Union, ast.Intersect, ast.Except):
        val = query_traversal(node.left, callback, parent_query=node, stack=stack2)
        if val is not None:
            node.left = val
        val = query_traversal(node.right, callback, parent_query=node, stack=stack2)
        if val is not None:
            node.right = val

    elif node_type is ast.Join:
        val = query_traversal(node.right, callback, is_table=True, parent_query=parent_query, stack=stack2)
        if val is not None:
            node.right = val
        val = query_traversal(node.left, callback, is_table=True, parent_query=parent_query, stack=stack2)
        if val is not None:
            node.left = val
        if node.condition is not None:
            val = query_traversal(node.condition, callback, parent_query=parent_query, stack=stack2)
            if val is not None:
                node.condition = val

    elif node_type in (
        ast.Function,
        ast.BinaryOperation,
        ast.UnaryOperation,
        ast.BetweenOperation,
        ast.Exists,
        ast.NotExists,
    ):
        node.args = _traverse_list(node.args, query_traversal, callback, parent_query=parent_query, stack=stack2)
        if node_type is ast.Function and getattr(node, "from_arg", None) is not None:
            val = query_traversal(node.from_arg, callback, parent_query=parent_query, stack=stack2)
            if val is not None:
                node.from_arg = val

    elif node_type is ast.WindowFunction:
        query_traversal(node.function, callback, parent_query=parent_query, stack=stack2)
        if node.partition is not None:
            node.partition = _traverse_list(
                node.partition, query_traversal, callback, parent_query=parent_query, stack=stack2
            )
        if node.order_by is not None:
            node.order_by = _traverse_list(
                node.order_by, query_traversal, callback, parent_query=parent_query, stack=stack2
            )

    elif node_type is ast.TypeCast:
        val = query_traversal(node.arg, callback, parent_query=parent_query, stack=stack2)
        if val is not None:
            node.arg = val

    elif node_type is ast.Tuple:
        node.items = _traverse_list(node.items, query_traversal, callback, parent_query=parent_query, stack=stack2)

    elif node_type is ast.Insert:
        if node.table is not None:
            val = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack2)
            if val is not None:
                node.table = val
        if node.values is not None:
            # Loop flattened for better cache/fast-indexing
            node.values = [
                [query_traversal(item, callback, parent_query=node, stack=stack2) or item for item in row]
                for row in node.values
            ]
        if node.from_select is not None:
            val = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.from_select = val

    elif node_type is ast.Update:
        if node.table is not None:
            val = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack2)
            if val is not None:
                node.table = val
        if node.where is not None:
            val = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.where = val
        if node.update_columns is not None:
            # Only update modified columns
            chgs = {
                k: v2
                for k, v in node.update_columns.items()
                if (v2 := query_traversal(v, callback, parent_query=node, stack=stack2)) is not None
            }
            if chgs:
                node.update_columns.update(chgs)
        if node.from_select is not None:
            val = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.from_select = val

    elif node_type is ast.CreateTable:
        if node.columns is not None:
            node.columns = _traverse_list(node.columns, query_traversal, callback, parent_query=node, stack=stack2)
        if node.name is not None:
            val = query_traversal(node.name, callback, is_table=True, parent_query=node, stack=stack2)
            if val is not None:
                node.name = val
        if node.from_select is not None:
            val = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.from_select = val

    elif node_type is ast.Delete:
        if node.where is not None:
            val = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if val is not None:
                node.where = val

    elif node_type is ast.OrderBy:
        if node.field is not None:
            val = query_traversal(node.field, callback, parent_query=parent_query, stack=stack2)
            if val is not None:
                node.field = val

    elif node_type is ast.Case:
        # Faster: one pass for rules using tuple unpacking
        node.rules = [
            (
                query_traversal(condition, callback, parent_query=parent_query, stack=stack2) or condition,
                query_traversal(result, callback, parent_query=parent_query, stack=stack2) or result,
            )
            for condition, result in node.rules
        ]
        default = query_traversal(node.default, callback, parent_query=parent_query, stack=stack2)
        if default is not None:
            node.default = default

    elif node_type is list:
        # This should be rare but batch it efficiently
        return [query_traversal(item, callback, parent_query=parent_query, stack=stack2) or item for item in node]

    # keep original node
    return None


def _traverse_list(lst, traversefn, callback, **kwargs):
    """Helper: efficiently traverse collection."""
    # Use generator to reduce temporaries, assign only on change.
    changed = False
    new_list = []
    for item in lst:
        v = traversefn(item, callback, **kwargs)
        if v is not None:
            changed = True
            if isinstance(v, list):
                new_list.extend(v)
            else:
                new_list.append(v)
        else:
            new_list.append(item)
    return new_list if changed else lst
