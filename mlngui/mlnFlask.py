from webmln.app import SessionStore

class MLNFlask(object):
    '''
    The MLN Flask app.
    '''    

    def __init__(self):
        print 'creating MLNFlask object'
        self.app = None
        self.session_store = SessionStore()
