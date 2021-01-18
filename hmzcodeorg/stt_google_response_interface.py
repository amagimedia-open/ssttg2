

class ResponeInterface ():
    def __init__ (self):
        self.stability      = 0.0
        self.is_final       = False
        self.transcript     = ""
        self.pts_seconds    = 0
        self.pts_nanos      = 0


def google_response_to_amg (gresult, amg_result):
    amg_result.stability      = gresult.stability
    amg_result.is_final       = gresult.is_final
    amg_result.transcript     = gresult.alternatives[0].transcript
    amg_result.pts_seconds    = gresult.result_end_time.seconds
    amg_result.pts_nanos      = gresult.result_end_time.microseconds/1000
