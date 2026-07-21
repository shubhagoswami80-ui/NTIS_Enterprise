"""
=========================================================
NTIS Replay Hooks
Version : 1.0
Purpose :
    Hook points for extending the
    Historical Replay Engine.
=========================================================
"""


class ReplayHooks:

    def before_session(self, session):
        pass

    def after_session(self, session):
        pass

    def before_trade(self, trade):
        pass

    def after_trade(self, trade):
        pass

    def before_validation(self, results):
        pass

    def after_validation(self, summary):
        pass

    def before_export(self, dataframe):
        pass

    def after_export(self, output_file):
        pass

    def on_error(self, exception):
        pass