from datetime import timedelta
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response, current_app, send_from_directory
from functools import update_wrapper
import os
import json
import configMLN as config
from mln.methods import InferenceMethods

DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)

#data
alchemy_engines = config.alchemy_versions.keys()
alchemy_engines.sort()
inference_methods = InferenceMethods.getNames()
'''
def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator
'''
@app.route('/')
def show_entries():
    return render_template('index.html', **locals())

#@app.route('/resource/qx/decoration/Modern/<path:filename>')
#def send_resource(filename):
#	return send_from_directory('/static/resource/qx/decoration/Modern/', filename);
@app.route('/_mln', methods=['GET', 'OPTIONS'])
def fetch_mln():
		filename = request.args.get('filename')
		directory = '.'
		if os.path.exists(os.path.join(directory, filename)):
		    text = file(os.path.join(directory, filename)).read()
		    if text.strip() == "":
		        text = "// %s is empty\n" % filename;
		else:
		    text = filename
		return text

@app.route('/_options', methods=['GET', 'OPTIONS'])
def options():
    return ';'.join(((','.join(alchemy_engines)),(','.join(inference_methods))))

if __name__ == '__main__':
    app.run(debug=True)
