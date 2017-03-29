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
from functools import reduce

logger = logging.getLogger(__name__)


class FastExistentialGrounding(DefaultGroundingFactory):
    """
    This class provides a grounder for formulas containing negated existential quantifiers.
    The grounder especially good if formulas like the following shall be grounded:
    !(EXIST ?p0 ,?p1 ((?p0=/="TYPE" v ?p1=/="mug") ^ (dP(?d0,?p0,?p1))) ^ (dP(?d0, "TYPE", "mug"))
    shall be grounded.
    It replaces the negated existential quantifier by a list of negated ground atoms.
    For example, if the domain of ?d0 is D, the domain of ?po is "TYPE", "NAME" and the domain of ?p1 is "mug", "plate",
    the grounder yields the following formula:
    dP(D, "TYPE", "mug") ^ !dP(D, "TYPE", "plate") ^ !dP(D, "NAME", "mug") ^ !dp(D, "NAME", "plate")
    """

    def __init__(self, mrf, simplify=False, unsatfailure=False, formulas=None, cache=auto, **params):
        DefaultGroundingFactory.__init__(self, mrf, simplify, unsatfailure, formulas, cache, **params)

    def _itergroundings(self, simplify=True, unsatfailure=True):
        cache = {}
        for formula in self.formulas:
            if not self.__is_applicable(formula):
                logger.info("FastExistentialGrounding is not applicable for formula %s, using default grounding..." %
                               formula)
                for gf in formula.itergroundings(self.mrf):
                    yield gf
                continue
            negated_existential_quantifiers = list(filter(self.__is_negated_existential_quantifier, formula.children))
            other_child = filter(lambda c: not self.__is_negated_existential_quantifier(c), formula.children)[0]
            for variable_assignment in other_child.itervargroundings(self.mrf):
                other_child_grounded = other_child.ground(self.mrf, variable_assignment)
                conjunction_parts = \
                    list(self.__get_grounding(variable_assignment, negated_existential_quantifiers, cache))
                if isinstance(other_child_grounded, Conjunction):
                    conjunction_parts += list(other_child_grounded.children)
                else:
                    conjunction_parts.append(other_child_grounded)
                grounding = Conjunction(conjunction_parts, mln=formula.mln, idx=formula.idx)
                grounding.weight = formula.weight
                yield grounding

    def __is_applicable(self, formula):
        if not isinstance(formula, Conjunction):
            return False
        other_children = [c for c in formula.children if not self.__is_negated_existential_quantifier(c)]
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
                literals = [x for x in conjunction.children if isinstance(x, Lit)]
                equality_comparisons = [x for x in conjunction.children if isinstance(x, Equality)]
                for equality_comparison in equality_comparisons:
                    if not equality_comparison.negated:
                        return False
                    if equality_comparison.args[0] not in quantified_variables \
                            or self.mrf.mln.logic.isvar(equality_comparison.args[1]):
                        return False

                others = [x for x in conjunction.children if not isinstance(x, Lit) and
                                          not isinstance(x, Disjunction) and
                                          not isinstance(x, Equality)]
                if len(literals) != 1 or len(others) > 0:
                    return False
                for disjunction in [x for x in conjunction.children if isinstance(x, Disjunction)]:
                    for equality_comparison in disjunction.children:
                        if not isinstance(equality_comparison, Equality) or not equality_comparison.negated:
                            return False
            elif not isinstance(conjunction, Lit):
                return False
        return True

    def __get_grounding(self, unfinished_assignment, negated_existential_quantifiers, cache):
        for quantifier in negated_existential_quantifiers:
            exceptions = []
            conjunction_or_predicate = quantifier.children[0].children[0]
            if isinstance(conjunction_or_predicate, Conjunction):
                for disjunction_or_predicate in conjunction_or_predicate.children:
                    if isinstance(disjunction_or_predicate, Lit):
                        predicate = disjunction_or_predicate
                    elif isinstance(disjunction_or_predicate, Equality):
                        equality_comparisons = [disjunction_or_predicate]
                    else:
                        equality_comparisons = disjunction_or_predicate.children
                    if equality_comparisons:
                        current_exception = {}
                        exceptions.append(current_exception)
                    for equality_comparison in equality_comparisons:
                        exception_value = equality_comparison.args[1]
                        if exception_value in unfinished_assignment:
                            exception_value = unfinished_assignment[exception_value]
                        current_exception[equality_comparison.args[0]] = exception_value
            else:
                predicate = conjunction_or_predicate

            quantified_variables = set(quantifier.children[0].vars)
            quantified_variables = [v for v in predicate.args if v in quantified_variables]
            quantified_indices = {i for i,v in enumerate(predicate.args) if v in quantified_variables}

            def get_exception_values(variables, exception, assembled_exception):
                if not variables:
                    return [assembled_exception]
                elif variables[0] in exception:
                    return get_exception_values(variables[1:], exception, assembled_exception+[exception[variables[0]]])
                else:
                    to_return = []
                    for value in predicate.vardom(variables[0]):
                        to_return += get_exception_values(variables[1:], exception, assembled_exception+[value])
                    return to_return

            exceptions = [get_exception_values(quantified_variables, e, []) for e in exceptions]
            exceptions = reduce(lambda a, b: a+b, exceptions, [])

            def is_exception(current_ground_literal):
                quantified_literal_values = [var for idx, var in enumerate(current_ground_literal.args)
                                             if idx in quantified_indices]
                for exception in exceptions:
                    if exception == quantified_literal_values:
                        return True
                return False

            cache_key = str(predicate.ground(self.mrf, unfinished_assignment, partial=True))
            if cache_key not in cache:
                cache[cache_key] = []
                for assignment in predicate.itervargroundings(self.mrf, unfinished_assignment):
                    ground_literal = predicate.ground(self.mrf, dict_union(assignment, unfinished_assignment))
                    ground_literal.negated = True
                    cache[cache_key].append(ground_literal)
                    if not is_exception(ground_literal):
                        yield ground_literal
            else:
                for ground_literal in cache[cache_key]:
                    if not is_exception(ground_literal):
                        yield ground_literal
