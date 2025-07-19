from typing import Optional

import pandas as pd
import duckdb

from mindsdb_sql_parser import parse_sql
from mindsdb.integrations.libs.base import DatabaseHandler

from mindsdb_sql_parser.ast.base import ASTNode

from mindsdb.utilities import log
from mindsdb.integrations.libs.response import (
    HandlerStatusResponse as StatusResponse,
    HandlerResponse as Response,
    RESPONSE_TYPE,
)


logger = log.getLogger(__name__)


class SheetsHandler(DatabaseHandler):
    """
    This handler handles connection and execution of the Airtable statements.
    """

    name = "sheets"

    def __init__(self, name: str, connection_data: Optional[dict], **kwargs):
        """
        Initialize the handler.
        Args:
            name (str): name of particular handler instance
            connection_data (dict): parameters for connecting to the database
            **kwargs: arbitrary keyword arguments.
        """
        # Initialize the handler.
        super().__init__(name)
        self.parser = parse_sql
        self.dialect = "sheets"
        self.connection_data = connection_data
        self.kwargs = kwargs

        self.connection = None
        self.is_connected = False
        self.sheet = None

    def __del__(self):
        if self.is_connected is True:
            self.disconnect()

    def connect(self) -> StatusResponse:
        """
        Set up the connection required by the handler.
        Returns:
            HandlerStatusResponse
        """
        # Set up the connection required by the handler.
        if self.is_connected and self.connection is not None:
            return self.connection

        conn_data = self.connection_data
        sheet_name = conn_data["sheet_name"]
        spreadsheet_id = conn_data["spreadsheet_id"]

        # Compose URL once
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

        # Read CSV to DataFrame (on_bad_lines is optimal for fast skipping)
        sheet_df = pd.read_csv(url, on_bad_lines="skip")

        # Create new duckdb connection and register DataFrame
        connection = duckdb.connect()
        connection.register(sheet_name, sheet_df)

        # Set instance attributes
        self.sheet = sheet_df
        self.connection = connection
        self.is_connected = True

        return connection

    def disconnect(self):
        """
        Close any existing connections.
        """
        if self.is_connected is False:
            return

        self.connection.close()
        self.is_connected = False
        return self.is_connected

    def check_connection(self) -> StatusResponse:
        """
        Check connection to the handler.
        Returns:
            HandlerStatusResponse
        """
        response = StatusResponse(False)
        need_to_close = self.is_connected is False

        try:
            self.connect()
            response.success = True
        except Exception as e:
            logger.error(f"Error connecting to the Google Sheet with ID {self.connection_data['spreadsheet_id']}, {e}!")
            response.error_message = str(e)
        finally:
            if response.success is True and need_to_close:
                self.disconnect()
            if response.success is False and self.is_connected is True:
                self.is_connected = False

        return response

    def native_query(self, query: str) -> StatusResponse:
        """
        Receive raw query and act upon it somehow.
        Args:
            query (str): query in native format
        Returns:
            HandlerResponse
        """

        need_to_close = self.is_connected is False
        connection = self.connect()
        try:
            result = connection.execute(query).fetchdf()
            if not result.empty:
                response = Response(RESPONSE_TYPE.TABLE, result)
            else:
                response = Response(RESPONSE_TYPE.OK)
                connection.commit()
        except Exception as e:
            logger.error(
                f"Error running query: {query} on the Google Sheet with ID {self.connection_data['spreadsheet_id']}!"
            )
            response = Response(RESPONSE_TYPE.ERROR, error_message=str(e))

        if need_to_close is True:
            self.disconnect()

        return response

    def query(self, query: ASTNode) -> StatusResponse:
        """
        Receive query as AST (abstract syntax tree) and act upon it somehow.
        Args:
            query (ASTNode): sql query represented as AST. May be any kind
                of query: SELECT, INTSERT, DELETE, etc
        Returns:
            HandlerResponse
        """
        return self.native_query(query.to_string())

    def get_tables(self) -> StatusResponse:
        """
        Return list of entities that will be accessible as tables.
        Returns:
            HandlerResponse
        """
        response = Response(
            RESPONSE_TYPE.TABLE, data_frame=pd.DataFrame([self.connection_data["sheet_name"]], columns=["table_name"])
        )

        return response

    def get_columns(self) -> StatusResponse:
        """
        Returns a list of entity columns.
        Args:
            table_name (str): name of one of tables returned by self.get_tables()
        Returns:
            HandlerResponse
        """
        response = Response(
            RESPONSE_TYPE.TABLE,
            data_frame=pd.DataFrame({"column_name": list(self.sheet.columns), "data_type": self.sheet.dtypes}),
        )

        return response
