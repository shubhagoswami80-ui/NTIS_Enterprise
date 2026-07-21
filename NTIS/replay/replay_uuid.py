from uuid import uuid4

class ReplayUUID:
    @staticmethod
    def new():
        return str(uuid4())
