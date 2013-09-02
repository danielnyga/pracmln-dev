#
# Clustering Methods
#
# (C) 2013 by Daniel Nyga, (nyga@cs.uni-bremen.de)
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
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.'''
from utils.evalSeqLabels import editDistance
import math
from mln.MarkovLogicNetwork import readMLNFromFile
from mln.database import readDBFromFile

class Cluster(object):
    '''
    Class representing a cluster of some set of abstract data points.
    '''
    
    def __init__(self, dataPoints=None):
        if dataPoints is None:
            dataPoints = []
        else:
            self.dataPoints = dataPoints
        self.type = None
        for point in dataPoints:
            t = type(point)
            t = 'number' if t is int or t is float or t is long else 'str'
            if self.type is not None and self.type != t:
                raise Exception('Data points must be all of the same type (%s).' % self.type)
            self.type = t
            
            
    def _computeCentroid(self, distance='auto'):
        '''
        Compute the centroid of the cluster.
        '''
        dist = self._getDistanceMetrics(distance)
        centroid = None
        if self.type == 'str':
            minAvgDist = float('inf')
            if len(self.dataPoints) == 1:
                return (self.dataPoints[0], 0)
            for p1 in self.dataPoints:
                avgDist = .0
                counter = 0
                for p2 in self.dataPoints:
                    if p1 is p2: continue
                    counter += 1
                    avgDist += dist(p1, p2)
                avgDist /= float(counter)
                if avgDist < minAvgDist:
                    minAvgDist = avgDist
                    centroid = p1
        elif self.type == 'number':
            centroid = map(lambda x: sum(x) / float(len(self.dataPoints)), zip(self.dataPoints))
        return centroid, minAvgDist
    
    def _getDistanceMetrics(self, distance):
        if distance == 'auto' and self.type == 'str':
            dist = editDistance
        elif distance == 'auto' and self.type == 'number':
            dist = lambda x, y: math.sqrt(sum(map(lambda x_1, x_2: (x_1 - x_2) ** 2, zip(x, y))))
        elif type(distance) is callable:
            dist = distance
        else:
            raise Exception('Distance measure not supported for the given data.')
        return dist
            
    def addPoint(self, dataPoint):
        '''
        Adds a data Point to the cluster.
        '''
        self.dataPoints.append(dataPoint)
        
    def computeDistance(self, cluster, linkage='avg', distance='auto'):
        '''
        Computes the distance between from the current cluster to the given one.
        - linkage:     specifies the linkage method for the clustering:
            - 'avg':   average linkage
            - 'single': single linkage
            - 'complete': complete coverage. 
        - distance:    the distance measure. Currently supported:
            - 'euclid':     the euclidean distance
            - 'edit':       the edit (Levenshtein) distance
            - 'manh':       the Manhatten distance
          distance also might be a callable for custom distance metrics.
        '''
        dist = self._getDistanceMetrics(distance)
        
        if linkage == 'avg':
            totalDist = .0
            for p1 in self.dataPoints:
                for p2 in cluster.dataPoints:
                    totalDist += dist(p1, p2)
            totalDist /= float(len(self.dataPoints))
        elif linkage == 'single':
            totalDist = float('inf')
            for p1 in self.dataPoints:
                for p2 in cluster.dataPoints:
                    d = dist(p1, p2)
                    if d < totalDist: totalDist = d
        elif linkage == 'complete':
            totalDist = .0
            for p1 in self.dataPoints:
                for p2 in cluster.dataPoints:
                    d = dist(p1, p2)
                    if d > totalDist: totalDist = d
        else:
            raise Exception('Linkage "%s" not supported.' % linkage)
        return totalDist
    
    def merge(self, cluster):
        '''
        Merges this cluster with the given one.
        '''
        self.dataPoints.extend(cluster.dataPoints)
        
    def __repr__(self):
        s = 'ClUSTER: {%s}' % ','.join(self.dataPoints)
        return s
        
        
def SAHN(dataPoints, threshold, linkage='avg', dist='auto'):
    '''
    Performs sequential agglomerative hierarchical non-overlapping (SAHN) clustering.
    ''' 
    clusters = [Cluster([p]) for p in dataPoints]
    
    print clusters
    while len(clusters) > 1:
        minDist = float('inf')
        for c1 in clusters:
            for c2 in clusters:
                if c1 is c2: continue
                d = c1.computeDistance(c2)
                if d < minDist:
                    minDist = d
                    minDistC1 = c1
                    minDistC2 = c2
        if minDist > threshold: break
        minDistC1.merge(minDistC2)
        clusters.remove(minDistC2)
        print clusters
        for c in clusters:
            print c._computeCentroid()
    return clusters
    
if __name__ == '__main__':
    
#     s = ['otto', 'otte', 'obama', 'markov logic network', 'markov logic', 'otta', 'markov random field']
#     
#     print SAHN(s, 100)
#     
    mln = readMLNFromFile('/home/nyga/code/pracmln/models/object-detection.mln')
    dbs = readDBFromFile(mln, '/home/nyga/code/pracmln/models/scenes.db')
    mln.materializeFormulaTemplates(dbs, verbose=True)
    print mln.domains['text']
    
    clusters = SAHN(mln.domains['text'], 20, linkage='complete')
            
    for c in clusters:
        print c
