import logging
from logging import handlers
import os
from multiprocessing import Queue, Event
from datetime import datetime
from .courier import LogMessage


class Log:
    _CRITICAL = logging.CRITICAL
    _ERROR = logging.ERROR
    _WARNING = logging.WARNING
    _INFO = logging.INFO
    _DEBUG = logging.DEBUG

    def __init__(self, process_event: Event, log_level=logging.INFO, log_folder=None, log_file=None, log_environment=None) -> None:
        self._process_event = process_event

        self.log_level = log_level
        self.log_folder = log_folder
        self.log_environment = log_environment
        if log_folder is not None:
            self.log_folder = log_folder.replace("\\", "/")
        self.log_file = log_file
        if log_file is not None:
            self.log_file = log_file.replace("\\", "/")

        self.log_queue = Queue()

        self.configure()
    
    def configure(self):
        handlers = [logging.StreamHandler()]
        if self.log_folder is not None or self.log_file is not None:
            if self.log_folder is not None and self.log_file is not None:
                if len(self.log_file.split("/")) > 1:
                    self.log_queue.put(LogMessage("Logger", "Log supplied with two filepaths - defaulting to inputted log_file", Log._ERROR))
                    handlers.append(logging.FileHandler(self.log_file))
                else:
                    if self.log_file[0] == "/":
                        self.log_file = self.log_file[1:]
                    handlers.append(logging.FileHandler(os.path.join(self.log_folder, self.log_file)))
            elif self.log_file is not None:
                handlers.append(logging.FileHandler(self.log_file))
            else:
                if self.log_folder.startswith("/"):
                    self.log_folder = self.log_folder[1:]
                handlers.append(logging.FileHandler(os.path.join(os.getcwd(), self.log_folder, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")))
        if self.log_environment is not None:
            if len(handlers) < 2:
                try:
                    path = os.getenv(self.log_environment)
                    handlers.append(logging.FileHandler(os.path.join(os.getcwd(), path if path[0] != "\\" and path[0] != "/" else path[1:], f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")))
                except Exception as e:
                    self.log_queue.put(LogMessage("Logger", f"Log Supplied with Uninitialised Environment Variable - {self.log_environment} - defaulting to console output | Error - {e}", Log._ERROR))
            else:
                self.log_queue.put(LogMessage("Logger", "Log Supplied with file handler and environment handler - defaulting to file handler", Log._WARNING))
        logging.basicConfig(
            level=self.log_level,   
            format="%(asctime)s | %(levelname)s - %(message)s",
            handlers=handlers
        )
    
    def log(self, log_item: LogMessage):
        logging.log(log_item.level, log_item.message)
    
    def start(self):
        while not self._process_event.is_set():
            try:
                log_item = self.log_queue.get(block=True, timeout=None)
                self.log(log_item)
            except (InterruptedError, KeyboardInterrupt):
                pass
        while not self.log_queue.empty():
            try:
                log_item = self.log_queue.get(block=True, timeout=None)
                self.log(log_item)
            except (InterruptedError, KeyboardInterrupt):
                pass
        self.log(LogMessage("Logger", "Logger Process Exited", Log._INFO))