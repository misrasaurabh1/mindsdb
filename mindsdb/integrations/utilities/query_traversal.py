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
    # Optimization: Use append/pop to mutate the existing stack instead of list concatenation.
    if stack is None:
        stack = []
    stack.append(node)
    res = callback(node, is_table=is_table, is_target=is_target, parent_query=parent_query, callstack=stack)
    if res is not None:
        stack.pop()
        return res

    # For repeated assignment
    qtr = query_traversal  # Localizing the function reference

    # Fast branch: handle node types
    node_type = type(node)
    if node_type is ast.Select:
        # For list attributes, minimize reallocation: create only if needed.
        if node.from_table is not None:
            node_out = qtr(node.from_table, callback, is_table=True, parent_query=node, stack=stack)
            if node_out is not None:
                node.from_table = node_out

        node.targets = [
            y
            for node2 in node.targets
            for y in (
                qtr(node2, callback, parent_query=node, is_target=True, stack=stack)
                if isinstance(qtr(node2, callback, parent_query=node, is_target=True, stack=stack), list)
                else [qtr(node2, callback, parent_query=node, is_target=True, stack=stack) or node2]
            )
        ]

        if node.cte is not None:
            node.cte = [qtr(cte.query, callback, parent_query=node, stack=stack) or cte for cte in node.cte]

        if node.where is not None:
            node_out = qtr(node.where, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.where = node_out

        if node.group_by is not None:
            node.group_by = [qtr(node2, callback, parent_query=node, stack=stack) or node2 for node2 in node.group_by]

        if node.having is not None:
            node_out = qtr(node.having, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.having = node_out

        if node.order_by is not None:
            node.order_by = [qtr(node2, callback, parent_query=node, stack=stack) or node2 for node2 in node.order_by]

    elif node_type in (ast.Union, ast.Intersect, ast.Except):
        node_out = qtr(node.left, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.left = node_out
        node_out = qtr(node.right, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.right = node_out

    elif node_type is ast.Join:
        node_out = qtr(node.right, callback, is_table=True, parent_query=parent_query, stack=stack)
        if node_out is not None:
            node.right = node_out
        node_out = qtr(node.left, callback, is_table=True, parent_query=parent_query, stack=stack)
        if node_out is not None:
            node.left = node_out
        if node.condition is not None:
            node_out = qtr(node.condition, callback, parent_query=parent_query, stack=stack)
            if node_out is not None:
                node.condition = node_out

    elif node_type in (
        ast.Function,
        ast.BinaryOperation,
        ast.UnaryOperation,
        ast.BetweenOperation,
        ast.Exists,
        ast.NotExists,
    ):
        node.args = [qtr(arg, callback, parent_query=parent_query, stack=stack) or arg for arg in node.args]
        if node_type is ast.Function and node.from_arg is not None:
            node_out = qtr(node.from_arg, callback, parent_query=parent_query, stack=stack)
            if node_out is not None:
                node.from_arg = node_out

    elif node_type is ast.WindowFunction:
        qtr(node.function, callback, parent_query=parent_query, stack=stack)
        if node.partition is not None:
            node.partition = [
                qtr(node2, callback, parent_query=parent_query, stack=stack) or node2 for node2 in node.partition
            ]
        if node.order_by is not None:
            node.order_by = [
                qtr(node2, callback, parent_query=parent_query, stack=stack) or node2 for node2 in node.order_by
            ]

    elif node_type is ast.TypeCast:
        node_out = qtr(node.arg, callback, parent_query=parent_query, stack=stack)
        if node_out is not None:
            node.arg = node_out

    elif node_type is ast.Tuple:
        node.items = [qtr(node2, callback, parent_query=parent_query, stack=stack) or node2 for node2 in node.items]

    elif node_type is ast.Insert:
        if node.table is not None:
            node_out = qtr(node.table, callback, is_table=True, parent_query=node, stack=stack)
            if node_out is not None:
                node.table = node_out

        if node.values is not None:
            node.values = [
                [qtr(item, callback, parent_query=node, stack=stack) or item for item in row] for row in node.values
            ]

        if node.from_select is not None:
            node_out = qtr(node.from_select, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.from_select = node_out

    elif node_type is ast.Update:
        if node.table is not None:
            node_out = qtr(node.table, callback, is_table=True, parent_query=node, stack=stack)
            if node_out is not None:
                node.table = node_out

        if node.where is not None:
            node_out = qtr(node.where, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.where = node_out

        if node.update_columns is not None:
            upd = {
                k: v2
                for k, v in node.update_columns.items()
                for v2 in [qtr(v, callback, parent_query=node, stack=stack)]
                if v2 is not None
            }
            if upd:
                node.update_columns.update(upd)

        if node.from_select is not None:
            node_out = qtr(node.from_select, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.from_select = node_out

    elif node_type is ast.CreateTable:
        if node.columns is not None:
            node.columns = [qtr(node2, callback, parent_query=node, stack=stack) or node2 for node2 in node.columns]
        if node.name is not None:
            node_out = qtr(node.name, callback, is_table=True, parent_query=node, stack=stack)
            if node_out is not None:
                node.name = node_out
        if node.from_select is not None:
            node_out = qtr(node.from_select, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.from_select = node_out

    elif node_type is ast.Delete:
        if node.where is not None:
            node_out = qtr(node.where, callback, parent_query=node, stack=stack)
            if node_out is not None:
                node.where = node_out

    elif node_type is ast.OrderBy:
        if node.field is not None:
            node_out = qtr(node.field, callback, parent_query=parent_query, stack=stack)
            if node_out is not None:
                node.field = node_out

    elif node_type is ast.Case:
        node.rules = [
            [
                (
                    c2
                    if (c2 := qtr(condition, callback, parent_query=parent_query, stack=stack)) is not None
                    else condition
                ),
                (r2 if (r2 := qtr(result, callback, parent_query=parent_query, stack=stack)) is not None else result),
            ]
            for condition, result in node.rules
        ]
        default = qtr(node.default, callback, parent_query=parent_query, stack=stack)
        if default is not None:
            node.default = default

    elif isinstance(node, list):
        # Return a new list, don't mutate the original (conservative for safety).
        res_list = [qtr(node2, callback, parent_query=parent_query, stack=stack) or node2 for node2 in node]
        stack.pop()
        return res_list

    stack.pop()
    # keep original node
    return None
