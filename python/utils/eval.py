# Classifier Evaluation
#
# (C) 2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
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

import pickle

class ConfusionMatrix(object):
	'''
	Represents a confusion matrix and provides some convenience methods
	for computing statistics like precision, recall, F1 score or methods
	for creating LaTex output.
	'''

	def __init__(self):
		self.matrix = {} # maps classification result to vector of ground truths
		self.instanceCount = 0
		self.labels = []

	def addClassificationResult(self, prediction, groundTruth):
		'''
		Add a new classification result to the confusion matrix.
		- gndTruth:	the correct label of an example
		- prediction:	the predicted class label of an example
		'''
		if not prediction in self.labels:
			self.labels.append(prediction)
		if not groundTruth in self.labels:
			self.labels.append(groundTruth)
		
		gndTruths = self.matrix.get(prediction, None)
		if gndTruths is None:
			gndTruths = {}
			self.matrix[prediction] = gndTruths
 		if self.matrix.get(groundTruth, None) is None:
 			self.matrix[groundTruth] = {groundTruth: 0}
		
		gndTruths[groundTruth] = gndTruths.get(groundTruth, 0) + 1
		self.instanceCount += 1
		
	def getMatrixEntry(self, pred, clazz):
		'''
		Returns the matrix entry for the prediction pred and ground truth clazz.
		'''
		if self.matrix.get(pred, None) is None or self.matrix[pred].get(clazz, None) is None:
			return 0
		return self.matrix[pred][clazz]
		
	def countClassifications(self, classname):
		'''
		Returns the true positive, true negative, false positive, false negative
		classification counts (in this order).
		'''
		tp = self.matrix.get(classname,{}).get(classname,0)
		classes = self.matrix.keys()
		fp = 0		
		for c in classes:
			if c != classname:
				fp += self.getMatrixEntry(classname, c)
		fn = 0
		for c in classes:
			if c != classname:
				fn += self.getMatrixEntry(c, classname)
		tn = 0
		for c in classes:
			if c != classname:
				for c2 in classes:
					if c2 != classname:
						tn += self.getMatrixEntry(c, c2)
		assert sum([tp, tn, fp, fn]) == self.instanceCount
		return tp, tn, fp, fn
		
	def getMetrics(self, classname):
		'''
		Returns the classifier evaluation metrices in the following order:
		Accuracy, Precision, Recall, F1-Score.
		'''
		classes = []
		for classification in self.matrix:
			for truth in self.matrix.get(classification,{}):
				try:
					classes.index(truth)
				except ValueError:
					classes.append(truth)
		
		classes = sorted(classes)
	
		tp, tn, fp, fn = self.countClassifications(classname)
		acc = None
		if tp + tn + fp + fn > 0:
			acc = (tp + tn) / float(tp + tn + fp + fn)
		
		pre = 0.0
		if tp + fp > 0:
			pre = tp / float(tp + fp)
		
		rec = 0.0
		if tp + fn > 0:
			rec = tp / float(tp + fn)
		
		f1 = 0.0
		if pre + rec > 0:
			f1  = (2.0 * pre * rec) / (pre + rec)
			
		return acc, pre, rec, f1

	def printLatexTable(self):		
		grid = "|l|"
		for cl in sorted(self.labels):
			grid += "l|"
		
		print "\\begin{table}[h!]"
		print "\\footnotesize"
		print "\\begin{tabular}{" + grid + "}"
		
		headerRow = r"Prediction/Ground Truth"
		for cl in sorted(self.labels):
			headerRow += r" & \begin{turn}{90}" + cl.replace('_', r'\_') + r'\end{turn}' 
		
		# count number of actual instances per class label
		examplesPerClass = {}
		for label in self.labels:
			tp, tn, fp, fn = self.countClassifications(label)
			examplesPerClass[label] = sum([tp, fp, fn])
			
		
		print r'\hline'
		print headerRow + r'\\ \hline'
		
		#for each class create row
		for clazz in sorted(self.labels):
			values = []
			#for each row fill colum
			for cl2 in sorted(self.labels):
				counts = self.getMatrixEntry(clazz, cl2)
				values.append(r'\cellcolor{tblgreen!%d}%s' % (int(round(float(counts)/examplesPerClass[clazz] * 100)), (r'\textbf{%d}' if clazz == cl2 else '%d') % counts))
			print clazz.replace('_', r'\_') + ' & ' + ' & '.join(values) + r'\\ \hline'
			
		print r"\end{tabular}"
		print r"\caption[Short Caption]{Long Caption}"
		print r"\label{fig:}"
		print r"\end{table}"

	def printPrecisions(self):
		
		classes = []
		for classification in self.matrix:
			for truth in self.matrix.get(classification,{}):
				try:
					classes.index(truth)
				except ValueError:
					classes.append(truth)
		
		classes = sorted(classes)
		
		for cf in classes:
			acc,pre,rec,f1 = self.getMetrics(cf)
			
			print '%s: - Acc=%.2f, Pre=%.2f, Rec=%.2f F1=%.2f' % (cf, acc, pre, rec, f1)
			print ""
			
		print ""

	def __str__(self):
		maxNumDigits = max(max(map(lambda x: x.values(), self.matrix.values()), key=max))
		maxNumDigits = len(str(maxNumDigits))
		maxClassLabelLength = max(map(len, self.matrix.keys()))
		padding = 1
		numLabels = len(self.matrix.keys())
		cellwidth = max(maxClassLabelLength, maxNumDigits, 3) + 2 * padding
		# create an horizontal line
		print maxNumDigits
		hline = '|' + '-' * (cellwidth) + '+'
		hline += '+'.join(['-' * (cellwidth)] * numLabels) + '|'
		sep = '|'
		outerHLine = '-' * len(hline)
 		
 		def createTableRow(args):
 			return sep + sep.join(map(lambda a: str(a).rjust(cellwidth-padding) + ' ' * padding, args)) + sep			
		endl = '\n'
		# draw the table
		table = outerHLine + endl
		table += createTableRow(['P\C'] + sorted(self.matrix.keys())) + endl
		table += hline + endl
		for i, clazz in enumerate(sorted(self.labels)):
			table += createTableRow([clazz] + map(lambda x: self.getMatrixEntry(clazz, x), sorted(self.labels))) + endl
			if i < len(self.matrix.keys()) - 1:
				table += hline + endl
		table += outerHLine
		return table

	def printTable(self):
		print self
		
	def toFile(self, filename):
		pickle.dump(self, open(filename, 'w+'))
			
if __name__ == '__main__':
	cm = ConfusionMatrix()
	
	for _ in range(10):
		cm.addClassificationResult("AAA","A")
	cm.addClassificationResult("AAA","AAA")
	cm.addClassificationResult("AAA","AAA")
	cm.addClassificationResult("AAA","AAA")
	cm.addClassificationResult("AAA","AAA")
	cm.addClassificationResult("AAA","B")
	cm.addClassificationResult("AAA","B")
	cm.addClassificationResult("AAA","C")
	cm.addClassificationResult("B","AAA")
	cm.addClassificationResult("B","AAA")
	cm.addClassificationResult("ffff=====B","AAA")
	cm.addClassificationResult("B","C")
	cm.addClassificationResult("B","C")
	cm.addClassificationResult("B","B")
	#cm.addClassificationResult("C","A")
	#cm.addClassificationResult("C","B")
	#cm.addClassificationResult("C","C")
	
	cm.printTable()
	cm.printPrecisions()
	cm.printLatexTable()
	
	print pickle.loads(pickle.dumps(cm))