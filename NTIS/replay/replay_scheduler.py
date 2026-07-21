"""
=========================================================
NTIS Replay Scheduler
Version : 1.0
Purpose :
    Schedule and execute Replay jobs.
=========================================================
"""

from datetime import datetime


class ReplayScheduler:

    def __init__(self):

        self.jobs = []

    def add_job(
        self,
        name,
        replay_function,
        *args,
        **kwargs,
    ):

        self.jobs.append(
            {
                "name": name,
                "function": replay_function,
                "args": args,
                "kwargs": kwargs,
            }
        )

    def run_all(self):

        results = []

        for job in self.jobs:

            start = datetime.now()

            output = job["function"](
                *job["args"],
                **job["kwargs"],
            )

            end = datetime.now()

            results.append(
                {
                    "Job": job["name"],
                    "Start": start,
                    "End": end,
                    "Duration": end - start,
                    "Result": output,
                }
            )

        return results

    def clear(self):

        self.jobs.clear()