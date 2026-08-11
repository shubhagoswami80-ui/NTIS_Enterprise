
from datetime import datetime
import os

_processing_date = None


def set_processing_date(value):

    global _processing_date

    _processing_date = datetime.strptime(
        value,
        "%Y-%m-%d"
    )


def get_processing_date():

    if _processing_date:
        return _processing_date

    env_date = os.environ.get(
        "NTIS_PROCESSING_DATE"
    )

    if env_date:
        return datetime.strptime(
            env_date,
            "%Y-%m-%d"
        )

    return datetime.today()
