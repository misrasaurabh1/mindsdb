from mindsdb.api.mongo.classes import Responder
import mindsdb.api.mongo.functions as helpers


class Responce(Responder):
    when = {"listIndexes": helpers.is_true}

    def result(self, query, request_env, mindsdb_env, session):
        # Fast local variable access for the two fields
        db = query["$db"]
        table = query["listIndexes"]
        # Copy the static structure and just patch the 'ns' value
        index = _INDEX_CORE.copy()
        index["ns"] = f"{db}.{table}"

        return {"cursor": [index], "ok": 1}


responder = Responce()

_INDEX_CORE = {
    "v": 2,
    "key": {"_id": 1},
    "name": "_id_",
}
