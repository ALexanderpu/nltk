# -*- coding: utf-8 -*-
# Natural Language Toolkit: An Incremental Earley Chart Parser
#
# Copyright (C) 2001-2009 NLTK Project
# Author: Peter Ljunglöf <peter.ljunglof@heatherleaf.se>
#         Rob Speer <rspeer@mit.edu>
#         Edward Loper <edloper@gradient.cis.upenn.edu>
#         Steven Bird <sb@csse.unimelb.edu.au>
#         Jean Mark Gawron <gawron@mail.sdsu.edu>
# URL: <http://www.nltk.org/>
# For license information, see LICENSE.TXT
#
# $Id: chart.py 8144 2009-06-01 22:27:39Z edloper $

"""
Data classes and parser implementations for I{incremental} chart 
parsers, which use dynamic programming to efficiently parse a text.  
A X{chart parser} derives parse trees for a text by iteratively adding 
\"edges\" to a \"chart\".  Each X{edge} represents a hypothesis about the tree
structure for a subsequence of the text.  The X{chart} is a
\"blackboard\" for composing and combining these hypotheses.

A parser is X{incremental}, if it guarantees that for all i, j where i < j,
all edges ending at i are built before any edges ending at j.    
This is appealing for, say, speech recognizer hypothesis filtering.

The main parser class is L{EarleyChartParser}, which is a top-down
algorithm, originally formulated by Jay Earley (1970).
"""

from nltk.grammar import *

from api import *
from chart import *
from featurechart import *

#////////////////////////////////////////////////////////////
# Incremental Chart
#////////////////////////////////////////////////////////////

class IncrementalChart(Chart):
    def initialize(self):
        # A sequence of edge lists contained in this chart.
        self._edgelists = tuple([] for x in self._positions())
        
        # The set of child pointer lists associated with each edge.
        self._edge_to_cpls = {}
        
        # Indexes mapping attribute values to lists of edges 
        # (used by select()).
        self._indexes = {}
    
    def edges(self):
        return list(self.iteredges())
    
    def iteredges(self):
        return (edge for edgelist in self._edgelists for edge in edgelist)
    
    def select(self, end, **restrictions):
        edgelist = self._edgelists[end]
        
        # If there are no restrictions, then return all edges.
        if restrictions=={}: return iter(edgelist)
            
        # Find the index corresponding to the given restrictions.
        restr_keys = restrictions.keys()
        restr_keys.sort()
        restr_keys = tuple(restr_keys)
        
        # If it doesn't exist, then create it.
        if restr_keys not in self._indexes:
            self._add_index(restr_keys)
                
        vals = tuple(restrictions[key] for key in restr_keys)
        return iter(self._indexes[restr_keys][end].get(vals, []))
    
    def _add_index(self, restr_keys):
        # Make sure it's a valid index.
        for key in restr_keys:
            if not hasattr(EdgeI, key):
                raise ValueError, 'Bad restriction: %s' % key
        
        # Create the index.
        index = self._indexes[restr_keys] = tuple({} for x in self._positions())
        
        # Add all existing edges to the index.
        for end, edgelist in enumerate(self._edgelists):
            this_index = index[end]
            for edge in edgelist:
                vals = tuple(getattr(edge, key)() for key in restr_keys)
                this_index.setdefault(vals, []).append(edge)
    
    def _register_with_indexes(self, edge):
        end = edge.end()
        for (restr_keys, index) in self._indexes.items():
            vals = tuple(getattr(edge, key)() for key in restr_keys)
            index[end].setdefault(vals, []).append(edge)
    
    def _append_edge(self, edge):
        self._edgelists[edge.end()].append(edge)
    
    def _positions(self):
        return xrange(self.num_leaves() + 1)    


