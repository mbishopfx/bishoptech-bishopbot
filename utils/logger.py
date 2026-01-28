import os
import datetime
import uuid

def get_new_id():
    return str(uuid.uuid4())

def log_verbose(log_id, interpreted_code, output):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"Timestamp: {timestamp}\nLog ID: {log_id}\n\nInterpreted Code:\n{interpreted_code}\n\nOutput:\n{output}\n"
    
    log_file = os.path.join("logs", f"{log_id}.log")
    with open(log_file, "w") as f:
        f.write(log_content)
    return log_file

def log_error(log_id, error_message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"Timestamp: {timestamp}\nLog ID: {log_id}\n\nError:\n{error_message}\n"
    
    log_file = os.path.join("logs", f"{log_id}.log")
    with open(log_file, "w") as f:
        f.write(log_content)
    return log_file
