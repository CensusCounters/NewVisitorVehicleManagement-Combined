# import the necessary packages
from json_minify import json_minify
import json
from string import Template

class Conf:
	def __init__(self, confPath):
		# load and store the configuration and update the object's
		# dictionary
		config_content=open(confPath).read()
		config_template = Template(json_minify(config_content))
		mid_json = json.loads(json_minify(config_content))
		config = config_template.safe_substitute(mid_json["cameras"][0]["Details"])
		conf = json.loads(config)
		self.__dict__.update(conf)

	def __getitem__(self, k):
		# return the value associated with the supplied key
		return self.__dict__.get(k, None)
