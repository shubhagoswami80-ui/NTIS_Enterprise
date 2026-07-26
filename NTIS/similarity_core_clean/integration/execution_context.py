from datetime import datetime
import uuid

class ExecutionContext:
    def __init__(self):
        self.execution_id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.status = 'INITIALIZED'
        self.metadata = {}
