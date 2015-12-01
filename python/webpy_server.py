import web
import json
import os
import configMLN as config
from mln.methods import InferenceMethods

render = web.template.render('templates/')
alchemy_engines = config.alchemy_versions.keys()
alchemy_engines.sort()
inference_methods = InferenceMethods.getNames()

urls = (
	'/', 'index',
	'/options', 'return_options',
	'/run', 'run',
	'/mln', 'fetch_mln'
)

class index:
	def GET(self):
		return render.index()
class fetch_mln:
	def GET(self):
		web.header('Content-Type', 'text/plain')

		directory = '.'
		filename = 'wts.pybpll.smoking-train-smoking.mln'
		if os.path.exists(os.path.join(directory, filename)):
		    text = file(os.path.join(directory, filename)).read()
		    if text.strip() == "":
		        text = "// %s is empty\n" % filename;
		else:
		    text = ""
		return text

class return_options:
	def GET(self):
		web.header('Content-Type', 'text/plain')
		
        	return ';'.join(((','.join(alchemy_engines)),(','.join(inference_methods))))

class run:
	def POST(self):
		web.header('Content-Type', 'text/plain')
		data = web.input()
		web.debug(data)
		return data

if __name__ == "__main__":
	app = web.application(urls, globals())
	app.run()
	
