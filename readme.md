
pracmln -- Markov logic networks in Python
==========================================

pracmln is a toolbox for statistical relational learning and reasoning and provides a pure python implementation of Markov logic networks. pracmln is a statistical relational learning and reasoning system that supports efficient learning and inference in relational domains. pracmln has started as a fork of the ProbCog toolbox and has been extended by latest developments in learning and reasoning by the Institute for Artificial Intelligence  at the University of Bremen, Germany.


  * Project Page: http://www.pracmln.org
  * Lead developer: Daniel Nyga (nyga@cs.uni-bremen.de)

Release notes
-------------

  * Version 1.1.0 (13.06.2016)
    * *Fix*: C++ bindings
    * *Feature*: literal groups for formula expansion
    * *Fix*: existentially quantified formulas evaluate to false when they cannot be grounded
    * *Fix*: cleanup of process pools in multicore mode

Documentation
-------------

pracmln comes with its own sphinx-based documentation. To build it, conduct the following actions:

    $ cd path/to/pracmln/doc
    $ make html

If you have installed Sphinx, the documentation should be build. Open
it in your favorite web browser:

    $ firefox _build/html/index.html

Sphinx can be installed with

    $ sudo pip install sphinx sphinxcontrib-bibtex 



