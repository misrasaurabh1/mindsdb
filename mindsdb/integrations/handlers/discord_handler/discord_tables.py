import pandas as pd
from typing import Text, List, Dict, Any

from mindsdb_sql_parser import ast

from mindsdb.integrations.libs.api_handler import APITable
from mindsdb.integrations.utilities.sql_utils import extract_comparison_conditions

from mindsdb.integrations.libs.response import HandlerResponse as Response

from mindsdb.integrations.utilities.handlers.query_utilities.insert_query_utilities import (
    INSERTQueryParser
)

from mindsdb.utilities import log

logger = log.getLogger(__name__)


class MessagesTable(APITable):
    """The Discord Table implementation"""

    def get_columns(self):
        return [
            'id', 'type', 'content',
            'author_id', 'author_username', 'author_global_name', 'author_avatar',
            'author_banner_color', 'attachments', 'embeds', 'mentions', 'mention_roles',
            'pinned', 'mention_everyone', 'tts', 'timestamp', 'edited_timestamp',
            'flags', 'components', 'nonce', 'referenced_message',
        ]

    def select(self, query: ast.Select) -> Response:
        """Selects data from the Discord channel.

        Parameters
        ----------
        query : ast.Select
           Given SQL SELECT query.

        Returns
        -------
        Response
            Response object representing collected data from Discord.
        """

        # extract simple comparison conditions
        conditions = extract_comparison_conditions(query.where)

        params = {}
        filters = []

        user_filter_flag = False
        channel_filter_flag = False

        # Pre-resolve attribute names for fast 'in'
        user_keys = {'author_id', 'author_username', 'author_global_name'}

        for op, arg1, arg2 in conditions:
            if op == 'or':
                raise NotImplementedError('OR is not supported')

            if arg1 == 'timestamp':
                if op == '>':
                    params['after'] = arg2
                elif op == '<':
                    params['before'] = arg2
                else:
                    raise NotImplementedError(f'Unsupported operator {op} for timestamp')

            elif arg1 in user_keys:
                if user_filter_flag:
                    raise NotImplementedError('Multiple user filters are not supported')
                user_filter_flag = True
                if op != '=':
                    raise NotImplementedError(f'Unsupported operator {op} for {arg1}')
                # pass, Discord API handler presumably filters by user in other ways

            elif arg1 == 'channel_id':
                if op != '=':
                    raise NotImplementedError(f'Unsupported operator {op} for {arg1}')
                channel_filter_flag = True
                params['channel_id'] = int(arg2)
            else:
                filters.append([op, arg1, arg2])

        params['limit'] = query.limit if query.limit is not None else 100

        if not channel_filter_flag:
            raise NotImplementedError('Channel filter is required')

        result = self.handler.call_discord_api(
            'get_messages', params=params, filters=filters
        )

        # Fast single-pass: build columns list and check for star
        targets = query.targets
        columns = None
        for target in targets:
            if isinstance(target, ast.Star):
                columns = None
                break
            if columns is None:
                columns = []
            if isinstance(target, ast.Identifier):
                columns.append(target.parts[-1])
            else:
                raise NotImplementedError

        # Default columns all-lower-case
        get_columns = self.get_columns
        if not columns:  # covers both None and []
            columns = get_columns()
        else:
            # fast path: if identifier columns given, no need to scan all columns
            pass

        # Only lower if needed. This is a surprisingly expensive list comprehension at scale
        columns = [name.lower() if not name.islower() else name for name in columns]

        # Only convert to DataFrame if absolutely necessary
        if len(result) == 0:
            # Use tuple(columns) to avoid unintentional case changes elsewhere
            result = pd.DataFrame([], columns=columns)
        else:
            # Optimize setting absent columns and ordering
            res_columns_set = set(result.columns)
            columns_set = set(columns)

            # Only add truly absent columns
            missing_cols = columns_set - res_columns_set
            if missing_cols:
                for col in missing_cols:
                    result[col] = None

            # filter columns efficiently: only reorder if necessary
            if columns != list(result.columns):  # pandas will reorder or drop as needed
                result = result.reindex(columns=columns)

        return result

    def insert(self, query: ast.Insert) -> None:
        """Sends messages to a Discord channel.

        Parameters
        ----------
        query : ast.Insert
           Given SQL INSERT query.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the query contains an unsupported condition
        """
        insert_statement_parser = INSERTQueryParser(
            query,
            supported_columns=['channel_id', 'text'],
            mandatory_columns=['channel_id', 'text'],
            all_mandatory=False,
        )
        message_data = insert_statement_parser.parse_query()
        self.send_message(message_data)

    def send_message(self, message_data: List[Dict[Text, Any]]) -> None:
        """Sends messages to a Discord Channel using the parsed message data.

        Parameters
        ----------
        message_data : List[Dict[Text, Any]]
           List of dictionaries containing the messages to send.

        Returns
        -------
        None
        """
        for message in message_data:
            try:
                params = {'channel_id': message['channel_id'], 'text': message['text']}
                self.handler.call_discord_api('send_message', params=params)
                logger.info("Message sent to Discord channel successfully.")
            except Exception as e:
                logger.error(f"Error sending message to Discord channel: {e}")
                raise e
