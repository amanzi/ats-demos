ATS Demonstrations
==================

This is the regression and demo suite for ATS.

Running the demos
------------------

To run a standard set of the tests that run fairly quickly, but should
not be considered complete, run:

```
python regression_tests.py -e /path/to/ats --suite=standard .
```

Visualizing the results
------------------------

Inside each subdirectory is a jupyter notebook.  Jupyter comes fairly standard with most comprehensive python installations (see, for instance Ananconda python).  

```
jupyter notebook
```


List of problems
-----------------

* _richards-steadystate:_ Column of water, solves hydrostatic balance on the column to establish a water table.

