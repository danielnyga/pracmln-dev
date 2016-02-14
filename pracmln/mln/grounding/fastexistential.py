# -*- coding: utf-8 -*-
#
# Fast Existential Grounding
#
# (C) 2016 by Marc Niehaus
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

import logging
from pracmln.logic.fol import Conjunction, Negation, Disjunction, Exist, Lit, Equality
from pracmln.mln.grounding.default import DefaultGroundingFactory
from pracmln.mln.constants import auto
from pracmln.mln.util import dict_union, dict_subset

logger = logging.getLogger(__name__)


class FastExistentialGrounding(DefaultGroundingFactory):
    def __init__(self, mrf, simplify=False, unsatfailure=False, formulas=None, cache=auto, **params):
        DefaultGroundingFactory.__init__(self, mrf, simplify, unsatfailure, formulas, cache, **params)

    def _itergroundings(self, simplify=True, unsatfailure=True):
        for formula in self.formulas:
            if not self.__is_applicable(formula):
                logger.warning("FastExistentialGrounding is not applicable for formula %s, using default grounding..."%
                               formula)
                for gf in formula.itergroundings(self.mrf):
                    yield gf
                continue
            negated_existential_quantifiers = \
                filter(FastExistentialGrounding.__is_negated_existential_quantifier, formula.children)
            other_child = filter(lambda c: not
                FastExistentialGrounding.__is_negated_existential_quantifier(c), formula.children)[0]
            for variable_assignment in other_child.itervargroundings(self.mrf):
                other_child_grounded = other_child.ground(self.mrf, variable_assignment)
                if other_child_grounded.truth(self.mrf.evidence) == 0.0:
                    continue
                conjunction_parts = list(self.__get_grounding(variable_assignment, negated_existential_quantifiers))
                conjunction_parts.append(other_child_grounded)
                grounding = Conjunction(conjunction_parts, mln=formula.mln, idx=formula.idx)
                if grounding.truth(self.mrf.evidence) != 0.0:
                    yield grounding

    def __is_applicable(self, formula):
        if not isinstance(formula, Conjunction):
            return False
        negated_existential_quantifiers = \
            filter(FastExistentialGrounding.__is_negated_existential_quantifier, formula.children)
        other_children = \
            filter(lambda c: not FastExistentialGrounding.__is_negated_existential_quantifier(c), formula.children)
        if len(other_children) != 1:
            return False
        return True

    @staticmethod
    def __is_negated_existential_quantifier(element):
        if not isinstance(element, Negation) or len(element.children)!=1 or not isinstance(element.children[0], Exist):
            return False
        existential_quantifier = element.children[0]
        for conjunction in existential_quantifier.children:
            if not isinstance(conjunction, Conjunction):
                return False
            literals = filter(lambda x: isinstance(x, Lit), conjunction.children)
            equality_comparisons = filter(lambda x: isinstance(x, Equality), conjunction.children)
            for equality_comparison in equality_comparisons:
                if not equality_comparison.negated:
                    return False
            others = filter(lambda x: not isinstance(x, Lit) and
                                      not isinstance(x, Disjunction) and
                                      not isinstance(x, Equality), conjunction.children)
            if len(literals) != 1 or len(others) > 0:
                return False
            for disjunction in filter(lambda x: isinstance(x, Disjunction), conjunction.children):
                for equality_comparison in disjunction.children:
                    if not isinstance(equality_comparison, Equality) or not equality_comparison.negated:
                        return False
        return True

    def __get_grounding(self, unfinished_assignment, negated_existential_quantifiers):
        for quantifier in negated_existential_quantifiers:
            exceptions = []
            for disjunction_or_predicate in quantifier.children[0].children[0].children:
                if isinstance(disjunction_or_predicate, Lit):
                    predicate = disjunction_or_predicate
                elif isinstance(disjunction_or_predicate, Equality):
                    equality_comparisons = [disjunction_or_predicate]
                else:
                    equality_comparisons =  disjunction_or_predicate.children
                if equality_comparisons:
                    current_exception = {}
                    exceptions.append(current_exception)
                for equality_comparison in equality_comparisons:
                    exception_value = equality_comparison.args[1]
                    if exception_value in unfinished_assignment:
                        exception_value = unfinished_assignment[exception_value]
                    current_exception[equality_comparison.args[0]] = exception_value
            for assignment in predicate.itervargroundings(self.mrf, unfinished_assignment):
                for exception in exceptions:
                    if dict_subset(exception, assignment):
                        break
                else:
                    ground_atom = predicate.ground(self.mrf, dict_union(assignment, unfinished_assignment))
                    ground_atom.negated = True
                    yield ground_atom
