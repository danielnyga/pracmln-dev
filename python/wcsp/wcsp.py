# Weighted Constraint Satisfaction Problems -- Representation and Solving
#
# (C) 2012 by Daniel Nyga (nyga@cs.tum.edu)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys
import os
from subprocess import Popen, PIPE
import logging
import bisect
import copy

class MaxCostExceeded(Exception): pass

temp_wcsp_file = os.path.join('/', 'tmp', 'temp%d.wcsp')

# Check if the toulbar2 executable can be found. Raise an exception, if not.
def is_executable(path):
    return os.path.exists(path) and os.access(path, os.X_OK)

def isToulbar2Installed():
    toulbar2cmd = 'toulbar2'
    for path in os.environ['PATH'].split(os.pathsep):
        cmd_file = os.path.join(path, toulbar2cmd)
        for candidate in cmd_file:
            if is_executable(candidate):
                return
    logging.getLogger(__name__).exception('toulbar2 executable cannot be found.')

isToulbar2Installed()

class Constraint(object):
    '''
    Represents a a constraint in WCSP problem consisting of
    a range of variables (indices), a set tuples with each
    assigned costs and default costs. Costs are either a real
    valued non-negative weight or the WCSP.TOP constant
    indicating global inconsistency.
    
    - tuples:     dictionary mapping a tuple to int (the costs)
    - defCost:    the default cost of this constraint
    '''
    
    def __init__(self, varIndices, tuples=None, defCost=0):
        '''
        Constructor:
        varIndices:    list of indices that identify the range of this constraint
        tuples         (optional) list of tuples, where the last element of each
                       tuple specifies the costs for this assignment.
        defCost        the default costs (if none of the tuples apply).
        '''
        self.tuples = dict()
        if tuples is not None:
            for t in tuples:
                self.tuples[tuple(t[:-1])] = t[-1]
        self.defCost = defCost
        self.varIndices = varIndices
        
    def addTuple(self, t, cost):
        '''
        Adds a tuple to the constraint. A value in the tuple corresponds to the
        index of the value in the domain of the respective variable.
        '''
        if not len(t) == len(self.varIndices):
            print 'tuple:', t
            print 'vars:', self.varIndices
            assert False
        self.tuples[tuple(t)] = cost
    
    def write(self, stream):
        stream.write('%d %s %d %d\n' % (len(self.varIndices), ' '.join(map(str, \
                            self.varIndices)), self.defCost, len(self.tuples)))
        for t in self.tuples.keys():
            stream.write('%s %d\n' % (' '.join(map(str, t)), self.tuples[t]))
            
    def __eq__(self, other):
        eq = set(self.varIndices) == set(other.varIndices)
        eq = eq and self.defCost == other.defCost
        eq = eq and self.tuples == other.tuples
        return eq


