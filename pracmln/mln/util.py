# -*- coding: utf-8 -*-
#
# Markov Logic Networks
#
# (C) 2006-2010 by Dominik Jain (jain@cs.tum.edu)
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

import re
import time
import logging
import sys
import os
import traceback
from pracmln.praclog.logformat import RainbowLoggingHandler
from collections import defaultdict

# math functions

USE_MPMATH = True

try:
    if not USE_MPMATH:
        raise Exception()
    import mpmath  # @UnresolvedImport
    mpmath.mp.dps = 80
    from mpmath import exp, fsum, log  # @UnresolvedImport
except:
    from math import exp, log
    try:
        from math import fsum 
    except: # not support   ed in Python 2.5
        fsum = sum
#sys.stderr.write("Warning: Falling back to standard math module because mpmath is not installed. If overflow errors occur, consider installing mpmath.")
from math import floor, ceil, e, sqrt

import math

def currentframe():
    """Return the frame object for the caller's stack frame."""
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back

if hasattr(sys, '_getframe'): currentframe = lambda: sys._getframe(3)

def caller():
    """
    Find the stack frame of the caller so that we can note the source
    file name, line number and function name.
    """
    f = currentframe()
    #On some versions of IronPython, currentframe() returns None if
    #IronPython isn't run with -X:Frames.
    rv = "(unknown file)", 0, "(unknown function)"
    while hasattr(f, "f_code"):
        co = f.f_code
        filename = os.path.normcase(co.co_filename)
        if filename == __file__:
            f = f.f_back
            continue
        rv = (co.co_filename, f.f_lineno, co.co_name)
        break
    return rv


def out(*args):
    rv = caller()
    print '%s: l.%d: %s' % (os.path.basename(rv[0]), rv[1], ' '.join(map(str, args)))


def stop(*args):
    rv = caller()
    print '%s: l.%d: %s' % (os.path.basename(rv[0]), rv[1], ' '.join(map(str, args)))
    print '<press enter to continue>'
    raw_input()
    

def trace(*args):
    print '=== STACK TRACE ==='
    traceback.print_stack()
    sys.stdout.flush()
    sys.stderr.flush()
    rv = caller()
    print '%s: l.%d: %s' % (os.path.basename(rv[0]), rv[1], ' '.join(map(str, args)))
    
def stoptrace(*args):
    print '=== STACK TRACE ==='
    traceback.print_stack()
    sys.stdout.flush()
    sys.stderr.flush()
    rv = caller()
    print '%s: l.%d: %s' % (os.path.basename(rv[0]), rv[1], ' '.join(map(str, args)))
    print '<press enter to continue>'
    raw_input()
    


def flip(value):
    '''
    Flips the given binary value to its complement.
    
    Works with ints and booleans. 
    '''
    if type(value) is bool:
        return True if value is False else False
    elif type(value) is int:
        return 1 - value
    else:
        TypeError('type %s not allowed' % type(value))

def logx(x):
    if x == 0:
        return - 100
    return math.log(x) #used for weights -> no high precision (mpmath) necessary


def stripComments(text):
#     comment = re.compile(r'//.*?$|/\*.*?\*/', re.DOTALL | re.MULTILINE)
#     return re.sub(comment, '', text)
    # this is a more sophisticated regex to replace c++ style comments
    # taken from http://stackoverflow.com/questions/241327/python-snippet-to-remove-c-and-c-comments
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)


def parse_queries(mln, query_str):
    '''
    Parses a list of comma-separated query strings.
    
    Admissible queries are all kinds of formulas or just predicate names.
    Returns a list of the queries.
    '''
    queries = []
    query_preds = set()
    q = ''
    for s in map(str.strip, query_str.split(',')):
        if not s: continue
        if q != '': q += ','
        q += s
        if balancedParentheses(q):
            try:
                # try to read it as a formula and update query predicates
                f = mln.logic.parse_formula(q)
                literals = f.literals()
                prednames = map(lambda l: l.predname, literals)
                query_preds.update(prednames)
            except:
                # not a formula, must be a pure predicate name 
                query_preds.add(s)
            queries.append(q)
            q = ''
    if q != '': raise Exception('Unbalanced parentheses in queries: ' + q)
    return queries


