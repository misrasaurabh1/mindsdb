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
    # Fast stack push/pop, avoid [node] + stack overhead
    if stack is None:
        stack = ()
    stack2 = (node,) + stack  # tuple, cheap and read-only

    res = callback(node, is_table=is_table, is_target=is_target, parent_query=parent_query, callstack=stack)
    if res is not None:
        # node is going to be replaced
        return res

    handler = _traversal_dispatch.get(type(node))
    if handler:
        return handler(node, callback, is_table, is_target, parent_query, stack2)

    # keep original node
    return None


def _query_traversal_select(node, callback, is_table, is_target, parent_query, stack):
    # Shortcuts for local vars (micro-optimization)
    cb = callback
    pq = node

    if node.from_table is not None:
        node_out = query_traversal(node.from_table, cb, is_table=True, parent_query=pq, stack=stack)
        if node_out is not None:
            node.from_table = node_out

    # targets
    targets = node.targets
    array = []
    for node2 in targets:
        node_out = query_traversal(node2, cb, parent_query=pq, is_target=True, stack=stack) or node2
        if isinstance(node_out, list):
            array.extend(node_out)
        else:
            array.append(node_out)
    node.targets = array

    if node.cte is not None:
        cte = node.cte
        array = []
        for c in cte:
            node_out = query_traversal(c.query, cb, parent_query=pq, stack=stack) or c
            array.append(node_out)
        node.cte = array

    if node.where is not None:
        node_out = query_traversal(node.where, cb, parent_query=pq, stack=stack)
        if node_out is not None:
            node.where = node_out

    if node.group_by is not None:
        gb = node.group_by
        array = [query_traversal(n2, cb, parent_query=pq, stack=stack) or n2 for n2 in gb]
        node.group_by = array

    if node.having is not None:
        node_out = query_traversal(node.having, cb, parent_query=pq, stack=stack)
        if node_out is not None:
            node.having = node_out

    if node.order_by is not None:
        ob = node.order_by
        array = [query_traversal(n2, cb, parent_query=pq, stack=stack) or n2 for n2 in ob]
        node.order_by = array

    return None


def _query_traversal_compound(node, callback, is_table, is_target, parent_query, stack):
    node_out = query_traversal(node.left, callback, parent_query=node, stack=stack)
    if node_out is not None:
        node.left = node_out
    node_out = query_traversal(node.right, callback, parent_query=node, stack=stack)
    if node_out is not None:
        node.right = node_out
    return None


def _query_traversal_join(node, callback, is_table, is_target, parent_query, stack):
    node_out = query_traversal(node.right, callback, is_table=True, parent_query=parent_query, stack=stack)
    if node_out is not None:
        node.right = node_out
    node_out = query_traversal(node.left, callback, is_table=True, parent_query=parent_query, stack=stack)
    if node_out is not None:
        node.left = node_out
    if node.condition is not None:
        node_out = query_traversal(node.condition, callback, parent_query=parent_query, stack=stack)
        if node_out is not None:
            node.condition = node_out
    return None


def _query_traversal_generic_func(node, callback, is_table, is_target, parent_query, stack):
    cb = callback
    pq = parent_query
    args = node.args
    node.args = [query_traversal(arg, cb, parent_query=pq, stack=stack) or arg for arg in args]
    if isinstance(node, ast.Function) and getattr(node, "from_arg", None) is not None:
        node_out = query_traversal(node.from_arg, cb, parent_query=pq, stack=stack)
        if node_out is not None:
            node.from_arg = node_out
    return None


def _query_traversal_window(func_node, callback, _1, _2, parent_query, stack):
    cb = callback
    pq = parent_query
    query_traversal(func_node.function, cb, parent_query=pq, stack=stack)
    if func_node.partition is not None:
        func_node.partition = [
            query_traversal(n2, cb, parent_query=pq, stack=stack) or n2 for n2 in func_node.partition
        ]
    if func_node.order_by is not None:
        func_node.order_by = [query_traversal(n2, cb, parent_query=pq, stack=stack) or n2 for n2 in func_node.order_by]
    return None


def _query_traversal_typecast(tc_node, callback, _1, _2, parent_query, stack):
    node_out = query_traversal(tc_node.arg, callback, parent_query=parent_query, stack=stack)
    if node_out is not None:
        tc_node.arg = node_out
    return None


