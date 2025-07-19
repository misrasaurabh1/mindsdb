from dataclasses import dataclass, astuple
from datetime import datetime


class TABLES_ROW_TYPE:
    __slots__ = ()
    BASE_TABLE = 'BASE TABLE'
    VIEW = 'VIEW'
    SYSTEM_VIEW = 'SYSTEM VIEW'


TABLES_ROW_TYPE = TABLES_ROW_TYPE()


@dataclass(slots=True)
class TablesRow:
    TABLE_CATALOG: str = 'def'
    TABLE_SCHEMA: str = 'information_schema'
    TABLE_NAME: str = None
    TABLE_TYPE: str = TABLES_ROW_TYPE.BASE_TABLE
    ENGINE: str = None
    VERSION: int = None
    ROW_FORMAT: str = None
    TABLE_ROWS: int = 0
    AVG_ROW_LENGTH: int = 0
    DATA_LENGTH: int = 0
    MAX_DATA_LENGTH: int = 0
    INDEX_LENGTH: int = 0
    DATA_FREE: int = 0
    AUTO_INCREMENT: int = None
    CREATE_TIME: datetime = datetime(2024, 1, 1)
    UPDATE_TIME: datetime = datetime(2024, 1, 1)
    CHECK_TIME: datetime = datetime(2024, 1, 1)
    TABLE_COLLATION: str = None
    CHECKSUM: int = None
    CREATE_OPTIONS: str = None
    TABLE_COMMENT: str = ''

    def to_list(self) -> list:
        return list(astuple(self))

    @staticmethod
    def from_dict(data: dict):
        # Uppercase keys once, and handle 'TABLE_NAME'
        fields = TablesRow.__dataclass_fields__
        out = {}
        got_table_name = False
        for k, v in data.items():
            k_up = k.upper()
            if k_up == 'NAME' and 'TABLE_NAME' not in data and 'TABLE_NAME' not in out:
                k_up = 'TABLE_NAME'
                got_table_name = True
            if k_up in fields and (k_up != 'TABLE_NAME' or got_table_name or 'TABLE_NAME' in data):
                out[k_up] = v
        # In the rare case 'NAME' is the only source of TABLE_NAME, ensured above
        return TablesRow(**out)