def predicate_declaration_string(predName, domains, blocks):
    '''
    Returns a string representation of the given predicate.
    '''
    args_list = ['%s%s' % (arg, {True: '!', False: ''}[block]) for arg, block in zip(domains, blocks)]
    args = ', '.join(args_list)
    return '%s(%s)' % (predName, args)


def getPredicateList(filename):
    ''' gets the set of predicate names from an MLN file '''
    content = file(filename, "r").read() + "\n"
    content = stripComments(content)
    lines = content.split("\n")
    predDecl = re.compile(r"(\w+)\([^\)]+\)")
    preds = set()
    for line in lines:
        line = line.strip()
        m = predDecl.match(line)
        if m is not None:
            preds.add(m.group(1))
    return list(preds)

def avg(*a):
    return sum(map(float, a)) / len(a)


class CallByRef(object):
    '''
    Convenience class for treating any kind of variable as an object that can be
    manipulated in-place by a call-by-reference, in particular for primitive data types such as numbers.
    '''
    
    def __init__(self, value):
        self.value = value
        
INC = 1
EXC = 2

class Interval():
    
    def __init__(self, interval):
        tokens = re.findall(r'(\(|\[|\])([-+]?\d*\.\d+|\d+),([-+]?\d*\.\d+|\d+)(\)|\]|\[)', interval.strip())[0]
        if tokens[0] in ('(', ']'):
            self.left = EXC
        elif tokens[0] == '[':
            self.left = INC
        else:
            raise Exception('Illegal interval: %s' % interval)
        if tokens[3] in (')', '['): 
            self.right = EXC
        elif tokens[3] == ']':
            self.right = INC
        else:
            raise Exception('Illegal interval: %s' % interval)
        self.start = float(tokens[1]) 
        self.end = float(tokens[2])
        
    def __contains__(self, x):
        return (self.start <= x if self.left == INC else self.start < x) and  (self.end >= x if self.right == INC else self.end > x) 
        
    
def ifNone(expr, else_expr, transform=None):
    '''
    Short version of the ternary if-then-else construct that returns the given expression `expr` if it is
    not `None` or else_expr otherwise. Optionally, a transformation can be specified, which
    is applied to `expr` in case it is not None.
    
    :Example:
    
    >>> import time
    >>> print ifNone(time.time(), 'N/A')
    >>> 1434619614.42
    >>> print ifNone(None, 'N/A')
    N/A
    >>> print ifNone(time.time(), 'N/A', time.ctime)
    Thu Jun 18 11:27:23 2015
    >>> print ifNone(None, 'N/A', time.ctime)
    N/A
    '''
    if expr is None:
        return else_expr
    else:
        if transform is not None:
            return transform(expr)
        else:
            return expr


def elapsedtime(start, end=None):
    '''
    Compute the elapsed time of the interval `start` to `end`.
    
    Returns a pair (t,s) where t is the time in seconds elapsed thus 
    far (since construction) and s is a readable string representation thereof.
    
    :param start:    the starting point of the time interval.
    :param end:      the end point of the time interval. If `None`, the current time is taken.
    '''
    if end is not None:
        elapsed = end - start
    else:
        elapsed = time.time() - start
    return elapsed_time_str(elapsed)
    
    
def elapsed_time_str(elapsed):
    hours = int(elapsed / 3600)
    elapsed -= hours * 3600
    minutes = int(elapsed / 60)
    elapsed -= minutes * 60
    secs = int(elapsed)
    msecs = int((elapsed - secs) * 1000)
    return "%d:%02d:%02d.%03d" % (hours, minutes, secs, msecs)


def balancedParentheses(s):
    cnt = 0
    for c in s:
        if c == '(':
            cnt += 1
        elif c == ')':
            if cnt <= 0:
                return False
            cnt -= 1
    return cnt == 0
  
