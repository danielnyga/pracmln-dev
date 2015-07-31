from webmln.mlninit import mlnApp
from flask import redirect

@mlnApp.app.route('/')
def start():
    return redirect('/mln/')

@mlnApp.app.route('/log/<filename>')
def log(filename):
    return redirect('/mln/log/{}'.format(filename))