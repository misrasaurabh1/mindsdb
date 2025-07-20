from mindsdb_sql_parser import ast
from typing import Text, List, Optional

from .exceptions import UnsupportedColumnException

from mindsdb.integrations.utilities.handlers.query_utilities.base_query_utilities import BaseQueryParser
from mindsdb.integrations.utilities.handlers.query_utilities.base_query_utilities import BaseQueryExecutor


class UPDATEQueryParser(BaseQueryParser):
    """
    Parses an UPDATE query into its component parts.

    Parameters
    ----------
    query : ast.Update
        Given SQL UPDATE query.
    supported_columns : List[Text], Optional
        List of columns supported by the table for updating.
    """

    def __init__(self, query: ast.Update, supported_columns: Optional[List[Text]] = None):
        super().__init__(query)
        # Convert supported_columns to set for much faster lookup if given and not already a set.
        if supported_columns is not None and not isinstance(supported_columns, set):
            self._supported_columns_set = set(supported_columns)
        else:
            self._supported_columns_set = supported_columns  # could be None or already a set

    def parse_query(self):
        """
        Parses a SQL UPDATE statement into its components: the columns and values to update as a dictionary, and the WHERE conditions.
        """
        values_to_update = self.parse_set_clause()
        where_conditions = self.parse_where_clause()
        return values_to_update, where_conditions

    def parse_set_clause(self):
        """
        Parses the SET clause of the query and returns a dictionary of columns and values to update.
        """
        update_cols = self.query.update_columns
        supported = self._supported_columns_set

        # Fast path: if supported is None, just return the mapping
        if supported is None:
            return {k: v.value for k, v in update_cols.items()}

        # Otherwise, check and build in one loop, O(1) per check.
        values_to_update = {}
        for col, val in update_cols.items():
            if col not in supported:
                raise UnsupportedColumnException(f"Unsupported column: {col}")
            values_to_update[col] = val.value
        return values_to_update


class UPDATEQueryExecutor(BaseQueryExecutor):
    """
    Executes an UPDATE query.

    Parameters
    ----------
    df : pd.DataFrame
        Given table.
    where_conditions : List[List[Text]]
        WHERE conditions of the query.

    NOTE: This class DOES NOT update the relevant records of the entity for you, it will simply return the records that need to be updated based on the WHERE conditions.

          This class expects all of the entities to be passed in as a DataFrane and filters out the relevant records based on the WHERE conditions.
          Because all of the records need to be extracted to be passed in as a DataFrame, this class is not very computationally efficient.
          Therefore, DO NOT use this class if the API/SDK that you are using supports updating records in bulk.
    """
