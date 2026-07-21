class ReplayMetricsCollector:
    def __init__(self): self.metrics={}
    def add(self,name,value): self.metrics[name]=value
