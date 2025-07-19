import re
import ast as py_ast
import typing as t

from mindsdb_sql_parser.ast import OrderBy, Identifier, Star, Select, Constant, BinaryOperation, Tuple, Latest
from functools import reduce


class MongoToAst:

    """
      Converts query mongo to AST format
    """

    def from_mongoqeury(self, query):
        # IS NOT USED YET AND NOT FINISHED

        collection = query.collection

        filter, projection = None, None
        sort, limit, skip = None, None, None
        for step in query.pipeline:
            if step['method'] == 'find':
                filter = step['args'][0]
                if len(step) > 1:
                    projection = step['args'][1]
            elif step['method'] == 'sort':
                sort = step['args'][0]
            elif step['method'] == 'limit':
                limit = step['args'][0]
            elif step['method'] == 'skip':
                skip = step['args'][0]

        return self.find(collection, filter=filter,
                         sort=sort, projection=projection,
                         limit=limit, skip=skip)

    def find(self, collection: t.Union[list, str],
             filter=None, sort=None, projection=None,
             limit=None, skip=None, **kwargs):
        # https://www.mongodb.com/docs/v4.2/reference/method/db.collection.find/

        order_by = None
        if sort is not None:
            # sort is dict
            order_by = []
            for col, direction in sort.items():
                order_by.append(
                    OrderBy(
                        field=Identifier(parts=[col]),
                        direction='DESC' if direction == -1 else 'ASC'
                    )
                )

        if projection is not None:
            targets = []
            for col, alias in projection.items():
                # it is only identifiers
                if isinstance(alias, str):
                    alias = Identifier(parts=[alias])
                else:
                    alias = None
                targets.append(
                    Identifier(path_str=col, alias=alias)
                )
        else:
            targets = [Star()]

        where = None
        if filter is not None:
            where = self.convert_filter(filter)

        # convert to AST node
        #   collection can be string or list
        if isinstance(collection, list):
            collection = Identifier(parts=collection)
        else:
            collection = Identifier(path_str=collection)

        node = Select(
            targets=targets,
            from_table=collection,
            where=where,
            order_by=order_by,
        )
        if limit is not None:
            node.limit = Constant(value=limit)

        if skip is not None and skip != 0:
            node.offset = Constant(value=skip)

        return node

    def convert_filter(self, filter):
        cond_ops = {
            '$and': 'and',
            '$or': 'or',
        }

        ast_filter = None
        for k, v in filter.items():
            if k in ('$or', '$and'):
                # suppose it is one key in dict

                op = cond_ops[k]

                nodes = []
                for cond in v:
                    nodes.append(self.convert_filter(cond))

                if len(nodes) == 1:
                    return nodes[0]

                # compose as tree
                arg1 = nodes[0]
                for node in nodes[1:]:
                    arg1 = BinaryOperation(op=op, args=[arg1, node])

                return arg1
            if k in ('$where', '$expr'):
                # try to parse simple expression like 'this.saledate > this.latest'
                return MongoWhereParser(v).to_ast()

            # is filter
            arg1 = Identifier(parts=[k])

            op, value = self.handle_filter(v)
            arg2 = Constant(value=value)
            ast_com = BinaryOperation(op=op, args=[arg1, arg2])
            if ast_filter is None:
                ast_filter = ast_com
            else:
                ast_filter = BinaryOperation(op='and', args=[
                    ast_filter,
                    ast_com
                ])
        return ast_filter

    def handle_filter(self, value):
        ops = {
            '$ge': '>=',
            '$gt': '>',
            '$lt': '<',
            '$le': '<=',
            '$ne': '!=',
            '$eq': '='
        }
        in_ops = {
            '$in': 'in',
            '$nin': 'not in'
        }

        if isinstance(value, dict):
            key, value = list(value.items())[0]
            if key in ops:
                op = ops[key]
                return op, value

            if key in in_ops:
                op = in_ops[key]
                if not isinstance(value, list):
                    raise NotImplementedError(f'Unknown type {key}, {value}')
                value = Tuple(value)

                return op, value

            raise NotImplementedError(f'Unknown type {key}')

        elif isinstance(value, list):
            raise NotImplementedError(f'Unknown filter {value}')
        else:
            # is simple type
            op = '='
            value = value
            return op, value


class MongoWhereParser:
    def __init__(self, query):
        self.query = query

        # Create dispatch table for AST node handlers
        ast_type_map = {
            py_ast.BoolOp: self._handle_boolop,
            py_ast.Compare: self._handle_compare,
            py_ast.Name: self._handle_name,
            py_ast.Attribute: self._handle_attr,
        }
        # For Python 3.8+, all literals are py_ast.Constant
        if hasattr(py_ast, "Constant"):
            ast_type_map[py_ast.Constant] = self._handle_const
        # For <=3.7, need .Num and .Str
        if hasattr(py_ast, "Num"):
            ast_type_map[py_ast.Num] = self._handle_num
        if hasattr(py_ast, "Str"):
            ast_type_map[py_ast.Str] = self._handle_str

        self._ast_type_map = ast_type_map

    def to_ast(self):
        # parse as python string
        # replace '=' with '=='
        query = _EQ_RE.sub(_replace_eq, self.query)
        tree = py_ast.parse(query, mode='eval')
        return self.process(tree.body)

    def process(self, node):
        handler = self._ast_type_map.get(type(node))
        if handler:
            return handler(node)
        raise NotImplementedError(f'Unknown node {node}')

    def compare_op(self, op):

        opname = op.__class__.__name__

        # TODO: in, not

        ops = {
            'Eq': '=',
            'NotEq': '!=',
            'Gt': '>',
            'Lt': '<',
            'GtE': '>=',
            'LtE': '<=',
        }
        if opname not in ops:
            raise NotImplementedError(f'Unknown $where op: {opname}')
        return ops[opname]

    @staticmethod
    def test(cls):
        assert cls('this.a ==1 and "te" >= latest').to_string() == "a = 1 AND 'te' >= LATEST"

    def _handle_boolop(self, node):
        op = node.op.__class__.__name__
        # Use reduce to fold for efficiency
        processed_args = [self.process(v) for v in node.values]
        return reduce(lambda a, b: BinaryOperation(op=op, args=[a, b]), processed_args)

    def _handle_compare(self, node):
        if len(node.ops) != 1:
            raise NotImplementedError(f'Multiple ops {node.ops}')
        op = self.compare_op(node.ops[0])
        arg1 = self.process(node.left)
        arg2 = self.process(node.comparators[0])
        return BinaryOperation(op=op, args=[arg1, arg2])

    def _handle_name(self, node):
        if node.id == 'latest':
            return Latest()
        raise NotImplementedError(f'Unknown variable {node.id}')

    def _handle_const(self, node):
        return Constant(value=node.value)

    def _handle_num(self, node):
        return Constant(value=node.n)

    def _handle_str(self, node):
        return Constant(value=node.s)

    def _handle_attr(self, node):
        if getattr(node.value, 'id', None) != 'this':
            raise NotImplementedError(f'Unknown variable {getattr(node.value, "id", None)}')
        return Identifier(parts=[node.attr])

def _replace_eq(match):
    return f'{match.group(1)}=={match.group(2)}'

_EQ_RE = re.compile(r'([^=><])=([^=])')
