import logging
from praclog.logformat import RainbowLoggingHandler
import sys
import time


# this defines the formats in (bg, fg, bold)
weight_color = (None, 'magenta', False)
comment_color = (None, 'green', False)
predicate_color = (None, 'white', True)

def colorize(message, format, color=False):
    '''
    Returns the given message in a colorized format
    string with ANSI escape codes for colorized console outputs:
    - message:   the message to be formatted.
    - format:    triple containing format information:
                 (bg-color, fg-color, bf-boolean) supported colors are
                 'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'
    - color:     boolean determining whether or not the colorization
                 is to be actually performed.
    '''
    colorize.colorHandler = RainbowLoggingHandler(sys.stdout)
    if color is False: return message
    params = []
    (bg, fg, bold) = format
    if bg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[bg] + 40))
    if fg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[fg] + 30))
    if bold:
        params.append('1')
    if params:
        message = ''.join((colorize.colorHandler.csi, ';'.join(params),
                           'm', message, colorize.colorHandler.reset))
    return message


class StopWatchTag:
    
    def __init__(self, label, starttime, stoptime=None):
        self.label = label
        self.starttime = starttime
        self.stoptime = stoptime

class StopWatch(object):
    '''
    Simple tagging of time spans.
    '''
    
    def __init__(self):
        self.start = 0
        self.tags = []
        
    def tag(self, label, verbose=True):
        if verbose:
            print '%s...' % label
        now = time.time()
        self.start = now
        if len(self.tags) > 0 and self.tags[-1].stoptime is None:
                self.tags[-1].stoptime = now
        self.tags.append(StopWatchTag(label, now))
    
    def finish(self):
        now = time.time()
        if len(self.tags) > 0 and self.tags[-1].stoptime is None:
            self.tags[-1].stoptime = now
    
    def reset(self):
        self.tags = []
        self.start = 0
        
    def printSteps(self):
        for t in self.tags:
            self.finish()
            print '%s took %.3f sec.' % (colorize(t.label, (None, None, True), True), t.stoptime-t.starttime)


def combinations(domains):
    if len(domains) == 0:
        raise Exception('domains mustn\'t be empty')
    return _combinations(domains, [])

def _combinations(domains, comb):
    if len(domains) == 0:
        yield comb
        return
    for v in domains[0]:
        for ret in _combinations(domains[1:], comb + [v]):
            yield ret
            
def deprecated(func):
    '''
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used.
    '''
    def newFunc(*args, **kwargs):
        logging.getLogger().warning("Call to deprecated function: %s." % func.__name__)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc
            
def unifyDicts(d1, d2):
    '''
    Adds all key-value pairs from d2 to d1.
    '''
    for key in d2:
        d1[key] = d2[key]
        
def dict_union(d1, d2):
    '''
    Returns a new dict containing all items from d1 and d2. Entries in d1 are
    overridden by the respective items in d2.
    '''
    d_new = {}
    for key, value in d1.iteritems():
        d_new[key] = value
    for key, value in d2.iteritems():
        d_new[key] = value
    return d_new
    
    
if __name__ == '__main__':
    
    for c in combinations([]):
        print c