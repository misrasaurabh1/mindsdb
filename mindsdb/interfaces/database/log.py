from typing import List
from copy import deepcopy
from abc import ABC, abstractmethod
from collections import OrderedDict

import pandas as pd
from mindsdb_sql_parser import parse_sql
from mindsdb_sql_parser.ast import Select, Identifier, Star, BinaryOperation, Constant, Join, Function
from mindsdb_sql_parser.utils import JoinType

from mindsdb.utilities.render.sqlalchemy_render import SqlalchemyRender
from mindsdb.integrations.utilities.query_traversal import query_traversal
from mindsdb.utilities.functions import resolve_table_identifier
from mindsdb.api.executor.utilities.sql import get_query_tables
from mindsdb.utilities.exception import EntityNotExistsError
import mindsdb.interfaces.storage.db as db
from mindsdb.utilities.context import context as ctx
from mindsdb.api.executor.datahub.classes.response import DataHubResponse
from mindsdb.api.executor.datahub.classes.tables_row import (
    TABLES_ROW_TYPE,
    TablesRow,
)


class LogTable(ABC):
    """Base class for 'table' entitie in internal 'log' database

    Attributes:
        name (str): name of the table
        deletable (bool): is it possible to delete a table
        visible (bool): should be table visible in GUI sidebar
        kind (str): type of the table/view
    """

    name: str
    deletable: bool = False
    visible: bool = True
    kind: str = "table"

    @staticmethod
    @abstractmethod
    def _get_base_subquery() -> Select:
        """Get a query that returns the table from internal db

        Returns:
            Select: 'select' query that returns table
        """
        pass

    @staticmethod
    def company_id_comparison(table_a: str, table_b: str) -> BinaryOperation:
        """Make statement for 'safe' comparison of company_id of two tables

        Args:
            table_a (str): name of first table
            table_b (str): name of second table

        Returns:
            BinaryOperation: statement that can be used for 'safe' comparison
        """
        table_a_company = f"{table_a}.company_id"
        table_b_company = f"{table_b}.company_id"
        return BinaryOperation(
            op="=",
            args=(
                Function(op="coalesce", args=(Identifier(table_a_company), 0)),
                Function(op="coalesce", args=(Identifier(table_b_company), 0)),
            ),
        )


class LLMLogTable(LogTable):
    name = "llm_log"

    columns = [
        "API_KEY",
        "MODEL_NAME",
        "INPUT",
        "OUTPUT",
        "START_TIME",
        "END_TIME",
        "PROMPT_TOKENS",
        "COMPLETION_TOKENS",
        "TOTAL_TOKENS",
        "SUCCESS",
    ]

    types_map = {"SUCCESS": "boolean", "START_TIME": "datetime64[ns]", "END_TIME": "datetime64[ns]"}

    @staticmethod
    def _get_base_subquery() -> Select:
        query = Select(
            targets=[
                Identifier("llm_log.api_key", alias=Identifier("api_key")),
                Identifier("predictor.name", alias=Identifier("model_name")),
                Identifier("llm_log.input", alias=Identifier("input")),
                Identifier("llm_log.output", alias=Identifier("output")),
                Identifier("llm_log.start_time", alias=Identifier("start_time")),
                Identifier("llm_log.end_time", alias=Identifier("end_time")),
                Identifier("llm_log.prompt_tokens", alias=Identifier("prompt_tokens")),
                Identifier("llm_log.completion_tokens", alias=Identifier("completion_tokens")),
                Identifier("llm_log.total_tokens", alias=Identifier("total_tokens")),
                Identifier("llm_log.success", alias=Identifier("success")),
            ],
            from_table=Join(
                left=Identifier("llm_log"),
                right=Identifier("predictor"),
                join_type=JoinType.LEFT_JOIN,
                condition=BinaryOperation(
                    op="and",
                    args=(
                        LLMLogTable.company_id_comparison("llm_log", "predictor"),
                        BinaryOperation(op="=", args=(Identifier("llm_log.model_id"), Identifier("predictor.id"))),
                    ),
                ),
            ),
            where=BinaryOperation(
                op="is" if ctx.company_id is None else "=",
                args=(Identifier("llm_log.company_id"), Constant(ctx.company_id)),
            ),
            alias=Identifier("llm_log"),
        )
        return query


