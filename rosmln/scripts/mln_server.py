#!/usr/bin/env python

from rosmln.srv import *
from rosmln.msg import *
import rospy
import traceback

from pracmln.mln.base import MLN
from pracmln.mln.database import parse_db, Database
from pracmln.mln.methods import InferenceMethods


class MLNInterfaceServer:
    def __init__(self):
        self.__config = None
        self.__mln = None

    def run(self, node_name="rosmln", service_name="mln_interface"):
        rospy.init_node(node_name)
        rospy.Service(service_name, MLNInterface, self.__handle_mln_query)
        rospy.loginfo("MLN is ready to be queried!")
        rospy.spin()

    def __handle_mln_query(self, request):
        try:
            rospy.loginfo("Processing request...")
            config = self.__get_config(request)
            if not self.__config_equals(self.__config, config):
                self.__mln = MLN(config.logic, config.grammar, config.mlnFiles)
            db = self.__get_db(request, config, self.__mln)
            materialized_mln = self.__mln.materialize(db)
            mrf = materialized_mln.ground(db)
            if not request.query:
                raise Exception("No query provided!")
            inference = InferenceMethods.clazz(config.method)(mrf, request.query.queries)
            result = inference.run()
            self.__save_results(config, result)
            self.__config = config
            tuple_list = []
            for atom, probability in inference.results.items():
                tuple_list.append(AtomProbPair(str(atom), float(probability)))
            tuple_list.sort(key=lambda item: item.prob, reverse=True)
            to_return = MLNInterfaceResponse(MLNDatabase(tuple_list))
            rospy.loginfo("Done!")
            return to_return
        except Exception:
            rospy.logfatal(traceback.format_exc())
            return MLNDatabase([])

    def __config_equals(self, config1, config2):
        if config1 is None or config2 is None:
            return False
        return  config1.db == config2.db and \
                config1.logic == config2.logic and \
                config1.mlnFiles == config2.mlnFiles and \
                config1.output_filename == config2.output_filename and \
                config1.saveResults == config2.saveResults and \
                config1.grammar == config2.grammar

    def __get_config(self, request):
        if self.__config is None and request.config.mlnFiles == "":
            raise Exception("No configuration provided!")
        elif request.config.mlnFiles != "":
            return request.config
        elif self.__config is not None:
            return self.__config

    def __get_db(self, request, config, mln):
        if not request.query.evidence and config.db == "":
            raise Exception("No evidence provided!")
        if request.query.evidence and config.db != "":
            raise Exception("Duplicate evidence; provide either a db in the config or an evidence db in the query")
        if request.query.evidence:
            to_return = parse_db(mln, reduce(lambda x, y: x + "\n" + y, request.query.evidence))
        else:
            to_return = Database.load(mln, config.db)
        if len(to_return) != 1:
            raise Exception("Only one db is supported!")
        return to_return[0]

    def __save_results(self, config, resutls):
        if config.saveResults:
            with open(config.output_filename, "w") as output:
                resutls.write(output)


if __name__ == "__main__":
    MLNInterfaceServer().run()
