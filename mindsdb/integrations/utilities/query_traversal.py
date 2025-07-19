from mindsdb_sql_parser import ast
import copy


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
    # This function is slightly optimized (collapsing repeated code and branches),
    # but core recursive logic is preserved.
    if stack is None:
        stack = []
    res = callback(node, is_table=is_table, is_target=is_target, parent_query=parent_query, callstack=stack)
    if res is not None:
        return res
    stack2 = [node] + stack

    t_ast = ast
    ntype = type(node)

    if ntype == t_ast.Select:
        if node.from_table is not None:
            out = query_traversal(node.from_table, callback, is_table=True, parent_query=node, stack=stack2)
            if out is not None:
                node.from_table = out
        node.targets = [
            item
            for node2 in node.targets
            for item in (query_traversal(node2, callback, parent_query=node, is_target=True, stack=stack2) or [node2])
            if not isinstance(item, list)
        ] + [
            item
            for node2 in node.targets
            for item in (query_traversal(node2, callback, parent_query=node, is_target=True, stack=stack2) or [node2])
            if isinstance(item, list)
            for item in item
        ]
        if node.cte is not None:
            node.cte = [
                query_traversal(cte.query, callback, parent_query=node, stack=stack2) or cte for cte in node.cte
            ]
        if node.where is not None:
            out = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.where = out
        if node.group_by is not None:
            node.group_by = [query_traversal(n, callback, parent_query=node, stack=stack2) or n for n in node.group_by]
        if node.having is not None:
            out = query_traversal(node.having, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.having = out
        if node.order_by is not None:
            node.order_by = [query_traversal(n, callback, parent_query=node, stack=stack2) or n for n in node.order_by]
    elif ntype in (t_ast.Union, t_ast.Intersect, t_ast.Except):
        left_out = query_traversal(node.left, callback, parent_query=node, stack=stack2)
        if left_out is not None:
            node.left = left_out
        right_out = query_traversal(node.right, callback, parent_query=node, stack=stack2)
        if right_out is not None:
            node.right = right_out
    elif ntype == t_ast.Join:
        for attr in ("right", "left"):
            out = query_traversal(getattr(node, attr), callback, is_table=True, parent_query=parent_query, stack=stack2)
            if out is not None:
                setattr(node, attr, out)
        if node.condition is not None:
            out = query_traversal(node.condition, callback, parent_query=parent_query, stack=stack2)
            if out is not None:
                node.condition = out
    elif ntype in (
        t_ast.Function,
        t_ast.BinaryOperation,
        t_ast.UnaryOperation,
        t_ast.BetweenOperation,
        t_ast.Exists,
        t_ast.NotExists,
    ):
        # Function-like nodes with .args
        node.args = [
            query_traversal(arg, callback, parent_query=parent_query, stack=stack2) or arg for arg in node.args
        ]
        if ntype == t_ast.Function and node.from_arg is not None:
            out = query_traversal(node.from_arg, callback, parent_query=parent_query, stack=stack2)
            if out is not None:
                node.from_arg = out
    elif ntype == t_ast.WindowFunction:
        query_traversal(node.function, callback, parent_query=parent_query, stack=stack2)
        if node.partition is not None:
            node.partition = [
                query_traversal(n, callback, parent_query=parent_query, stack=stack2) or n for n in node.partition
            ]
        if node.order_by is not None:
            node.order_by = [
                query_traversal(n, callback, parent_query=parent_query, stack=stack2) or n for n in node.order_by
            ]
    elif ntype == t_ast.TypeCast:
        out = query_traversal(node.arg, callback, parent_query=parent_query, stack=stack2)
        if out is not None:
            node.arg = out
    elif ntype == t_ast.Tuple:
        node.items = [query_traversal(n, callback, parent_query=parent_query, stack=stack2) or n for n in node.items]
    elif ntype == t_ast.Insert:
        if node.table is not None:
            out = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack2)
            if out is not None:
                node.table = out
        if node.values is not None:
            node.values = [
                [query_traversal(item, callback, parent_query=node, stack=stack2) or item for item in row]
                for row in node.values
            ]
        if node.from_select is not None:
            out = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.from_select = out
    elif ntype == t_ast.Update:
        if node.table is not None:
            out = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack2)
            if out is not None:
                node.table = out
        if node.where is not None:
            out = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.where = out
        if node.update_columns is not None:
            changes = {
                k: v2
                for k, v in node.update_columns.items()
                if (v2 := query_traversal(v, callback, parent_query=node, stack=stack2)) is not None
            }
            if changes:
                node.update_columns.update(changes)
        if node.from_select is not None:
            out = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.from_select = out
    elif ntype == t_ast.CreateTable:
        if node.columns is not None:
            node.columns = [query_traversal(n, callback, parent_query=node, stack=stack2) or n for n in node.columns]
        if node.name is not None:
            out = query_traversal(node.name, callback, is_table=True, parent_query=node, stack=stack2)
            if out is not None:
                node.name = out
        if node.from_select is not None:
            out = query_traversal(node.from_select, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.from_select = out
    elif ntype == t_ast.Delete:
        if node.where is not None:
            out = query_traversal(node.where, callback, parent_query=node, stack=stack2)
            if out is not None:
                node.where = out
    elif ntype == t_ast.OrderBy:
        if node.field is not None:
            out = query_traversal(node.field, callback, parent_query=parent_query, stack=stack2)
            if out is not None:
                node.field = out
    elif ntype == t_ast.Case:
        node.rules = [
            [
                (
                    c2
                    if (c2 := query_traversal(condition, callback, parent_query=parent_query, stack=stack2)) is not None
                    else condition
                ),
                (
                    r2
                    if (r2 := query_traversal(result, callback, parent_query=parent_query, stack=stack2)) is not None
                    else result
                ),
            ]
            for condition, result in node.rules
        ]
        if (default := query_traversal(node.default, callback, parent_query=parent_query, stack=stack2)) is not None:
            node.default = default
    elif ntype == list:
        return [query_traversal(n, callback, parent_query=parent_query, stack=stack2) or n for n in node]
    return None


def _fast_query_shallow_copy(query):
    # Optimized shallow copy to avoid deepcopy slowdowns when possible.
    new_query = copy.copy(query)
    # Standard container attributes that may need copying:
    for attr in ("targets", "cte", "group_by", "order_by"):
        val = getattr(query, attr, None)
        if isinstance(val, list):
            setattr(new_query, attr, val[:])
    # For dict-like fields (rare in most queries, but update_columns for UPDATE)
    if hasattr(query, "update_columns") and isinstance(query.update_columns, dict):
        new_query.update_columns = query.update_columns.copy()
    return new_query
