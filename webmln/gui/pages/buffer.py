import threading
from pracmln.praclog import logger


log = logger(__name__)

class RequestBuffer(object):

    def __init__(self):
        self._condition = threading.Condition()
        self._content = {'status': False, 'message': ''}


    def waitformsg(self, timeout=None):
        with self.condition:
            self.condition.wait(timeout=timeout)


    def setmsg(self, cnt):
        with self.condition:
            self.content.update(cnt)
            self.condition.notifyAll()


    @property
    def condition(self):
        return self._condition


    @property
    def content(self):
        return self._content
