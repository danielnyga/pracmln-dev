import traceback
from multiprocessing import Pool
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
        


# exmaple how to be used
if __name__ == '__main__':
    def f(x):
        return x*x
    pool = Pool(processes=4)              # start 4 worker processes
    print pool.map(with_tracing(f), range(10))          # prints "[0, 1, 4,..., 81]"
    
    
   
            
