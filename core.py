import multiprocessing
import logging
import json
import os
import signal
from dotenv import load_dotenv

from .log import Log, LogMessage
from .courier import Courier


def _process_wrapper(process_id, _courier, *args, **kwargs):
    waitingProcess = True
    while waitingProcess:
        received = _courier.receive(wait=True)
        if received.subject != 'process':
            _courier.receiveQueue.put(received)
        else:
            waitingProcess = False
    process_function = received.message
    _courier.info(f"Starting Process - {process_id}")
    try:
        process_function(_courier, *args, **kwargs)
    except Exception as e:
        _courier.error(f"Process {process_id} failed with error: {e}")
        _courier.shutdown()


class Core:
    def __init__(self, log_level=logging.INFO, log_folder=None, log_file=None, log_environment=None, environment_file=None):
        self.log_level = log_level
        self.log_folder = log_folder
        self.log_file = log_file
        self.log_environment = log_environment
        self.environment_file = environment_file
        self._log_process_event = multiprocessing.Event()            

        self._process_event = multiprocessing.Event()
        self._processes = {}
        self._process_count = 0

        signal.signal(signal.SIGINT, self._cancel_handler)

        self._setup_environment()

        self._courier = Courier("Core", self._process_event, multiprocessing.Event())
        self._log = Log(self._log_process_event, self.log_level, self.log_folder, self.log_file, self.log_environment)
        self._watcher_process = multiprocessing.Process(target=self.watcher)

        if self.log_environment is not None and self.environment_file is None:
            self._courier.log(logging.WARNING, "Environment File not Given - Use of Environment Will be Attempted")
        
    def _cancel_handler(self, signum, frame):
        self._process_event.set()
        self._log.log_queue.put(LogMessage("Core", f"Interrupt Received", Log._INFO))
    
    def _setup_environment(self):
        if self.environment_file is not None:
            if ".json" in self.environment_file:
                with open(self.environment_file, "r") as ej:
                    ejd = json.load(ej)
                    for key, value in ejd.items():
                        os.environ[str(key)] = str(value)
            elif ".env" in self.enviornment_file:
                load_dotenv(self.environment_file)
            else:
                self._courier.log(logging.ERROR, "Environment File Supplied Unknown Format - Environment File can either be .env or .json")
        
    def create_process(self, process_id, process_function, process_args=None, process_kwargs=None, force_terminate=False, worker_count=1):
        if process_args is None:
            process_args = []
        if process_kwargs is None:
            process_kwargs = {}
        receive_queue = None
        for i in range(worker_count):
            self._process_count += 1
            shutdown = multiprocessing.Event()
            courier = Courier(process_id, self._process_event, shutdown, self._log.log_queue, receive_queue)
            if receive_queue is None:
                receive_queue = courier.receiveQueue
                self.update_couriers(process_id, courier.receiveQueue)
            courier.add_send_queue(self._courier.id, self._courier.receiveQueue)
            for processData in self._processes.values():
                courier.add_send_queue(processData["receiver_id"], processData["courier"].receiveQueue)
            nprocess_id = process_id
            if worker_count > 1:
                nprocess_id = f"{process_id}_{i}"
                courier.set_identifier(nprocess_id)
            process_args.insert(0, courier)
            process_args.insert(0, nprocess_id)
            process = multiprocessing.Process(target=_process_wrapper, args=process_args, kwargs=process_kwargs)
            self._processes[nprocess_id] = {
                "process": process,
                "shutdown": shutdown,
                "courier": courier,
                "pid": None,
                "isShutdown": False,
                "forceTerminate": force_terminate,
                'function': process_function,
                'bulk': False if worker_count == 1 else True,
                'receiver_id': process_id
            }

    def update_couriers(self, newCourierId: str, newCourierQueue: multiprocessing.Queue):
        for processData in self._processes.values():
            processData["courier"].add_send_queue(newCourierId, newCourierQueue)
        self._courier.add_send_queue(newCourierId, newCourierQueue)
    
    def _check_shutdowns(self, terminate=False):
        for id, processData in self._processes.items():
            if not processData["isShutdown"] and processData["shutdown"].is_set():
                self._log.log_queue.put(LogMessage(id, f"Shutdown Received - {processData['courier'].id}", Log._INFO))
                self._process_event.set()
                self._process_count -= 1
                processData["isShutdown"] = True
            elif not processData["isShutdown"] and terminate and processData["forceTerminate"]:
                self._log.log_queue.put(LogMessage(id, f"Forcing Shutdown - {processData['courier'].id}", Log._INFO))
                self._process_event.set()
                self._process_count -= 1
                processData["isShutdown"] = True
                processData["process"].terminate()
    
    def send(self, receiver: str, subject:str, message=None):
        self._courier.send(receiver, subject, message)
    
    def watcher(self):
        while not self._process_event.is_set():
            try:
                self._check_shutdowns()
                message = self._courier.receive()
                if message is not None:
                    if message.subject == "PID":
                        self._processes[message.sender]["pid"] = message.message
            except (InterruptedError, KeyboardInterrupt):
                pass
        self._log.log_queue.put(LogMessage("Core", "Watcher Shutdown Complete", Log._INFO))
        force_shutdowns = [i["courier"].id for i in self._processes.values() if i["forceTerminate"]]
        if len(force_shutdowns) > 0:
            self._log.log_queue.put(LogMessage("Core", f"{force_shutdowns} Process Required to be Force Terminated - Shutting down Quietly", Log._INFO))
        self._log_process_event.set()
    
    def start(self):
        self._watcher_process.start()
        for processData in self._processes.values():
            processData["process"].start()
            self.send(processData["receiver_id"], subject='process', message=processData['function'])
        self._log.start() # Blocking Function, Exits on Shutdown Event
        while self._process_count != 0:
            try:
                self._check_shutdowns(True)
            except (InterruptedError, KeyboardInterrupt):
                pass

        