from io import BytesIO
from typing import List, Text

import pandas as pd

from mindsdb.integrations.libs.api_handler import APIResource
from mindsdb.integrations.utilities.sql_utils import FilterCondition, SortColumn

from mindsdb.integrations.utilities.files.file_reader import FileReader


class ListFilesTable(APIResource):
    """
    The table abstraction for querying the files (tables) in Microsoft OneDrive.
    """

    def list(
        self,
        conditions: List[FilterCondition] = None,
        limit: int = None,
        sort: List[SortColumn] = None,
        targets: List[Text] = None,
        **kwargs,
    ):
        """
        Lists the files in Microsoft OneDrive.

        Args:
            conditions (List[FilterCondition]): The conditions to filter the files.
            limit (int): The maximum number of files to return.
            sort (List[SortColumn]): The columns to sort the files by.
            targets (List[Text]): The columns to return in the result.

        Returns:
            pd.DataFrame: The list of files in Microsoft OneDrive based on the specified clauses.
        """
        client = self.handler.connect()
        files = client.get_all_items()

        # Pre-check targets to avoid checks and computations per loop
        need_content = targets and "content" in targets
        need_content_if_selectstar = not targets
        # If not targets but 'content' may or may not be wanted, handle explicitly
        # In both cases, we want to add a "content" column

        # Gather all file entries in dicts in one pass with a list comprehension (faster than loop+append)
        if need_content or need_content_if_selectstar:
            # Preallocate None, only fetch for requested
            content_dict = {}
            if need_content:
                # Only fetch content for those files when "content" is in targets
                for file in files:
                    content_dict[file["path"]] = client.get_item_content(file["path"])
            data = [
                {
                    "name": file["name"],
                    "path": file["path"],
                    "extension": file["name"].rsplit(".", 1)[-1],  # slightly faster for single split
                    "content": (content_dict.get(file["path"]) if need_content else None),
                }
                for file in files
            ]
        else:
            # Don't generate the content column at all for efficiency if not needed
            data = [
                {"name": file["name"], "path": file["path"], "extension": file["name"].rsplit(".", 1)[-1]}
                for file in files
            ]

        # Use pd.DataFrame.from_records which is optimal for list-of-dict
        df = pd.DataFrame.from_records(data)
        return df

    def get_columns(self):
        return ["name", "path", "extension", "content"]


class FileTable(APIResource):
    """
    The table abstraction for querying the content of a file (table) in Microsoft OneDrive.
    """

    def list(self, targets: List[str] = None, table_name=None, *args, **kwargs) -> pd.DataFrame:
        """
        Retrieves the content of the specified file (table) in Microsoft OneDrive.

        Args:
            targets (List[str]): The columns to return in the result.
            table_name (str): The name of the file (table) to retrieve.

        Returns:
            pd.DataFrame: The content of the specified file (table) in Microsoft OneDrive.
        """
        client = self.handler.connect()

        file_content = client.get_item_content(table_name)

        reader = FileReader(file=BytesIO(file_content), name=table_name)

        return reader.get_page_content()
