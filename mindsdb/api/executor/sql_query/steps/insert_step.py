from mindsdb_sql_parser.ast import (
    Identifier,
)

from mindsdb.api.executor.planner.steps import SaveToTable, InsertToTable, CreateTableStep
from mindsdb.api.executor.sql_query.result_set import ResultSet, Column
from mindsdb.api.executor.exceptions import NotSupportedYet, LogicError
from mindsdb.integrations.libs.response import INF_SCHEMA_COLUMNS_NAMES

from .base import BaseStepCall


class InsertToTableCall(BaseStepCall):
    bind = InsertToTable

    def call(self, step):
        is_replace = False
        is_create = False

        if type(step) == SaveToTable:
            is_create = True
            if step.is_replace:
                is_replace = True

        if len(step.table.parts) > 1:
            integration_name = step.table.parts[0]
            table_name = Identifier(parts=step.table.parts[1:])
        else:
            integration_name = self.context["database"]
            table_name = step.table

        dn = self.session.datahub.get(integration_name)

        if not hasattr(dn, "create_table"):
            raise NotSupportedYet(f"Creating table in '{integration_name}' is not supported")

        if step.dataframe is not None:
            data = self.steps_data[step.dataframe.step_num]
        elif step.query is not None:
            data = ResultSet()
            if step.query.columns is None:
                # Query is: INSERT INTO table VALUES (...)
                table_columns_df = dn.get_table_columns_df(str(table_name))
                columns_names = table_columns_df[INF_SCHEMA_COLUMNS_NAMES.COLUMN_NAME].to_list()
                # Bulk create columns
                data._columns.extend(Column(name=col) for col in columns_names)  # <--- OPTIMIZED bulk add
            else:
                # Query is: INSERT INTO table (column_name, ...) VALUES (...)
                data._columns.extend(Column(name=col.name) for col in step.query.columns)  # <--- OPTIMIZED bulk add

            # Fast construction of value records as a list
            values_are_identifiers = False
            if step.query.values and any(isinstance(v, Identifier) for row in step.query.values for v in row):
                # Only if any value is an Identifier, enable slow path
                values_are_identifiers = True

            # Fast: no Identifiers to check, use list comprehension
            if not values_are_identifiers:
                records = [[v.value for v in row] for row in step.query.values]
            else:
                records = []
                for row in step.query.values:
                    record = []
                    for v in row:
                        if isinstance(v, Identifier) and v.parts[0] == "None":
                            record.append(None)
                            continue
                        record.append(v.value)
                    records.append(record)
            data.add_raw_values(records)
        else:
            raise LogicError(f"Data not found for insert: {step}")

        # Remove 'service' columns using a single pass
        service_cols = {"__mindsdb_row_id", "__mdb_forecast_offset"}
        # Keep reference to columns to avoid repeated function call
        columns_to_remove = [col for col in data.columns if col.name in service_cols]
        for col in columns_to_remove:
            data.del_column(col)

        # region del columns filtered at projection step (faster set-based filtering)
        columns_list = self.get_columns_list()
        if columns_list is not None:
            filtered_column_names = {x.name for x in columns_list}
            to_remove = [
                col
                for col in data.columns
                if not col.name.startswith("predictor.") and col.name not in filtered_column_names
            ]
            for col in to_remove:
                data.del_column(col)
        # endregion

        # Drop double aliases with a single sweep (preserve order, more efficient)
        seen_aliases = set()
        cols_to_drop = []
        for col in data.columns:
            if col.alias in seen_aliases:
                cols_to_drop.append(col)
            else:
                seen_aliases.add(col.alias)
        for col in cols_to_drop:
            data.del_column(col)

        response = dn.create_table(
            table_name=table_name, result_set=data, is_replace=is_replace, is_create=is_create, params=step.params
        )
        return ResultSet(affected_rows=response.affected_rows)


class SaveToTableCall(InsertToTableCall):
    bind = SaveToTable


class CreateTableCall(BaseStepCall):
    bind = CreateTableStep

    def call(self, step):
        if len(step.table.parts) > 1:
            integration_name = step.table.parts[0]
            table_name = Identifier(parts=step.table.parts[1:])
        else:
            integration_name = self.context["database"]
            table_name = step.table

        dn = self.session.datahub.get(integration_name)

        dn.create_table(table_name=table_name, columns=step.columns, is_replace=step.is_replace, is_create=True)
        return ResultSet()
