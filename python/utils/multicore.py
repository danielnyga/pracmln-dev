import traceback
from multiprocessing import Pool
import multiprocessing.pool

import sys

class with_tracing(object):
    '''
    Wrapper class for functions intended to be executed in parallel
    on multiple cores. This facilitates debugging with multiprocessing.
    '''
    
    def __init__(self, func):
        self.func = func
        
    def __call__(self, *args, **kwargs):
        try:
            result = self.func(*args,**kwargs)
            return result
        except Exception, e:
            tb = traceback.format_exc()
            sys.stderr.write(tb)
            raise e
        

# created because only non-Daemon Processes can have children
class NDProcess(multiprocessing.Process):
    
    def _get_daemon(self):
        return False # daemon attribute false to create non-daemon process
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# multiprocessing.Pool only wrapper fct -> use multiprocessing.pool.Pool
class NDPool(multiprocessing.pool.Pool):
    Process = NDProcess


# exmaple how to be used
if __name__ == '__main__':
    def f(x):
        return x*x
    pool = Pool(processes=4)              # start 4 worker processes
    print pool.map(with_tracing(f), range(10))          # prints "[0, 1, 4,..., 81]"
    
    
   
            
