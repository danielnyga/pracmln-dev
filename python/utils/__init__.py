import logging

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