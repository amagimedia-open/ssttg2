import syslog
import sys
import datetime

import stt_globals

LOG_DEBUG = syslog.LOG_DEBUG 
LOG_INFO = syslog.LOG_INFO 
LOG_WARNING = syslog.LOG_WARNING
LOG_ERR = syslog.LOG_ERR 

#facility
LOG_USER = syslog.LOG_USER
LOG_LOCAL0 = syslog.LOG_LOCAL0
LOG_LOCAL1 = syslog.LOG_LOCAL1

class amagi_logger:

    def __init__(self, 
                 module="com.amagimedia-open.ssttg2", 
                 log_level=LOG_INFO, 
                 facility=LOG_USER, 
                 log_stream="syslog"):

        self.__module = module
        self.__log_level = log_level
        self.__facility = facility
        self.__log_stream = log_stream

        self.__log2stderr = False
        if self.__log_stream == "stderr":
            self.__log2stderr = True
        else:
            #https://docs.python.org/3/library/syslog.html
            syslog.openlog(ident='', logoption=syslog.LOG_PID, facility=self.__facility)

        self.__level_strings = {
                syslog.LOG_INFO    : 'INFO',
                syslog.LOG_DEBUG   : 'DEBUG',
                syslog.LOG_WARNING : 'WARN',
                syslog.LOG_ERR     : 'ERROR'
            }

    def info(self, log_message):
        if syslog.LOG_INFO <= self.__log_level:
            self.log(syslog.LOG_INFO, log_message)

    def debug(self, log_message):
        if syslog.LOG_DEBUG <= self.__log_level:
            self.log(syslog.LOG_DEBUG, log_message)

    def warn(self, log_message):
        if syslog.LOG_WARNING <= self.__log_level:
            self.log(syslog.LOG_WARNING, log_message)

    def error(self, log_message):
        if syslog.LOG_ERR <= self.__log_level:
            self.log(syslog.LOG_ERR, log_message)

    def log(self, priority, log_message):

        p_string = self.__level_strings[priority]

        log_message = log_message.replace('\x00','')
        module_log_message = '%s, %s, %s'%(p_string, self.__module, str(log_message))

        if self.__log2stderr:
            stt_globals.eprint (module_log_message)
        else:
            syslog.syslog(priority, module_log_message)


if __name__ == '__main__':
    logger = amagi_logger(module="com.amagi.stt.logger.test", log_level=LOG_DEBUG)
    logger.debug("this is a debug msg")
    logger.info("this is an info msg")
    logger.warn("this is a warn msg")
    logger.error("this is an error msg")