class FeatureIncrementalChart(IncrementalChart, FeatureChart):
    def select(self, end, **restrictions):
        edgelist = self._edgelists[end]
        
        # If there are no restrictions, then return all edges.
        if restrictions=={}: return iter(edgelist)
            
        # Find the index corresponding to the given restrictions.
        restr_keys = restrictions.keys()
        restr_keys.sort()
        restr_keys = tuple(restr_keys)

        # If it doesn't exist, then create it.
        if restr_keys not in self._indexes:
            self._add_index(restr_keys)
                
        vals = tuple(self._get_type_if_possible(restrictions[key]) 
                     for key in restr_keys)
        return iter(self._indexes[restr_keys][end].get(vals, []))
    
    def _add_index(self, restr_keys):
        # Make sure it's a valid index.
        for key in restr_keys:
            if not hasattr(EdgeI, key):
                raise ValueError, 'Bad restriction: %s' % key

        # Create the index.
        index = self._indexes[restr_keys] = tuple({} for x in self._positions())

        # Add all existing edges to the index.
        for end, edgelist in enumerate(self._edgelists):
            this_index = index[end]
            for edge in edgelist:
                vals = tuple(self._get_type_if_possible(getattr(edge, key)()) 
                             for key in restr_keys)
                this_index.setdefault(vals, []).append(edge)
    
    def _register_with_indexes(self, edge):
        end = edge.end()
        for (restr_keys, index) in self._indexes.items():
            vals = tuple(self._get_type_if_possible(getattr(edge, key)())
                         for key in restr_keys)
            index[end].setdefault(vals, []).append(edge)


#////////////////////////////////////////////////////////////
# Earley CFG Rules
#////////////////////////////////////////////////////////////

class CompleterRule(SingleEdgeFundamentalRule):
    def apply_iter(self, chart, grammar, edge):
        if isinstance(edge, LeafEdge): return
        if edge.is_complete(): 
            for new_edge in self._apply_complete(chart, edge):
                yield new_edge

class ScannerRule(SingleEdgeFundamentalRule):
    def apply_iter(self, chart, grammar, edge):
        if not isinstance(edge, LeafEdge): return
        if edge.is_complete(): 
            for new_edge in self._apply_complete(chart, edge):
                yield new_edge

class PredictorRule(CachedTopDownPredictRule):
    pass

#////////////////////////////////////////////////////////////
# Earley FCFG Rules
#////////////////////////////////////////////////////////////

class FeatureCompleterRule(FeatureSingleEdgeFundamentalRule):
    _fundamental_rule = FeatureFundamentalRule()
    def apply_iter(self, chart, grammar, edge):
        if isinstance(edge, LeafEdge): return
        if edge.is_complete(): 
            fr = self._fundamental_rule
            for left_edge in chart.select(end=edge.start(), 
                                          is_complete=False,
                                          next=edge.lhs()):
                for new_edge in fr.apply_iter(chart, grammar, left_edge, edge):
                    yield new_edge

class FeatureScannerRule(FeatureSingleEdgeFundamentalRule):
    _fundamental_rule = FeatureFundamentalRule()
    def apply_iter(self, chart, grammar, edge):
        if not isinstance(edge, LeafEdge): return
        if edge.is_complete(): 
            fr = self._fundamental_rule
            for left_edge in chart.select(end=edge.start(), 
                                          is_complete=False,
                                          next=edge.lhs()):
                for new_edge in fr.apply_iter(chart, grammar, left_edge, edge):
                    yield new_edge

class FeaturePredictorRule(FeatureTopDownPredictRule): 
    pass

#////////////////////////////////////////////////////////////
# Incremental Earley Parser
#////////////////////////////////////////////////////////////

EARLEY_STRATEGY = [LeafInitRule(),
                   TopDownInitRule(), 
                   CompleterRule(), 
                   ScannerRule(),
                   PredictorRule()] 

FEATURE_EARLEY_STRATEGY = [LeafInitRule(),
                           FeatureTopDownInitRule(), 
                           FeatureCompleterRule(), 
                           FeatureScannerRule(),
                           FeaturePredictorRule()] 

