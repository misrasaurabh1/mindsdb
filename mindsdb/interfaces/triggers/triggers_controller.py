from mindsdb_sql_parser.ast import Identifier

from mindsdb_sql_parser import parse_sql, ParsingException

from mindsdb.interfaces.storage import db
from mindsdb.interfaces.database.projects import ProjectController
from mindsdb.utilities.context import context as ctx
from mindsdb.utilities.config import config

from mindsdb.api.executor.controllers.session_controller import SessionController


class TriggersController:
    OBJECT_TYPE = 'trigger'

    def add(self, name, project_name, table, query_str, columns=None):
        name = name.lower()

        if project_name is None:
            project_name = config.get('default_project')
        project_controller = ProjectController()
        project = project_controller.get(name=project_name)

        from mindsdb.api.executor.controllers.session_controller import SessionController
        session = SessionController()

        # check exists
        trigger = self.get_trigger_record(name, project_name)
        if trigger is not None:
            raise Exception(f'Trigger already exists: {name}')

        # check table
        if len(table.parts) < 2:
            raise Exception(f'Database or table not found: {table}')

        table_name = Identifier(parts=table.parts[1:]).to_string()
        db_name = table.parts[0]

        db_integration = session.integration_controller.get(db_name)
        db_handler = session.integration_controller.get_data_handler(db_name)

        if not hasattr(db_handler, 'subscribe'):
            raise Exception(f'Handler {db_integration["engine"]} does''t support subscription')

        df = db_handler.get_tables().data_frame
        column = 'table_name'
        if column not in df.columns:
            column = df.columns[0]
        tables = list(df[column])

        # check only if tables are visible
        if len(tables) > 0 and table_name not in tables:
            raise Exception(f'Table {table_name} not found in {db_name}')

        columns_str = None
        if columns is not None and len(columns) > 0:
            # join to string with delimiter
            columns_str = '|'.join([col.parts[-1] for col in columns])

        # check sql
        try:
            parse_sql(query_str)
        except ParsingException as e:
            raise ParsingException(f'Unable to parse: {query_str}: {e}')

        # create job record
        record = db.Triggers(
            name=name,
            project_id=project.id,

            database_id=db_integration['id'],
            table_name=table_name,
            query_str=query_str,
            columns=columns_str
        )
        db.session.add(record)
        db.session.flush()

        task_record = db.Tasks(
            company_id=ctx.company_id,
            user_class=ctx.user_class,

            object_type=self.OBJECT_TYPE,
            object_id=record.id,
        )
        db.session.add(task_record)
        db.session.commit()

    def delete(self, name, project_name):
        # check exists

        trigger = self.get_trigger_record(name, project_name)
        if trigger is None:
            raise Exception(f"Trigger doesn't exist: {name}")

        task = db.Tasks.query.filter(
            db.Tasks.object_type == self.OBJECT_TYPE,
            db.Tasks.object_id == trigger.id,
            db.Tasks.company_id == ctx.company_id,
        ).first()

        if task is not None:
            db.session.delete(task)

        db.session.delete(trigger)

        db.session.commit()

    def get_trigger_record(self, name, project_name):
        project_controller = ProjectController()
        project = project_controller.get(name=project_name)

        query = db.session.query(
            db.Triggers
        ).join(
            db.Tasks, db.Triggers.id == db.Tasks.object_id
        ).filter(
            db.Triggers.project_id == project.id,
            db.Triggers.name == name,
            db.Tasks.object_type == self.OBJECT_TYPE,
            db.Tasks.company_id == ctx.company_id,
        )
        return query.first()

    def get_list(self, project_name=None):
        # Fast-path: use lazy controller construction
        query = db.session.query(
            db.Tasks.object_id,
            db.Triggers.project_id,
            db.Triggers.name,
            db.Triggers.database_id,
            db.Triggers.table_name,
            db.Triggers.query_str,
            db.Tasks.last_error,
        ).join(
            db.Triggers, db.Triggers.id == db.Tasks.object_id
        ).filter(
            db.Tasks.object_type == self.OBJECT_TYPE,
            db.Tasks.company_id == ctx.company_id,
        )

        project_controller = None
        project_id = None
        if project_name is not None:
            if project_controller is None:
                project_controller = ProjectController()
            # Directly cache project.id to avoid extra attribute access
            project = project_controller.get(name=project_name)
            project_id = project.id
            query = query.filter(db.Triggers.project_id == project_id)

        # Fetch all needed records at once for mapping
        records = query.all()
        if not records:
            return []

        # Only fetch project and database info for those rows actually present
        project_ids = {r.project_id for r in records}
        database_ids = {r.database_id for r in records}
        
        # If controller wasn't built yet and we need list
        if project_controller is None:
            project_controller = ProjectController()
        projects = project_controller.get_list()
        project_names = {p.id: p.name for p in projects if p.id in project_ids}
        
        session = SessionController()  # Only now, because .database_controller used
        db_map = {i['id']: i['name'] for i in session.database_controller.get_list() if i['id'] in database_ids}

        # Build result list using fast local vars
        pn = project_names
        dn = db_map
        data = [
            {
                'id': rec.object_id,
                'project': pn.get(rec.project_id, '?'),
                'name': rec.name.lower(),
                'database': dn.get(rec.database_id, '?'),
                'table': rec.table_name,
                'query': rec.query_str,
                'last_error': rec.last_error,
            }
            for rec in records
        ]
        return data
