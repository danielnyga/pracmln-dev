from multiprocessing import Process, Queue
from pracmln.praclog import logger
import threading

log = logger(__name__)

class RequestBuffer(object):

    def __init__(self):
        self._condition = threading.Condition()
        self._content = {'status': False, 'message': ''}
        self._dirty = False


    def waitformsg(self, timeout=None):
        with self.condition:
            if self._dirty:
                return
            self.condition.wait(timeout=timeout)


    def setmsg(self, cnt):
        with self.condition:
            self.content.update(cnt)
            self._dirty = True
            self.condition.notifyAll()


    @property
    def condition(self):
        return self._condition


    @property
    def content(self):
        self._dirty = False
        return self._content


class RunProcess(threading.Thread):
    """
    Run calling: success, result = RunProcess(func, timeout).Run()
    """
    def __init__(self, func, timeout):
        threading.Thread.__init__(self)
        self.func = func
        self.timeout = timeout
        self.result = None


    def worker(self, q):
        result = self.func()
        q.put(result)


    def run(self):
        self.queue = Queue()
        self.p = Process(target=self.worker, args=(self.queue,))
        self.p.start()
        self.p.join()


    def Run(self):
        self.start()
        self.join(self.timeout)

        if self.is_alive():
            self.p.terminate()      # or self.p.kill()
            self.join()
            return None
        return self.queue.get()
