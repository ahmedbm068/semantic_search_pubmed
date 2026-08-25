import logging, sys
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
h = logging.StreamHandler(sys.stdout)
h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.handlers = []
logger.addHandler(h)