class WCSP(object):
    '''
    Represents a WCSP problem.
    Members:
    self.name        (arbitrary) name of the problem
    self.domainSizes list of domain sizes
    self.top         maximal costs (entirely inconsistent worlds)
    self.constraints list of constraint objects
    '''
    
    # symbol for the globally inconsistent cost
    TOP = -1

    # maximum costs imposed by toulbar
    MAX_COST = 1537228672809129301L
    

    def __init__(self, name=None, domSizes=None, top=None):
        self.name = name
        self.domSizes = domSizes
        self.top = top
        self.constraints = []
    
    def __eq__(self, other):
        eq = self.domSizes == other.domSizes
        eq = eq and self.top == other.top
        (toBeCopied, ref) = (self, other) if len(self.constraints) <= len(other.constraints) else (other, self)
        copy = []
        for c in toBeCopied.constraints:
            copy.append(c)
        for c in ref.constraints:
            if not c in copy: 
                return False
            copy.remove(c)
        eq = eq and len(copy) == 0
        return eq
    
    def addConstraint(self, constraint):
        '''
        Adds the given constraint to the WCSP. If a constraint 
        with the same scope already exists, the tuples of the
        new constraint are merged with the existing ones.
        '''
        const = None
        for c in self.constraints:
            if c.varIndices == constraint.varIndices: 
                const = c
                break
        if const is None:
            self.constraints.append(constraint)
        else:
            for t in constraint.tuples.keys():
                const.addTuple(t, constraint.tuples[t])
        
    def write(self, stream):
        '''
        Writes the WCSP problem in WCSP format into an arbitrary stream
        providing a write method.
        '''
        wcsp = self#.makeIntegerCostWCSP()
        stream.write('%s %d %d %d %f\n' % (wcsp.name, len(wcsp.domSizes), max(wcsp.domSizes), len(wcsp.constraints), wcsp.top))
        stream.write(' '.join(map(str, wcsp.domSizes)) + '\n')
        for c in wcsp.constraints:
            stream.write('%d %s %d %d\n' % (len(c.varIndices), ' '.join(map(str, c.varIndices)), c.defCost, len(c.tuples)))
            for t in c.tuples.keys():
                stream.write('%s %f\n' % (' '.join(map(str, t)), c.tuples[t]))
        
    def read(self, stream):
        '''
        Loads a WCSP problem from an arbitrary stream. Must be in the WCSP format.
        '''
        tuplesToRead = 0
        for i, line in enumerate(stream.readlines()):
            tokens = line.split()
            if i == 0:
                self.name = tokens[0]
                self.top = int(tokens[-1])
            elif i == 1:
                self.domSizes = map(int, tokens)
            else:
                if tuplesToRead == 0:
                    tuplesToRead = int(tokens[-1])
                    varIndices = map(int, tokens[1:-2])
                    defCost = int(tokens[-2])
                    constraint = Constraint(varIndices, defCost=defCost)
                    self.constraints.append(constraint)
                else:
                    constraint.addTuple(map(int,tokens[0:-1]), int(tokens[-1]))
                    tuplesToRead -= 1
                    
    def _computeDivisor(self):
        '''
        Computes a divisor for making all constraint costs integers.
        '''
        # store all costs in a sorted list
        costs = []
        log = logging.getLogger('wcsp')
        minWeight = None
        for constraint in self.constraints:
            for value in [constraint.defCost] + constraint.tuples.values():
                if value in costs or value == WCSP.TOP:
                    continue
                bisect.insort(costs, value)
                if (minWeight is None or value < minWeight) and value > 0:
                    minWeight = value
        
        # compute the smallest difference between subsequent costs
        deltaMin = None
        w1 = costs[0]
        if len(costs) == 1:
            deltaMin = costs[0]
        for w2 in costs[1:]:
            diff = w2 - w1
            if deltaMin is None or diff < deltaMin:
                deltaMin = diff
            w1 = w2
        divisor = 1.0
        if minWeight < 1.0:
            divisor *= minWeight
        if deltaMin < 1.0:
            divisor *= deltaMin
        log.warning('divisor=%f, deltaMin=%f, minWeight=%f' % (divisor, deltaMin, minWeight))
        return divisor
    
    
    def _computeHardCosts(self, divisor):
        '''
        Computes the costs for hard constraints that determine
        costs for entirely inconsistent worlds (0 probability).
        '''
        costSum = long(0)
        for constraint in self.constraints:
            maxCost = max([constraint.defCost] + constraint.tuples.values())
            if maxCost == WCSP.TOP or maxCost == 0.0: continue
            cost = abs(long(maxCost / divisor))
            newSum = costSum + cost
            if newSum < costSum:
                raise Exception("Numeric Overflow")
            costSum = newSum
        top = costSum + 1
        print top
        if top < costSum:
            raise Exception("Numeric Overflow")
        if top > WCSP.MAX_COST:
            self.log.critical('Maximum costs exceeded: %d > %d' % (top, WCSP.MAX_COST))
            raise MaxCostExceeded()
        return long(top)
    
    def makeIntegerCostWCSP(self):
        '''
        Returns a new WCSP problem instance, which is semantically
        equivalent to the original one, but whose costs have been converted
        to integers.
        '''
        log = logging.getLogger()
        wcsp_ = copy.copy(self)
        divisor = wcsp_._computeDivisor()
        log.warning(divisor)
        top = wcsp_.top = wcsp_._computeHardCosts(divisor)
        for constraint in wcsp_.constraints:
            if constraint.defCost == WCSP.TOP:
                constraint.defCost = top
            else:
                constraint.defCost = long(float(constraint.defCost) / divisor)
            for tup, cost in constraint.tuples.iteritems():
                if cost == WCSP.TOP:
                    constraint.tuples[tup] = top
                else:
                    constraint.tuples[tup] = long(float(cost) / divisor)
        return wcsp_
    
                    
    def solve(self, verbose=False):
        '''
        Uses toulbar2 inference. Returns the best solution, i.e. a tuple
        of variable assignments.
        '''
        log = logging.getLogger(self.__class__.__name__)
        wcsp_ = self.makeIntegerCostWCSP()
        
        # append the process id to the filename to make it "process safe"
        wcspfilename = temp_wcsp_file % os.getpid()
        f = open(wcspfilename, 'w+')
        wcsp_.write(f)
#         cmd = 'toulbar2 -s -v=1 -e=0 -nopre -k=0 %s' % temp_wcsp_file
        f.close()
        cmd = 'toulbar2 -s %s' % wcspfilename
        log.debug('solving WCSP...')
        p = Popen(cmd, shell=True, stderr=PIPE, stdout=PIPE)
        solution = None
        nextLineIsSolution = False
        cost = None
        while True:
            l = p.stdout.readline()
            # print l
            if not l: break
            if l.startswith('New solution'):
                cost = long(l.split()[2])
                nextLineIsSolution = True
                continue
            if nextLineIsSolution:
                if verbose: print solution, cost
                solution = map(int, l.split())
                nextLineIsSolution = False
        p.wait()        
        retCode = p.returncode
        log.debug('toulbar2 process returned %s' % str(retCode))
        return solution, cost
    
if __name__ == '__main__':
    wcsp = WCSP()
    wcsp.read(open('test.wcsp'))
    wcsp.write(sys.stdout)
    print 'best solution:', wcsp.solve()
            