class JobsHistoryTable(LogTable):
    name = "jobs_history"

    columns = ["NAME", "PROJECT", "RUN_START", "RUN_END", "ERROR", "QUERY"]
    types_map = {"RUN_START": "datetime64[ns]", "RUN_END": "datetime64[ns]"}

    @staticmethod
    def _get_base_subquery() -> Select:
        # Pre-assemble join conditions to avoid redundancy
        join_condition_left = BinaryOperation(
            op="and",
            args=(
                LogTable.company_id_comparison("jobs_history", "jobs"),
                BinaryOperation(op="=", args=(_JOBS_HISTORY_JOB_ID, _JOBS_ID)),
            ),
        )
        join_condition_right = BinaryOperation(
            op="and",
            args=(
                LogTable.company_id_comparison("project", "jobs"),
                BinaryOperation(op="=", args=(_PROJECT_ID, _JOBS_PROJECT_ID)),
            ),
        )

        # Prepare targets statically
        targets = [
            _JOBS_NAME,
            _PROJECT_NAME,
            _JH_START_AT,
            _JH_END_AT,
            _JH_ERROR,
            _JH_QUERY_STR,
        ]

        # WHERE clause, select operator only once
        if ctx.company_id is None:
            where_clause = BinaryOperation(
                op="is",
                args=(_JOBS_HISTORY_COMPANY_ID, Constant(None)),
            )
        else:
            where_clause = BinaryOperation(
                op="=",
                args=(_JOBS_HISTORY_COMPANY_ID, Constant(ctx.company_id)),
            )

        # Assemble join hierarchy
        join = Join(
            left=Join(
                left=_JOBS_HISTORY,
                right=_JOBS,
                join_type=JoinType.LEFT_JOIN,
                condition=join_condition_left,
            ),
            right=_PROJECT,
            join_type=JoinType.LEFT_JOIN,
            condition=join_condition_right,
        )

        # Compose final Select object
        query = Select(
            targets=targets,
            from_table=join,
            where=where_clause,
            alias=_JOBS_HISTORY,
        )
        return query


class LogDBController:
    def __init__(self):
        self._tables = OrderedDict()
        self._tables["llm_log"] = LLMLogTable
        self._tables["jobs_history"] = JobsHistoryTable

    def get_list(self) -> List[LogTable]:
        return list(self._tables.values())

    def get(self, name: str = None) -> LogTable:
        try:
            return self._tables[name]
        except KeyError:
            raise EntityNotExistsError(f"Table log.{name} does not exists")

    def get_tables(self) -> OrderedDict:
        return self._tables

    def get_tree_tables(self) -> OrderedDict:
        return self._tables

    def get_tables_rows(self) -> List[TablesRow]:
        return [
            TablesRow(TABLE_TYPE=TABLES_ROW_TYPE.SYSTEM_VIEW, TABLE_NAME=table_name)
            for table_name in self._tables.keys()
        ]

    def query(self, query: Select = None, native_query: str = None, session=None) -> DataHubResponse:
        if native_query is not None:
            if query is not None:
                raise Exception("'query' and 'native_query' arguments can not be used together")
            query = parse_sql(native_query)
        else:
            query = deepcopy(query)

        if type(query) is not Select:
            raise Exception("Only 'SELECT' is allowed for tables in log database")
        tables = get_query_tables(query)
        if len(tables) != 1:
            raise Exception("Only one table may be in query to log database")
        table = tables[0]
        if table[0] is not None and table[0].lower() != "log":
            raise Exception("This is not a query to the log database")
        if table[1].lower() not in self._tables.keys():
            raise Exception(f"There is no table '{table[1]}' in the log database")

        log_table = self._tables[table[1].lower()]

        # region check that only allowed identifiers are used in the query
        available_columns_names = [column.lower() for column in log_table.columns]

        def check_columns(node, is_table, **kwargs):
            # region replace * to available columns
            if type(node) is Select:
                new_targets = []
                for target in node.targets:
                    if type(target) is Star:
                        new_targets += [Identifier(name) for name in available_columns_names]
                    else:
                        new_targets.append(target)
                node.targets = new_targets
            # endregion

            if type(node) is Identifier and is_table is False:
                parts = resolve_table_identifier(node)
                if parts[0] is not None and parts[0].lower() not in self._tables:
                    raise Exception(f"Table '{parts[0]}' can not be used in query")
                if parts[1].lower() not in available_columns_names:
                    raise Exception(f"Column '{parts[1]}' can not be used in query")

        query_traversal(query, check_columns)
        # endregion

        query.from_table = log_table._get_base_subquery()

        render_engine = db.engine.name
        if render_engine == "postgresql":
            "postgres"
        render = SqlalchemyRender(render_engine)
        query_str = render.get_string(query, with_failback=False)
        df = pd.read_sql_query(query_str, db.engine)

        # region cast columns values to proper types
        for column_name, column_type in log_table.types_map.items():
            for df_column_name in df.columns:
                if df_column_name.lower() == column_name.lower() and df[df_column_name].dtype != column_type:
                    df[df_column_name] = df[df_column_name].astype(column_type)
        # endregion

        columns_info = [{"name": k, "type": v} for k, v in df.dtypes.items()]

        return DataHubResponse(data_frame=df, columns=columns_info)


_JOBS_NAME = Identifier("jobs.name", alias=Identifier("name"))

_PROJECT_NAME = Identifier("project.name", alias=Identifier("project"))

_JH_START_AT = Identifier("jobs_history.start_at", alias=Identifier("run_start"))

_JH_END_AT = Identifier("jobs_history.end_at", alias=Identifier("run_end"))

_JH_ERROR = Identifier("jobs_history.error", alias=Identifier("error"))

_JH_QUERY_STR = Identifier("jobs_history.query_str", alias=Identifier("query"))

_JOBS_HISTORY = Identifier("jobs_history")

_JOBS = Identifier("jobs")

_PROJECT = Identifier("project")

_PROJECT_ID = Identifier("project.id")

_JOBS_PROJECT_ID = Identifier("jobs.project_id")

_JOBS_HISTORY_JOB_ID = Identifier("jobs_history.job_id")

_JOBS_ID = Identifier("jobs.id")

_JOBS_HISTORY_COMPANY_ID = Identifier("jobs_history.company_id")