class IncrementalChartParser(ChartParser):
    """
    An I{incremental} chart parser implementing Jay Earley's 
    parsing algorithm:

        - For each index I{end} in [0, 1, ..., N]:
          - For each I{edge} s.t. I{edge}.end = I{end}:
            - If I{edge} is incomplete, and I{edge}.next is not a part
              of speech:
                - Apply PredictorRule to I{edge}
            - If I{edge} is incomplete, and I{edge}.next is a part of
              speech:
                - Apply ScannerRule to I{edge}
            - If I{edge} is complete:
                - Apply CompleterRule to I{edge}
        - Return any complete parses in the chart
    """
    def __init__(self, grammar, strategy=EARLEY_STRATEGY,
                 trace=0, trace_chart_width=50, 
                 chart_class=IncrementalChart): 
        """
        Create a new Earley chart parser, that uses C{grammar} to
        parse texts.
        
        @type grammar: C{ContextFreeGrammar}
        @param grammar: The grammar used to parse texts.
        @type trace: C{int}
        @param trace: The level of tracing that should be used when
            parsing a text.  C{0} will generate no tracing output;
            and higher numbers will produce more verbose tracing
            output.
        @type trace_chart_width: C{int}
        @param trace_chart_width: The default total width reserved for 
            the chart in trace output.  The remainder of each line will 
            be used to display edges. 
        @param chart_class: The class that should be used to create
            the charts used by this parser.
        """
        self._grammar = grammar
        self._trace = trace
        self._trace_chart_width = trace_chart_width
        self._chart_class = chart_class
        
        self._axioms = []
        self._inference_rules = []
        for rule in strategy:
            if rule.NUM_EDGES == 0:
                self._axioms.append(rule)
            elif rule.NUM_EDGES == 1:
                self._inference_rules.append(rule)
            else:
                raise ValueError("Incremental inference rules must have "
                                 "NUM_EDGES == 0 or 1")

    def chart_parse(self, tokens, trace=None):
        if trace is None: trace = self._trace
        trace_new_edges = self._trace_new_edges

        tokens = list(tokens)
        self._grammar.check_coverage(tokens)
        chart = self._chart_class(tokens)
        grammar = self._grammar

        # Width, for printing trace edges.
        trace_edge_width = self._trace_chart_width / (chart.num_leaves() + 1)
        if trace: print chart.pp_leaves(trace_edge_width)

        for axiom in self._axioms:
            new_edges = axiom.apply(chart, grammar)
            trace_new_edges(chart, axiom, new_edges, trace, trace_edge_width)

        inference_rules = self._inference_rules
        for end in range(chart.num_leaves()+1):
            if trace > 1: print "\n* Processing queue:", end, "\n"
            agenda = list(chart.select(end=end))
            while agenda:
                edge = agenda.pop()
                for rule in inference_rules:
                    new_edges = rule.apply_iter(chart, grammar, edge)
                    if trace:
                        new_edges = list(new_edges)
                        trace_new_edges(chart, rule, new_edges, trace, trace_edge_width)
                    for edge in new_edges:
                        if edge.end()==end:
                            agenda.append(edge)

        return chart

class EarleyChartParser(IncrementalChartParser): 
    pass


class FeatureIncrementalChartParser(IncrementalChartParser, FeatureChartParser):
    def __init__(self, grammar, 
                 strategy=FEATURE_EARLEY_STRATEGY,
                 trace_chart_width=20, 
                 chart_class=FeatureIncrementalChart,
                 **parser_args): 
        IncrementalChartParser.__init__(self, grammar, 
                                        strategy=strategy,
                                        trace_chart_width=trace_chart_width,
                                        chart_class=chart_class,
                                        **parser_args)

class FeatureEarleyChartParser(FeatureIncrementalChartParser):
    pass


def demo(should_print_times=True, should_print_grammar=False,
         should_print_trees=True, trace=2,
         sent='I saw John with a dog with my cookie', numparses=5):
    """
    A demonstration of the Earley parsers.
    """
    import sys, time

    # The grammar for ChartParser and SteppingChartParser:
    grammar = nltk.parse.chart.demo_grammar()
    if should_print_grammar:
        print "* Grammar"
        print grammar

    # Tokenize the sample sentence.
    print "* Sentence:" 
    print sent
    tokens = sent.split()
    print tokens
    print

    # Do the parsing.
    earley = EarleyChartParser(grammar, trace=trace)
    t = time.clock()
    chart = earley.chart_parse(tokens)
    parses = chart.parses(grammar.start())
    t = time.clock()-t
    
    # Print results.
    if numparses:
        assert len(parses)==numparses, 'Not all parses found'
    if should_print_trees:
        for tree in parses: print tree
    else:
        print "Nr trees:", len(parses)
    if should_print_times:
        print "Time:", t

if __name__ == '__main__': demo()
