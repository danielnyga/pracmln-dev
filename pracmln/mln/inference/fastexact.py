# -*- coding: utf-8 -*-
#
# Fast Exact Inference
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
from pracmln.mln.errors import MRFValueException
from pracmln.mln.inference.infer import Inference
from pracmln.mln.grounding.fastconj import FastConjunctionGrounding
from pracmln.mln.constants import HARD
from pracmln.logic.fol import Conjunction, GroundLit, TrueFalse
from numpy import exp
from operator import mul


class FastExact(Inference):
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)

    def _run(self):
        ground_formulas = self.__get_ground_formulas()
        hard_formulas = filter(lambda f: f.weight == HARD, ground_formulas)
        non_hard_formulas = filter(lambda f: f.weight != HARD, ground_formulas)
        evidence = self.__concatenate_formulas(self.__get_evidence_as_list_of_gnd_literals(), hard_formulas)
        non_weight_one_worlds = self.__get_non_weight_one_worlds(non_hard_formulas, self.queries, evidence)
        to_return = {query: self.__calculate_probability(ground_formulas, query, evidence,
                                                    non_weight_one_worlds.query_worlds_dict[query],
                                                    non_weight_one_worlds.evidence_worlds)
                for query in self.queries}
        return to_return

    class _NonWeightOneWorldCollection(object):
        def __init__(self, queries):
            self.evidence_worlds = []
            self.query_worlds_dict = dict.fromkeys(queries, [])

    def __get_evidence_as_list_of_gnd_literals(self):
        logical_evidence = []
        for i in range(0, len(self.mrf.evidence)):
            if self.mrf.evidence[i] is not None:
                if self.mrf.evidence[i] != 1 and self.mrf.evidence[i] != 0:
                    raise Exception("Unknown Probability value: " + str(self.mrf.evidence[i]))
                logical_evidence.append(GroundLit(self.mrf.gndatom(i), self.mrf.evidence[i] == 0, self.mln))
        return logical_evidence

    def __get_non_weight_one_worlds(self, non_hard_formulas, queries, evidence):
        to_return = self._NonWeightOneWorldCollection(queries)
        for formula in non_hard_formulas:
            evidence_generator = self.__concatenate_formulas(formula, evidence)
            if evidence_generator is not None:
                to_return.evidence_worlds += self.__get_worlds_satisfying_formula(evidence_generator)
            for query in queries:
                query_generator = self.__concatenate_formulas(formula, query, evidence)
                if not query_generator is None:
                    to_return.query_worlds_dict[query] += self.__get_worlds_satisfying_formula(query_generator)
        return to_return

    def __get_ground_formulas(self):
        grounder = FastConjunctionGrounding(self.mrf, False, False, self.mrf.formulas, -1)
        return [ground_formula.cnf() for ground_formula in grounder.itergroundings()]

    def __concatenate_formulas(self, *formulas):
        conjuncts = []
        for formula in formulas:
            # TODO: Support Disjunctions
            if isinstance(formula, Conjunction):
                #Make sure that the conjunction contains allowed elements
                child = self.__concatenate_formulas(*formula.children)
                if isinstance(child, Conjunction):
                    conjuncts += child.children
                else:
                    conjuncts.append(child)
            elif isinstance(formula, list):
                child = self.__concatenate_formulas(*formula)
                if isinstance(child, Conjunction):
                    conjuncts += child.children
                else:
                    conjuncts.append(child)
            elif isinstance(formula, TrueFalse):
                if formula.value == 1:
                    continue
                elif formula.value == 0:
                    return None
                else:
                    raise Exception("Unknown truth value for trueFalse: " + str(formula.value))
            elif isinstance(formula, GroundLit):
                conjuncts.append(formula)
            else:
                raise Exception("Unknown formula type:" + str(type(formula)))
        if len(conjuncts) == 0:
            return TrueFalse(1, self.mln)
        elif len(conjuncts) == 1:
            return conjuncts[0]
        else:
            return Conjunction(filter(lambda f: not isinstance(f, TrueFalse), conjuncts), self.mln)

    def __get_conjunction_as_dict_of_truth_values(self, logical_world_restrictions):
        evidence_truth_values = [None]*len(self.mrf.gndatoms)
        if isinstance(logical_world_restrictions, GroundLit):
            evidence_truth_values[logical_world_restrictions.gndatom.idx]=0 if logical_world_restrictions.negated else 1
        elif isinstance(logical_world_restrictions, Conjunction):
            for ground_literal in logical_world_restrictions.children:
                current_value = evidence_truth_values[ground_literal.gndatom.idx]
                new_value = 0 if ground_literal.negated else 1
                if current_value is not None and current_value != new_value:
                    return None
                evidence_truth_values[ground_literal.gndatom.idx] = new_value
        elif not (isinstance(logical_world_restrictions, TrueFalse) and logical_world_restrictions.value == 1):
            raise Exception("Unknown formula type:" + str(type(logical_world_restrictions)))
        for variable in self.mrf.variables:
            try:
                variable.consistent(evidence_truth_values)
            except MRFValueException as e:
                return None
        return dict(enumerate(evidence_truth_values))

    def __get_world_count(self, logical_world_restrictions):
        evidence_truth_values = self.__get_conjunction_as_dict_of_truth_values(logical_world_restrictions)
        if evidence_truth_values is None:
            return 0
        return reduce(mul, [variable.valuecount(evidence_truth_values) for variable in self.mrf.variables], 1)

    def __get_worlds_satisfying_formula(self, formula):
        world_restriction = self.__get_conjunction_as_dict_of_truth_values(formula)
        if world_restriction is None:
            return []

        def evaluate_variable(variables, old_world):
            if not variables:
                yield old_world
            else:
                variable = variables[0]
                other_variables = variables[1:]
                for _, world in variable.iterworlds(old_world):
                    for child_world in evaluate_variable(other_variables, world):
                        yield child_world
        to_return = list(evaluate_variable(self.mrf.variables, world_restriction))
        return to_return

    def __calculate_probability(self, ground_formulas, query, evidence, query_worlds, evidence_worlds):
        # TODO: Exact formulas are not handled correctly: Worlds violating hard formulas must have probability 0
        # TODO: What if no worlds match the evidence? div by zero?
        def get_world_probability(worlds):
            return sum([exp(sum([gf.weight * gf(w) for gf in ground_formulas])) for w in worlds])
        return (
                    self.__get_world_count(self.__concatenate_formulas(query, evidence)) - \
                    len(query_worlds) + \
                    get_world_probability(query_worlds)
               ) \
               * 1.0 / \
               (
                    self.__get_world_count(evidence) - \
                    len(evidence_worlds) + \
                    get_world_probability(evidence_worlds)
               )