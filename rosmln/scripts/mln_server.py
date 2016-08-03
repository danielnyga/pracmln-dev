#!/usr/bin/env python

from rosmln.srv import *
from rosmln.msg import *
import rospy
import traceback
import os

from pracmln.mln.base import MLN
from pracmln.mln.database import parse_db, Database
from pracmln.mln.methods import InferenceMethods


class MLNInterfaceServer:
    '''
    This class represents the ROS node.
    '''
    def __init__(self):
        self.__config = None
        self.__mln = None
        self.__mln_date = None

    def run(self, node_name="rosmln", service_name="mln_interface"):
        '''
        This method starts the server.
        It keeps an infinite loop while waiting
        for clients to ask for the service. 

        :param node_name: The name of the ROS node to instantiate
        :param service_name: The name of the MLN query service to advertise
        '''
        rospy.init_node(node_name)
        rospy.Service(service_name, MLNInterface, self.__handle_mln_query)
        rospy.loginfo("MLN is ready to be queried!")
        rospy.spin()

    def __handle_mln_query(self, request):
        '''
        Handles the query from the client. It expects
        `request` to have two fields, `request.query` and an optional
        `request.config`. `request.query` should be of type :class`MLNQuery` while
        `request.config` should be of type :class:`MLNConfig`.

        :return: a list of :class:`AtomProbPair` objects. Each element of the 
        list is an atom with it's corresponding degree of truth.
        '''
        try:
            rospy.loginfo("Processing request...")
            config = self.__get_config(request)
            if self.__config_changed(config):
                rospy.loginfo("Configuration changed")
                self.__mln = MLN(config.logic, config.grammar, config.mlnFiles)
                self.__mln_date = os.path.getmtime(os.path.expandvars(config.mlnFiles))
                self.__config = config
            db = self.__get_db(request, config, self.__mln)
            materialized_mln = self.__mln.materialize(db)
            mrf = materialized_mln.ground(db)
            if not request.query:
                raise Exception("No query provided!")
            inference = InferenceMethods.clazz(config.method)(mrf, request.query.queries)
            result = inference.run()
            self.__save_results(config, result)
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

    def __config_changed(self, config):
        '''
        Checks whether the given `config` is the same as the configuration
        used in the previous query.
        '''
        if self.__config is None or config is None:
            return True
        return  not (self.__config.db == config.db and \
                     self.__config.logic == config.logic and \
                     self.__config.mlnFiles == config.mlnFiles and \
                     self.__config.output_filename == config.output_filename and \
                     self.__config.saveResults == config.saveResults and \
                     self.__config.grammar == config.grammar and \
                     os.path.getmtime(os.path.expandvars(config.mlnFiles)) == self.__mln_date)

    def __get_config(self, request):
        '''
        Checks whether a configuration is contained in the `request`.
        If so, it is returned.
        If not, the config used during the previous query is returned.
        If there was no previous query, an exception is raised.
        '''
        if self.__config is None and request.config.mlnFiles == "":
            raise Exception("No configuration provided!")
        elif request.config.mlnFiles != "":
            return request.config
        elif self.__config is not None:
            return self.__config

    def __get_db(self, request, config, mln):
        '''
        Returns the evidence database for the query.
        If none is given in the `config` and none is given in the `request`, 
        or both, the `config` and the `request` contain evidence, an
        exception exception is raised.
        '''
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
        '''
        Saves the inference results in `results` to a file specified 
        by `config`.
        '''
        if config.saveResults:
            with open(config.output_filename, "w") as output:
                resutls.write(output)


if __name__ == "__main__":
    MLNInterfaceServer().run()
