# Core - Python Multiprocessing Wrapper

Python multiprocessing wrapper constructed to simplify the use of multiprocessing and communication between the processes as well as logging throughout all processes.

## Usage

Download Github files and copy `core` folder to python program directory. 

### Importing 
Import core into python file which launches program

```
import core
```

### Initializing & Environment Setup
Initialize the Core object supplying with the following optional keyword arguments
- log_level (optional) - The logging level wanting to be captured and outputted, these are taken from e.g. logging.DEBUG
- log_folder (optional) - The absolute path to the folder where log files should be stored
- log_environment (optional) - An envrionment variable name (str) which stores the log folder path 
- environment_json (optional) - The absolute path to a JSON file contianing the environment variables; to be loaded into the environment which the program is being run from. NOTE - all variables will be placed into environment as strings regardless of original format

NOTE - For inputted log_environment if there is no available environment variable with the path, the program will default to not saving the logs in a file

```
multicore = Core(environment_json="/path/to/environment.json", log_environemnt="LOG_FILEPATH")
```

### Adding Processes & Running
New Process Functions can be added using the `create_process` function in `Core` with the following arguments
- process_id (required) - [String] Process identifier, used for sending and receiving messages between the proesses
- process_function (required) - Function or Class to be run in the new process created
- process_args (optional) - [List] Arguments to be supplied to the process
- process_kwargs (optional) - [Dictionary] Keyword arguments to be supplied to the process
- force_terminate (optional) - [Boolean] Indicator that the process will not shutdown by itself and must be force terminated before it will close

A courier object will be passed to the process as the first argument in each case

Once all processes are added run `Core.start()` to start all processes

```
class ExampleClass:
    def __init__(self, courier, *args, **kwargs):
        self._courier = courier
    
    def run(self):
        while self._courier.check_continue():
            message = self._courier.receive()
            if message is not None:
                #process message
            #do something else

function exampleFunction(courier, *args, **kwargs):
    #do something
    while True:
        pass

multicore.create_process("exampleclass", ExampleClass, process_args=[1,2,3], process_kwargs={'arg':1})
multicore.create_process("examplefunction", exampleFunction, force_terminate=True)

multicore.start()
```

### Courier - Interprocess Messaging
The courier class acts as a interprocess message manager, allowing for messages to be sent between processes, logging between the processes and shutting down of all processes. This object is fed into each process already initialized with ability to send and receive from all other processes.

#### Messages:
Messages are sent and received as a dataclass between processes, each message with:
- sender
- receiver
- subject
- message

```
message = courier.receive()
if message is not None:
    if message.subject == "subject" and message.sender == "exampleclass":
        message = message.message
```

### Courier Class Functions:
#### critical | error | warning | info | debug
Logging function to write logs to the expected file/terminal output

Arguments:
- message (required) - [str] Message to be logged

Usage:
```
courier.critical("Message")
```

#### send
Send functionality to send a message to another process 

Arguments:
- recipient (required) - [str] Process ID for the message to be sent to 
- subject (optional) - [str] Subject of the message
- message (optional) - [any] Message/Data to be sent

Usage:
```
courier.send("exampleClass", subject="subject", message={"something": 1})
```

#### check_continue
Check if the main program is being shutdown, True if continuing, False if shutting down

Usage:
```
while courier.check_continue():
    #continue
courier.shutdown()
```


#### shutdown
Signal to the process controller that this process has shutdown successfully 

NOTE - if process is flagged to be force terminated this is not necessary as it will be forcefully stopped once all other processes have signalled successful shutdown

Usage:
```
while courier.check_continue():
    #continue
courier.shutdown()
```

### Process Shutdown
The processes will be shutdown whenever either a shutdown flag is received from any one of the processes, or if an exception occurs on one of the processes


## Work in Progress
This module is a work in progress and is continuously growing. No-one will probably use this but if you have any ideas for updates please let me know. 