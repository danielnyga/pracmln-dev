# 
#
# (C) 2011-2014 by Daniel Nyga (nyga@cs.uni-bremen.de)
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

class AtomicBlock(object):
    '''
    Represents a (mutually exclusive) block of ground atoms.
    '''
    
    def __init__(self, blockname, blockidx, *gndatoms):
        self.gndatoms = list(gndatoms)
        self.blockidx = blockidx
        self.name = blockname
    
    
    def iteratoms(self):
        '''
        Yields all ground atoms in this block, sorted by atom index ascending
        '''
        for atom in sorted(self.gndatoms, key=lambda a: a.idx):
            yield atom
    
    
    def getNumberOfValues(self):
        raise Exception('%s does not implement getNumberOfValues()' % self.__class__.__name__)
    
    
    def generateValueTuples(self, evidence=None):
        '''
        evidence mapping gnd atom indices to truth values
        '''
        raise Exception('%s does not implement generateValueTuples()' % self.__class__.__name__)
    
    
    def getValueIndex(self, value):
        '''
        Computes the index of the given value (for this atomic block, so only wrt
        the ground atoms contained in this block). Values are given as tuples. For
        a binary atomic bock (a 'normal' ground atom), the two values are represented
        by (0,) and (1,).
        '''
        raise Exception('%s does not implement getValueIndex()' % self.__class__.__name__)
    
    
    def getEvidenceIndex(self, evidence):
        '''
        Returns the index of this atomic block value for the given possible world.
        '''
        value = []
        for gndatom in self.gndatoms:
            value.append(evidence[gndatom.idx])
        return self.getValueIndex(tuple(value))
    
    
    def getEvidenceValue(self, evidence):
        '''
        Returns the value of this atomic block as a tuple of truth values.
        Exp: (0, 1, 0) for a mutex atomic block containing 3 gnd atoms
        '''
        value = []
        for gndatom in self.gndatoms:
            value.append(evidence[gndatom.idx])
        return tuple(value)
    
    
    def valueTuple2EvidenceDict(self, worldtuple):
        '''
        Takes a value tuple and transforms
        it into a dict mapping the respective atom indices to their truth values
        '''
        evidence = {}
        for atom, value in zip(self.gndatoms, worldtuple):
            evidence[atom.idx] = value
        return evidence
            
    
    def __str__(self):
        return '%s: %s' % (self.name, ','.join(map(str, self.gndatoms)))


class BinaryBlock(AtomicBlock):
    '''
    Represents a binary ("normal") ground atom with the two states 1 and 0
    '''

    def getNumberOfValues(self):
        return 2


    def generateValueTuples(self, evidence=None):
        if evidence is None:
            evidence = {}
        if len(self.gndatoms) == 0: return
        gndatom = self.gndatoms[0]
        if gndatom.idx in evidence:
            yield (evidence[gndatom.idx],)
            return
        for t in (0, 1): yield (t,)


    def getValueIndex(self, value):
        if value == (0,):
            return 0
        elif value == (1,):
            return 1
        else:
            raise Exception('Invalid world value for binary block %s: %s' % (str(self), str(value)))
        

class MutexBlock(AtomicBlock):
    '''
    Represents a mutually exclusive block of ground atoms.
    '''
    
    def getNumberOfValues(self):
        return len(self.gndatoms)
    
    
    def generateValueTuples(self, evidence=None):
        if evidence is None:
            evidence = {}
        for world in self._generateValueTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generateValueTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple(map(lambda x: 1 if x == 1 else 0, valpattern))
            return
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)

    
    def getValueIndex(self, value):
        if sum(value) != 1:
            raise Exception('Invalid world value for mutex block %s: %s' % (str(self), str(value)))
        else:
            return value.index(1)
        
        

class SoftMutexBlock(AtomicBlock):
    '''
    Represents a soft mutex block of ground atoms.
    '''
    
    def getNumberOfValues(self):
        return len(self.gndatoms) + 1


    def generateValueTuples(self, evidence=None):
        if evidence is None:
            evidence = {}
        for world in self._generateValueTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generateValueTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple(map(lambda x: 1 if x == 1 else 0, valpattern))
            return
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)
        yield tuple([0] * len(atomindices))
        
    
    def getValueIndex(self, value):
        if sum(value) > 1:
            raise Exception('Invalid world value for soft mutex block %s: %s' % (str(self), str(value)))
        try:
            return value.index(1)
        except ValueError:
            return self.getNumberOfValues() - 1
