import sys
from datetime import datetime, timedelta

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

def now_2_epochms():
    #https://stackoverflow.com/questions/27245488/converting-iso-8601-date-time-to-seconds-in-python
    #eg: 1984-06-02T19:05:00.000Z
    utc_dt = datetime.utcnow()
    timestamp = (utc_dt - datetime(1970, 1, 1)).total_seconds()
    return int (timestamp * 1000)

