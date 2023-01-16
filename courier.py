from dataclasses import dataclass
from multiprocessing import Queue, Event
import logging
import os


@dataclass
class Message:
    sender: str
    receiver: str
    subject: str
    message: any
    bulkindex: int = 0
    bulksender: str = None


@dataclass
class LogMessage:
    sender: str
    message: str
    level: int


class Courier:
    _CRITICAL = logging.CRITICAL
    _ERROR = logging.ERROR
    _WARNING = logging.WARNING
    _INFO = logging.INFO
    _DEBUG = logging.DEBUG

    _DEFAULT_TIMEOUT = 0.1
    _BULK_SEPERATOR = "-BULK|"

    def __init__(self, identifier: str,process_event: Event, shutdown_event: Event, logQueue: Queue = None, receiveQueue: Queue = None):
        self.process_event = process_event
        self.shutdown_event = shutdown_event

        self._identifier = identifier
        if receiveQueue is None:
            self.receiveQueue = Queue()
        else:
            self.receiveQueue = receiveQueue
        self.logQueue = logQueue
        self.sendQueues = {}
        self._bulk_receiving = {}
        self._process_received = False
    
    def _check_received(self, msg: Message):
        if msg.subject == "process" and msg.sender == "Core":
            if self._process_received:
                self.receiveQueue.put(msg)
                return None
            else:
                self._process_received = True
            return msg
        response = msg
        if msg is not None and self._BULK_SEPERATOR in msg.subject and msg.bulkindex != 0 and msg.bulksender == self._identifier:
            subject, index = msg.subject.split(self._BULK_SEPERATOR)
            if subject not in self._bulk_receiving.keys():
                self._bulk_receiving[subject] = {}
            self._bulk_receiving[subject]["received"][int(index)] = msg.message
            if len(self._bulk_receiving[subject]["received"].keys()) == msg.bulkindex:
                response = Message(self._bulk_receiving[subject]["receiver"], msg.receiver, subject, [self._bulk_receiving[subject]["received"][i] for i in range(msg.bulkindex)])
                del self._bulk_receiving[subject]
            else:
                response = None
        return response

    @property
    def id(self):
        return self._identifier
    
    @property
    def recipients(self):
        return self.sendQueues.keys()
    
    def set_identifier(self, identifier):
        self._identifier = identifier
    
    def send_pid(self):
        self.send("Core", os.getpid(), "PID")
    
    def add_send_queue(self, queueName: str, queue: Queue):
        if queueName not in self.sendQueues.keys():
            self.sendQueues[queueName] = queue
    
    def log(self, level: int, message: str):
        if self.logQueue is not None:
            self.logQueue.put(LogMessage(self._identifier, f"{self._identifier} - {message}", level))
    
    def critical(self, message: str):
        self.log(self._CRITICAL, message)
    
    def error(self, message: str):
        self.log(self._ERROR, message)
    
    def warning(self, message: str):
        self.log(self._WARNING, message)
    
    def info(self, message: str):
        self.log(self._INFO, message)
    
    def debug(self, message: str):
        self.log(self._DEBUG, message)
    
    def send(self, recipient: str, subject: str="", message: any=None, nowait=False, bulkindex=0, bulksender=None):
        self.debug(f"Sending message to {recipient}")
        if recipient in self.sendQueues.keys() or recipient.lower() in self.sendQueues.keys() or recipient.lower() in [id.lower() for id in self.sendQueues.keys()]:
            try:
                if nowait:
                    self.sendQueues[recipient].put_nowait(Message(self._identifier, recipient, subject, message, bulkindex, bulksender))
                else:
                    self.sendQueues[recipient].put(Message(self._identifier, recipient, subject, message, bulkindex,  bulksender))
            except Exception as e:
                self.error(f"{self._identifier} Courier - Unable to Send Message {Message(self._identifier, recipient, subject, message, bulkindex, bulksender)} - {e}")
        else:
            self.error(f"{self._identifier} Courier - Recipient {recipient} not found")
    
    def send_bulk(self, recipient: str, subject: str="", message: list=None, nowait=False):
        self.debug(f"Sending bulk message to {recipient}")
        self._bulk_receiving[subject] = {
            "subject": subject,
            "bulkindex": len(message),
            "receiver": recipient,
            "received": {}
        }
        if recipient in self.sendQueues.keys() or recipient.lower() in self.sendQueues.keys() or recipient.lower() in [id.lower() for id in self.sendQueues.keys()]:
            for i in range(len(message)):
                mp = Message(self._identifier, recipient, f"{subject}{self._BULK_SEPERATOR}{i}", message[i], len(message), self._identifier)
                try:
                    if nowait:
                        self.sendQueues[recipient].put_nowait(mp)
                    else:
                        self.sendQueues[recipient].put(mp)
                except Exception as e:
                    self.error(f"{self._identifier} Courier - Unable to Send Message {mp} - {e}")
        else:
            self.error(f"{self._identifier} Courier - Recipient {recipient} not found")
    
    def receive(self, wait=False, timeout=_DEFAULT_TIMEOUT) -> Message:
        if wait:
            msg = self._check_received(self.receiveQueue.get(block=True, timeout=None))
            if msg is not None: self.debug(f"Received message {msg}")
            return msg
        try:
            msg = self._check_received(self.receiveQueue.get(block=False, timeout=timeout))
            if msg is not None: self.debug(f"Received message {msg}")
            return msg
        except:
            return None
    
    def check_receive(self):
        return not self.receiveQueue.empty()
    
    def check_continue(self):
        return not self.process_event.is_set()
    
    def shutdown(self):
        if not self.shutdown_event.is_set():
            self.shutdown_event.set()
            self.info("Shutdown Occured")