def fstr(f):
    s = str(f)
    while s[0] == '(' and s[ -1] == ')':
        s2 = s[1:-1]
        if not balancedParentheses(s2):
            return s
        s = s2
    return s


def evidence2conjunction(evidence):
    '''
    Converts the evidence obtained from a database (dict mapping ground atom names to truth values) to a conjunction (string)
    '''
    evidence = map(lambda x: ("" if x[1] else "!") + x[0], evidence.iteritems())
    return " ^ ".join(evidence)


def tty(stream):
    isatty = getattr(stream, 'isatty', None)
    return isatty and isatty()
    
def barstr(width, percent, color=None):
    '''
    Returns the string representation of an ASCII 'progress bar'.
    
    
    '''
    barw = int(round(width * percent))
    bar = ''.ljust(barw, '=')
    bar = bar.ljust(width, ' ')
    if color is not None:
        filler = u'\u25A0'
        bar = bar.replace('=', filler)
        bar = colorize('[', format=(None, None, True), color=True) + colorize(bar, format=(None, color, False), color=True) + colorize(']', format=(None, None, True), color=True)
    else:
        bar = '[%s]' % bar
    return u'{0} {1: >7.3f} %'.format(bar, percent * 100.).encode('utf8') 


class ProgressBar():
    
    def __init__(self, width, value=0, steps=None, label='', color=None, stream=sys.stdout):
        self.width = width
        self.steps = steps
        if steps is not None:
            self.step = value
            self.value = float(value) / steps
        else:
            self.value = value
            self.step = None
            self.steps = None
        self.color = color
        self._label = label
        if tty(sys.stdout):
            self.update(self.value)
        
        
    def label(self, label):
        self._label = label
        self.update(self.value)
        
    
    def update(self, value, label=None):
        self.value = value
        if label is not None: self._label = label
        if value == 1: self._label = ''
        if tty(sys.stdout):
            sys.stdout.write(barstr(self.width, value, color=self.color) + ' ' + self._label[:min(len(self._label), 100)].ljust(100, ' ') +  ('\r' if value < 1. else '\n'))
            sys.stdout.flush()
            
    
    def inc(self):
        if self.steps is None:
            raise Exception('Cannot call inc() on a real-valued progress bar.')
        self.step += 1
        self.value = float(self.step) / self.steps
        self.update(self.value)
        
BOLD = (None, None, True)
            
def headline(s):
    l = ''.ljust(len(s), '=')
    return '%s\n%s\n%s' % (colorize(l, BOLD, True), colorize(s, BOLD, True), colorize(l, BOLD, True))


def gaussianZeroMean(x, sigma):
    return 1.0/sqrt(2 * math.pi * sigma**2) * math.exp(- (x**2) / (2 * sigma**2))


def gradGaussianZeroMean(x, sigma):
    return - (0.3990434423 * x * math.exp(-0.5 * x**2 / sigma**2) ) / (sigma**3)


def mergedom(*domains):
    ''' 
    Returning a new domains dictionary that contains the elements of all the given domains
    '''
    fullDomain = {}
    for domain in domains:
        for domName, values in domain.iteritems():
            if domName not in fullDomain:
                fullDomain[domName] = set(values)
            else:
                fullDomain[domName].update(values)
    for key, s in fullDomain.iteritems():
        fullDomain[key] = list(s)
    return fullDomain




def colorize(message, format, color=False):
    '''
    Returns the given message in a colorized format
    string with ANSI escape codes for colorized console outputs:
    - message:   the message to be formatted.
    - format:    triple containing format information:
                 (bg-color, fg-color, bf-boolean) supported colors are
                 'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'
    - color:     boolean determining whether or not the colorization
                 is to be actually performed.
    '''
    colorize.colorHandler = RainbowLoggingHandler(sys.stdout)
    if color is False: return message
    params = []
    (bg, fg, bold) = format
    if bg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[bg] + 40))
    if fg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[fg] + 30))
    if bold:
        params.append('1')
    if params:
        message = ''.join((colorize.colorHandler.csi, ';'.join(params),
                           'm', message, colorize.colorHandler.reset))
    return message


