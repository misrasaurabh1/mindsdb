from mindsdb.integrations.handlers.dockerhub_handler.dockerhub_tables import (
    DockerHubRepoImagesSummaryTable,
    DockerHubRepoImagesTable,
    DockerHubRepoTagTable,
    DockerHubRepoTagsTable,
    DockerHubOrgSettingsTable,
)
from mindsdb.integrations.handlers.dockerhub_handler.dockerhub import DockerHubClient
from mindsdb.integrations.libs.api_handler import APIResource, APIHandler
from mindsdb.integrations.libs.response import (
    RESPONSE_TYPE,
    HandlerResponse as Response,
    HandlerStatusResponse as StatusResponse,
)

from mindsdb.utilities import log
from mindsdb_sql_parser import parse_sql
import pandas as pd
from functools import lru_cache
from mindsdb_sql_parser.ast import ASTNode, Delete, Insert, Select, Star, Update

logger = log.getLogger(__name__)


class DockerHubHandler(APIHandler):
    """The DockerHub handler implementation"""

    def __init__(self, name: str, **kwargs):
        """Initialize the DockerHub handler.

        Parameters
        ----------
        name : str
            name of a handler instance
        """
        super().__init__(name)

        connection_data = kwargs.get("connection_data", {})
        self.connection_data = connection_data
        self.kwargs = kwargs
        self.docker_client = DockerHubClient()
        self.is_connected = False

        # Set up tables only once
        self._register_table("repo_images_summary", DockerHubRepoImagesSummaryTable(self))
        self._register_table("repo_images", DockerHubRepoImagesTable(self))
        self._register_table("repo_tag_details", DockerHubRepoTagTable(self))
        self._register_table("repo_tags", DockerHubRepoTagsTable(self))
        self._register_table("org_settings", DockerHubOrgSettingsTable(self))

    def connect(self) -> StatusResponse:
        """Set up the connection required by the handler.

        Returns
        -------
        StatusResponse
            connection object
        """
        resp = StatusResponse(False)
        status = self.docker_client.login(self.connection_data.get("username"), self.connection_data.get("password"))
        if status["code"] != 200:
            resp.success = False
            resp.error_message = status["error"]
            return resp
        self.is_connected = True
        return resp

    def check_connection(self) -> StatusResponse:
        """Check connection to the handler.

        Returns
        -------
        StatusResponse
            Status confirmation
        """
        response = StatusResponse(False)

        try:
            status = self.docker_client.login(
                self.connection_data.get("username"), self.connection_data.get("password")
            )
            if status["code"] == 200:
                current_user = self.connection_data.get("username")
                logger.info(f"Authenticated as user {current_user}")
                response.success = True
            else:
                response.success = False
                logger.info("Error connecting to dockerhub. " + status["error"])
                response.error_message = status["error"]
        except Exception as e:
            logger.error(f"Error connecting to DockerHub API: {e}!")
            response.error_message = e

        self.is_connected = response.success
        return response

    def native_query(self, query: str) -> StatusResponse:
        """Receive and process a raw query.

        Parameters
        ----------
        query : str
            query in a native format

        Returns
        -------
        StatusResponse
            Request status
        """
        # Memoized parser for repeat queries, fallback to normal parse_sql if needed
        ast = cached_parse_sql(query)
        return self.query(ast)

    def query(self, query: ASTNode):
        """
        Process parsed query and dispatch to the appropriate table method.
        """
        # Direct attribute lookups
        if isinstance(query, Select):
            table_obj = self._get_table(query.from_table)
            # Fast method member lookup
            list_method = getattr(table_obj, "list", None)
            if not list_method or (hasattr(list_method, "__func__") and list_method.__func__ is APIResource.list):
                # Backwards compatibility: targets wasn't passed in previous version
                query.targets = [Star()]
            result = table_obj.select(query)
        elif isinstance(query, Update):
            table_obj = self._get_table(query.table)
            result = table_obj.update(query)
        elif isinstance(query, Insert):
            table_obj = self._get_table(query.table)
            result = table_obj.insert(query)
        elif isinstance(query, Delete):
            table_obj = self._get_table(query.table)
            result = table_obj.delete(query)
        else:
            raise NotImplementedError

        # Return proper response type
        if result is None:
            return Response(RESPONSE_TYPE.OK)
        elif isinstance(result, pd.DataFrame):
            return Response(RESPONSE_TYPE.TABLE, result)
        else:
            raise NotImplementedError


# Memoize parse_sql for fast repeated queries; you can tune maxsize as needed.
@lru_cache(maxsize=512)
def cached_parse_sql(query: str):
    return parse_sql(query)
