from mindsdb.api.mongo.classes import Responder
from mindsdb.utilities.context import context as ctx


class Responce(Responder):
    def when(self, query):
        return "company_id" in query

    def result(self, query, request_env, mindsdb_env, session):
        # Fast-path: if need_response is True, return immediately without context assignments
        need_response = query.get("need_response", False)
        if need_response:
            return {"ok": 1}

        company_id = query.get("company_id")
        if ctx.company_id != company_id:
            ctx.company_id = company_id

        user_class = query.get("user_class", 0)
        if ctx.user_class != user_class:
            ctx.user_class = user_class

        email_confirmed = query.get("email_confirmed", 1)
        if ctx.email_confirmed != email_confirmed:
            ctx.email_confirmed = email_confirmed

        return None


responder = Responce()
