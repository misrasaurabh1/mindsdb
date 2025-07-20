class Responder:
    def __init__(self, when=None, result=None):
        # Direct assignment and validation for better performance
        self.when = when
        self.result = result
        # Use tuple type checks for single isinstance call
        if not isinstance(self.when, (dict, type(lambda: None))):
            raise ValueError("Responder attr 'when' must be dict or function.")
        if not isinstance(self.result, (dict, type(lambda: None))):
            raise ValueError("Responder attr 'result' must be dict or function.")

    def match(self, query):
        """check, if this 'responder' can be used to answer or current request

        query (dict): request document

        return bool
        """
        w = self.when
        if isinstance(w, dict):
            q = query
            for key, value in w.items():
                try:
                    q_val = q[key]
                except KeyError:
                    return False
                if callable(value):
                    if not value(q_val):
                        return False
                elif value != q_val:
                    return False
            return True
        else:
            return w(query)

    def handle(self, query, args, env, session):
        """making answer based on params:

        query (dict): document(s) from request
        args (dict): all other significant information from request: flags, collection name, rows to return, etc
        env (dict): config, model_controller instance, and other mindsdb related stuff
        session (object): current session

        returns documents as dict or list of dicts
        """
        if isinstance(self.result, dict):
            return self.result
        else:
            return self.result(query, args, env, session)
