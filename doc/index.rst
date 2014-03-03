.. mln_interface documentation master file, created by
   sphinx-quickstart on Tue Feb 25 11:53:18 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=========================================
PRACMLNs: Markov logic networks in Python
=========================================


About
-----

PRACMLNs is a toolbox for statistical relational learning and reasoning and as such also
includes tools for standard graphical models. PRACMLNs is a fork of the *ProbCog* toolbox.

PRACMLN is a statistical relational learning and reasoning system 
that supports efficient learning and inference in relational 
domains. We provide an extensive set of open-source tools for both 
undirected and directed statistical relational models.

Though ProbCog is a general-purpose software suite, it was designed 
with the particular needs of technical systems in mind. Our methods 
are geared towards practical applicability and can easily be 
integrated into other applications. The tools for relational data 
collection and transformation facilitate data-driven knowledge 
engineering, and the availability of graphical tools makes both 
learning or inference sessions a user-friendly experience. 
Scripting support enables automation, and for easy integration into 
other applications, we provide a client-server library. There is 
also support for the `ROS (Robot Operating System) <http://www.ros.org/>`_
middleware.

* Bayesian logic networks (BLNs): learning and inference
* Markov logic networks (MLNs): learning and inference
* Bayesian networks: learning and inference
* Logic: representation, propositionalization, stochastic SAT sampling, etc.

This package consists of:

* An implementation of MLNs as a Python module (mln.py) that you can use to work with MLNs in your own Python scripts 
* Graphical tools for performing inference in MLNs and learning the parameters of MLNs, using either PyMLNs itself, J-MLNs (a Java implementation of MLNs that is shipped with ProbCog) or the Alchemy system as the underlying engine.

Contents:

.. toctree::
   :maxdepth: 2

   features
   installation
   intro
   tutorial

Contributors:
^^^^^^^^^^^^^
* Daniel Nyga (`nyga@cs.uni-bremen.de <mailto:nyga@cs.uni-bremen.de>`_)
* Dominik Jain
* Valentine Chiwome
* Hartmut Messerschmidt

Former Contributors (from ProbCog):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Stefan Waldherr
* Klaus von Gleissenthall
* Andreas Barthels
* Ralf Wernicke
* Gregor Wylezich
* Martin Schuster
* Philipp Meyer

Acknowledgements
^^^^^^^^^^^^^^^^

This work is supported in part by the EU FP7 projects
`RoboHow <http://www.robohow.org>`_ (grant number 288533) and `ACAT <http://www.acat-project.eu>`_ (grant number
600578).

This project builds upon third-party software including

* Bayesian network tools in Java (`<http://bnj.sourceforge.net>`_)
* The WEKA machine learning library (`<http://www.cs.waikato.ac.nz/ml/weka/>`_)


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

