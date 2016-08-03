#!/usr/bin/env python
import sys

import rospy
from rosmln.srv import *
from rosmln.msg import *


def mln_interface_client(query, config=None):
    '''
    This is an example of the client quering the service.
    The important thing to note is that you have the option
    to set the configuration parameters only once and use the
    the same settings in further calls.

    :param query: The query to execute as string
    :param config: The configuration to use
    '''
    rospy.wait_for_service('mln_interface')
    try:
        mln_interface = rospy.ServiceProxy('mln_interface', MLNInterface)
        resp1 = mln_interface(query, config)
        return resp1.response
    except rospy.ServiceException, e:
        print("Service call failed: %s"%e)


def print_results(results):
    '''
    This function prints the results from the :attr:`mln_interface_client`
    to the command line, or an error message if the query was unsuceessul.
    '''
    if not results.evidence:
        print("ERROR: Something went wrong...")
    else:
        print results


if __name__ == "__main__":
    mlnFiles = "$PRACMLN_HOME/test/models/smokers/wts.pybpll.smoking-train-smoking.mln"
    db = "$PRACMLN_HOME/test/models/smokers/smoking-test-smaller.db"
    queries = "Smokes"
    output_filename = "results.txt"
    query = MLNQuery(queries, None)
    config = MLNConfig(mlnFiles, db, "GibbsSampler", output_filename, True,  "FirstOrderLogic", "PRACGrammar")
    print_results(mln_interface_client(query, config))

    print("Without config parameters")
    print_results(mln_interface_client(query))

    print("Without evidence")
    config.db=""
    query = MLNQuery(queries, ["Cancer(Ann)", "!Cancer(Bob)", "!Friends(Ann,Bob)"])
    print_results(mln_interface_client(query, config))


