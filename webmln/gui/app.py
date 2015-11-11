from flask import Flask

class MLNFlask(object):
    '''
    The MLN Flask app.
    '''

    def __init__(self):
        print 'creating MLNFlask object'
        self.app = None
        self.session_store = SessionStore()

class MLNSession():
    '''
    The MLN Session.
    '''
    def __init__(self, http_session):
        self.id = http_session['id']
        self.http_session = http_session

class SessionStore():
    '''
    The MLN SessionStore.
    '''
    def __init__(self):
        self.sessions = {}

    def put(self, mln_session):
        self.sessions[mln_session.id] = mln_session

    def __getitem__(self, s):
        if 'id' not in s: return None
        return self.sessions.get(s['id'])

    def remove(self, s):
        del self.sessions[s['id']]

    def __str__(self):
        return str(self.sessions)

app = Flask(__name__)
mlnApp = MLNFlask()
