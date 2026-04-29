import logging
import logging.handlers
import os

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("product_catalog")
logger.setLevel(logging.INFO)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_fh = logging.handlers.RotatingFileHandler("logs/app.log", maxBytes=5_000_000, backupCount=3)
_fh.setFormatter(_fmt)

_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)

logger.addHandler(_fh)
logger.addHandler(_sh)