class StopWatchTag:
    
    def __init__(self, label, starttime, stoptime=None):
        self.label = label
        self.starttime = starttime
        self.stoptime = stoptime
        
    @property
    def elapsedtime(self):
        return ifNone(self.stoptime, time.time()) - self.starttime 
    
    @property
    def finished(self):
        return self.stoptime is not None
    

class StopWatch(object):
    '''
    Simple tagging of time spans.
    '''
    
    
    def __init__(self):
        self.tags = {}
    
        
    def tag(self, label, verbose=True):
        if verbose:
            print '%s...' % label
        tag = self.tags.get(label)
        now = time.time()
        if tag is None:
            tag = StopWatchTag(label, now)
        else:
            tag.starttime = now
        self.tags[label] = tag
    
    
    def finish(self, label=None):
        now = time.time()
        if label is None:
            for _, tag in self.tags.iteritems():
                tag.stoptime = ifNone(tag.stoptime, now)
        else:
            tag = self.tags.get(label)
            if tag is None:
                raise Exception('Unknown tag: %s' % label)
            tag.stoptime = now

    
    def __getitem__(self, key):
        return self.tags.get(key)

    
    def reset(self):
        self.tags = {}

        
    def printSteps(self):
        for t in sorted(self.tags.values(), key=lambda t: t.starttime):
            if t.finished:
                print '%s took %s' % (colorize(t.label, (None, None, True), True), elapsed_time_str(t.elapsedtime))
            else:
                print '%s is running for %s now...' % (colorize(t.label, (None, None, True), True), elapsed_time_str(t.elapsedtime))


def combinations(domains):
    if len(domains) == 0:
        raise Exception('domains mustn\'t be empty')
    return _combinations(domains, [])

def _combinations(domains, comb):
    if len(domains) == 0:
        yield comb
        return
    for v in domains[0]:
        for ret in _combinations(domains[1:], comb + [v]):
            yield ret
            
def deprecated(func):
    '''
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used.
    '''
    def newFunc(*args, **kwargs):
        logging.getLogger().warning("Call to deprecated function: %s." % func.__name__)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc
            
def unifyDicts(d1, d2):
    '''
    Adds all key-value pairs from d2 to d1.
    '''
    for key in d2:
        d1[key] = d2[key]
        
def dict_union(d1, d2):
    '''
    Returns a new dict containing all items from d1 and d2. Entries in d1 are
    overridden by the respective items in d2.
    '''
    d_new = {}
    for key, value in d1.iteritems():
        d_new[key] = value
    for key, value in d2.iteritems():
        d_new[key] = value
    return d_new


def dict_subset(subset, superset):
    '''
    Checks whether or not a dictionary is a subset of another dictionary.
    '''
    return all(item in superset.items() for item in subset.items())


class edict(dict):
    
    def __add__(self, d):
        return dict_union(self, d)
    
    def __sub__(self, d):
        if type(d) in (dict, defaultdict):
            ret = dict(self)
            for k in d:
                del ret[k]
        else:
            ret = dict(self)
            del ret[d]
        return ret
    

class temporary_evidence():
    '''
    Context guard class for enabling convenient handling of temporary evidence in
    MRFs using the python `with` statement. This guarantees that the evidence
    is set back to the original whatever happens in the `with` block.
    
    :Example:
    
    >> with temporary_evidence(mrf, [0, 0, 0, 1, 0, None, None]) as mrf_:
    '''
    
    
    def __init__(self, mrf, evidence=None):
        self.mrf = mrf
        self.evidence_backup = list(mrf.evidence)
        if evidence is not None:
            self.mrf.evidence = evidence 
        
    def __enter__(self):
        return self.mrf
    
    def __exit__(self, *args):
        self.mrf.evidence = self.evidence_backup
        return True
        
    
if __name__ == '__main__':
    
    d = edict({1:2,2:3,'hi':'world'})
    print d
    print d + {'bla': 'blub'}
    print d
    print d - 1
    print d - {'hi': 'bla'}
    print d
    
