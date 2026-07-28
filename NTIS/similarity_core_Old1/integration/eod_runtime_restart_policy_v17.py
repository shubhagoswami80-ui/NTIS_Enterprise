
class EODRuntimeRestartPolicyV17:
    def policy(self):
        return {"restart_policy": "READY"}
