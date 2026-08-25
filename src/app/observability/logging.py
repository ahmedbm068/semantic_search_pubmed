import logging, json, sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {"level": record.levelname, "message": record.getMessage(), "logger": record.name}
        return json.dumps(obj)

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.INFO)
    root.addHandler(handler)
