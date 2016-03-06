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
from pracmln.mln.util import dict_subset, dict_union

logger = logging.getLogger(__name__)


class FastExistentialGrounding(DefaultGroundingFactory):
    def __init__(self, mrf, simplify=False, unsatfailure=False, formulas=None, cache=auto, **params):
        DefaultGroundingFactory.__init__(self, mrf, simplify, unsatfailure, formulas, cache, **params)

    def _itergroundings(self, simplify=True, unsatfailure=True):
        for formula in self.formulas:
            if not self.__is_applicable(formula):
                logger.info("FastExistentialGrounding is not applicable for formula %s, using default grounding..." %
                               formula)
                for gf in formula.itergroundings(self.mrf):
                    yield gf
                continue
            negated_existential_quantifiers = \
                filter(self.__is_negated_existential_quantifier, formula.children)
            partial_existential_groundings = list(self.__get_partial_groundings(negated_existential_quantifiers))
            other_child = filter(lambda c: not self.__is_negated_existential_quantifier(c), formula.children)[0]
            for variable_assignment in other_child.itervargroundings(self.mrf):
                other_child_grounded = other_child.ground(self.mrf, variable_assignment)
                grounded = True
                if isinstance(other_child_grounded, Conjunction):
                    conjunction_parts = list(other_child_grounded.children)
                else:
                    conjunction_parts = [other_child_grounded]
                for partial_grounding in partial_existential_groundings:
                    grounding_grounded, partial_groundings = partial_grounding.get_groundings(variable_assignment)
                    conjunction_parts += partial_groundings
                    grounded = grounded and grounding_grounded
                conjunction = conjunction_parts[0] if len(conjunction_parts) == 0 else \
                    Conjunction(conjunction_parts, mln=formula.mln)
                conjunction.idx = formula.idx
                if grounded:
                    yield conjunction
                else:
                    for new_assignment in conjunction.itervargroundings(self.mrf, variable_assignment):
                        yield conjunction.ground(self.mrf, dict_union(variable_assignment, new_assignment))

    def __is_applicable(self, formula):
        if not isinstance(formula, Conjunction):
            return False
        other_children = \
            filter(lambda c: not self.__is_negated_existential_quantifier(c), formula.children)
        if len(other_children) != 1:
            return False
        return True

    def __is_negated_existential_quantifier(self, element):
        if not isinstance(element, Negation) or len(element.children)!=1 or not isinstance(element.children[0], Exist):
            return False
        existential_quantifier = element.children[0]
        quantified_variables = set(existential_quantifier.vars)
        for conjunction in existential_quantifier.children:
            if isinstance(conjunction, Conjunction):
                literals = filter(lambda x: isinstance(x, Lit), conjunction.children)
                equality_comparisons = filter(lambda x: isinstance(x, Equality), conjunction.children)
                for equality_comparison in equality_comparisons:
                    if not equality_comparison.negated:
                        return False
                    if equality_comparison.args[0] not in quantified_variables \
                            or self.mrf.mln.logic.isvar(equality_comparison.args[1]):
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
            elif not isinstance(conjunction, Lit):
                return False
        return True

    def __get_partial_groundings(self, negated_existential_quantifiers):
        for quantifier in negated_existential_quantifiers:
            exceptions = []
            conjunction_or_predicate = quantifier.children[0].children[0]
            if isinstance(conjunction_or_predicate, Conjunction):
                for disjunction_or_predicate in conjunction_or_predicate.children:
                    if isinstance(disjunction_or_predicate, Lit):
                        predicate = disjunction_or_predicate
                        equality_comparisons = []
                    elif isinstance(disjunction_or_predicate, Equality):
                        equality_comparisons = [disjunction_or_predicate]
                    else:
                        equality_comparisons = disjunction_or_predicate.children
                    if equality_comparisons:
                        current_exception = {}
                        exceptions.append(current_exception)
                    for equality_comparison in equality_comparisons:
                        exception_value = equality_comparison.args[1]
                        current_exception[equality_comparison.args[0]] = exception_value
            else:
                predicate = conjunction_or_predicate
            variable_domains = predicate.vardoms()
            quantified_variables = quantifier.children[0].vars
            free_variables = set(filter(lambda v: self.mrf.mln.logic.isvar(v), predicate.args)) - \
                             set(quantified_variables)

            def get_assignment_of_quantified_variables(variables, partial_assignment={}):
                if not variables:
                    yield partial_assignment
                    return
                current_variable = variables[0]
                other_variables = variables[1:]
                for value in self.mrf.domains[variable_domains[current_variable]]:
                    partial_assignment[current_variable] = value
                    for result in get_assignment_of_quantified_variables(other_variables, partial_assignment):
                        yield result

            groundings = []
            for assignment in get_assignment_of_quantified_variables(quantified_variables):
                for exception in exceptions:
                    if dict_subset(exception, assignment):
                        break
                else:
                    ground_atom = predicate.ground(self.mrf, assignment, partial=True)
                    ground_atom.negated = True
                    groundings.append(ground_atom)
            yield FastExistentialGrounding.PartialExistentialGrounding(self.mrf, free_variables, groundings)

    class PartialExistentialGrounding(object):
        def __init__(self, mrf, free_variables, groundings):
            self.__free_variables = free_variables
            self.__groundings = groundings
            self.__mrf = mrf

        def get_groundings(self, assignment):
            if len(self.__free_variables) == 0:
                return True, self.__groundings
            elif all([var in assignment for var in self.__free_variables]):
                return True, [literal.ground(self.__mrf, assignment, partial=True) for literal in self.__groundings]
            else:
                return False, self.__groundings