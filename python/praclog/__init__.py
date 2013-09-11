import logging
from praclog.logformat import RainbowLoggingHandler
import sys

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

handler = RainbowLoggingHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root_logger.addHandler(handler)

