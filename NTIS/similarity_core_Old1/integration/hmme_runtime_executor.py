class HMMERuntimeExecutor:
    def __init__(self, gateway):
        self.gateway = gateway

    def execute(self):
        return {
            'status': 'EXECUTED',
            'gateway': self.gateway.connect_all()
        }
