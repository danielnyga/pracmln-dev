from flask import redirect
from webmln.gui.app import mlnApp


@mlnApp.app.route('/')
def start():
    return redirect('/mln/')


@mlnApp.app.route('/log/<filename>')
def log(filename):
    return redirect('/mln/log/{}'.format(filename))