def _query_traversal_tuple(tup_node, callback, _1, _2, parent_query, stack):
    tup_node.items = [
        query_traversal(item, callback, parent_query=parent_query, stack=stack) or item for item in tup_node.items
    ]
    return None


def _query_traversal_insert(node, callback, is_table, is_target, parent_query, stack):
    if node.table is not None:
        node_out = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack)
        if node_out is not None:
            node.table = node_out
    if node.values is not None:
        node.values = [
            [query_traversal(item, callback, parent_query=node, stack=stack) or item for item in row]
            for row in node.values
        ]
    if node.from_select is not None:
        node_out = query_traversal(node.from_select, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.from_select = node_out
    return None


def _query_traversal_update(node, callback, is_table, is_target, parent_query, stack):
    if node.table is not None:
        node_out = query_traversal(node.table, callback, is_table=True, parent_query=node, stack=stack)
        if node_out is not None:
            node.table = node_out
    if node.where is not None:
        node_out = query_traversal(node.where, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.where = node_out
    if node.update_columns is not None:
        # only call callback if vals changed
        changes = {}
        for k, v in node.update_columns.items():
            v2 = query_traversal(v, callback, parent_query=node, stack=stack)
            if v2 is not None:
                changes[k] = v2
        if changes:
            node.update_columns.update(changes)
    if node.from_select is not None:
        node_out = query_traversal(node.from_select, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.from_select = node_out
    return None


def _query_traversal_createtable(node, callback, is_table, is_target, parent_query, stack):
    if node.columns is not None:
        node.columns = [query_traversal(c, callback, parent_query=node, stack=stack) or c for c in node.columns]
    if node.name is not None:
        node_out = query_traversal(node.name, callback, is_table=True, parent_query=node, stack=stack)
        if node_out is not None:
            node.name = node_out
    if node.from_select is not None:
        node_out = query_traversal(node.from_select, callback, parent_query=node, stack=stack)
        if node_out is not None:
            node.from_select = node_out
    return None


def _query_traversal_delete(node, callback, *_):
    if node.where is not None:
        node_out = query_traversal(node.where, callback, parent_query=node, stack=None)
        if node_out is not None:
            node.where = node_out
    return None


def _query_traversal_orderby(node, callback, *_):
    if node.field is not None:
        node_out = query_traversal(node.field, callback, parent_query=None, stack=None)
        if node_out is not None:
            node.field = node_out
    return None


def _query_traversal_case(node, callback, *_1, parent_query, stack):
    rule_out = []
    for condition, result in node.rules:
        condition2 = query_traversal(condition, callback, parent_query=parent_query, stack=stack)
        result2 = query_traversal(result, callback, parent_query=parent_query, stack=stack)

        rule_out.append([condition if condition2 is None else condition2, result if result2 is None else result2])
    node.rules = rule_out
    default = query_traversal(node.default, callback, parent_query=parent_query, stack=stack)
    if default is not None:
        node.default = default
    return None


def _query_traversal_list(node, callback, is_table, is_target, parent_query, stack):
    return [query_traversal(n2, callback, parent_query=parent_query, stack=stack) or n2 for n2 in node]


_traversal_dispatch = {
    ast.Select: _query_traversal_select,
    ast.Union: _query_traversal_compound,
    ast.Intersect: _query_traversal_compound,
    ast.Except: _query_traversal_compound,
    ast.Join: _query_traversal_join,
    ast.Function: _query_traversal_generic_func,
    ast.BinaryOperation: _query_traversal_generic_func,
    ast.UnaryOperation: _query_traversal_generic_func,
    ast.BetweenOperation: _query_traversal_generic_func,
    ast.Exists: _query_traversal_generic_func,
    ast.NotExists: _query_traversal_generic_func,
    ast.WindowFunction: _query_traversal_window,
    ast.TypeCast: _query_traversal_typecast,
    ast.Tuple: _query_traversal_tuple,
    ast.Insert: _query_traversal_insert,
    ast.Update: _query_traversal_update,
    ast.CreateTable: _query_traversal_createtable,
    ast.Delete: _query_traversal_delete,
    ast.OrderBy: _query_traversal_orderby,
    ast.Case: _query_traversal_case,
    list: _query_traversal_list,
}
