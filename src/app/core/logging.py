from pathlib import Path
import logging, json, time, sys
from logging.handlers import RotatingFileHandler

class JSONFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        for k, v in getattr(record, "extra", {}).items():
            base[k] = v
        return json.dumps(base, ensure_ascii=False)

def setup_logging(log_path: str = "logs/app.log"):
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(p, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    json_formatter = JSONFormatter()
    file_handler.setFormatter(json_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Logs d'accès Uvicorn -> mêmes handlers
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = [file_handler, console_handler]
    uvicorn_access.propagate = False
