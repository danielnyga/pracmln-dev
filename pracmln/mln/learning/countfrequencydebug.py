from pracmln.mln.learning.countfrequency import CountFrequency
from pracmln.mln.learning.ll import LL
from numpy import exp

class CountFrequencyDebug(CountFrequency):
    def __init__(self, mln, databases):
        CountFrequency.__init__(self, mln, databases)

    def run(self, **unused_kwargs):
        weights = CountFrequency.run(self, **unused_kwargs)
        for db_index, db in enumerate(self.databases):
            mrf = self.mln.ground(db)
            learner = LL(mrf)
            learner._prepare()
            print "P for database " + str(db_index) + ": " + str(learner._l(weights)[learner._eworld_idx])
        return weights