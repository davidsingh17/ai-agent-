from loguru import logger
logger.add("logs/app.log", rotation="10 MB", retention="7 days", backtrace=True, diagnose=True, level="INFO")
