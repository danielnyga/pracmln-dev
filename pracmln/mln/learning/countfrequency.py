# -*- coding: utf-8 -*-
#
# Count Frequency Learning
#
# (C) 2015 by Marc Niehaus
#
# Contains code from pracmln and uses the pracmln framework
#
# (C) 2012-2015 by Daniel Nyga
#     2006-2011 by Dominik Jain
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
from numpy import exp, log
from pracmln.mln.grounding.fastconj import FastConjunctionGrounding


class CountFrequency(object):
    def __init__(self, mln, databases):
        self.mln = mln.materialize(*databases)
        self.databases = databases

    @property
    def name(self):
        return "CountFrequency"

    def run(self, **unused_kwargs):
        frequencies = [exp(float(w)-CountFrequency.__get_value_for_frequency_one()) for w in self.mln.weights]
        for db in self.databases:
            mrf = self.mln.ground(db)
            mrf_frequencies = CountFrequency.__get_frequency_for_database(mrf)
            frequencies = [pair[0]+pair[1] for pair in zip(frequencies, mrf_frequencies)]
        return [self.__convert_frequency_to_weight(frequency) for frequency in frequencies]

    @staticmethod
    def __get_frequency_for_database(mrf):
        for index, value in enumerate(mrf.evidence):
            if value is None:
                mrf.evidence[index] = 0
        to_return = [0]*len(mrf.formulas)
        for ground_formula in mrf.itergroundings():
            value = ground_formula(mrf.evidence)
            if value is not None:
                to_return[ground_formula.idx] += value
        return to_return

    @staticmethod
    def __get_value_for_frequency_one():
        return 40

    @staticmethod
    def __convert_frequency_to_weight(frequency):
        return 0 if frequency == 0 else CountFrequency.__get_value_for_frequency_one() + log(frequency)