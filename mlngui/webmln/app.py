from flask import Flask


class MLNSession():

    def __init__(self, http_session):
        self.id = http_session['id']
        self.http_session = http_session

class SessionStore():

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
