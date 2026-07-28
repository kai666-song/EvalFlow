import logging
from pathlib import Path

def get_logger(name: str = "evalflow") -> logging.Logger:
    """创建同时输出到终端和文件的项目日志记录器。"""

    #自动创建日志目录。
    log_dir = Path("logs") 
    log_dir.mkdir(exist_ok=True)

    #获取一个名称为 evalflow 的日志记录器。
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 防止日志继续传递给根日志器，避免重复输出。
    logger.propagate = False

    # FastAPI 开发模式会自动重载。
    # 已经存在 Handler 时直接返回，避免重复添加。
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # 输出到 powershell
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 输出到 logs/app.log
    file_handler = logging.FileHandler(
        log_dir / "app.log",
        encoding = "utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger