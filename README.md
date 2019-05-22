ATS Demonstrations
==================

This is a suite of demonstration problems which show the various capabilities and typical workflows of ATS simulations.

A wide range of capabilities are shown here -- this is really meant to be the first introduction to ATS and the primary introductory documentation for ATS.  **Start here!**

Included in each demonstration folder is a collection of runs meant to map out usage of the described physical capability.  These include everything needed to get started using ATS.  Any given run contains some of, and maybe all of, the following components:

* An input file: an `.xml` file read by ATS via `ats --xml_file=../my_file.xml` **required**
* A mesh file for non-trivial meshes: typically an `.exo` file.  Most meshes have included a python script or ipython notebook used to generate that mesh, showing that workflow.
* Forcing data: typically an `.h5` file, and often generated from DayMet or other products.  Often a python script or ipython notebook is used to generate these files, and these are included to show that workflow as well.
* A jupyter notebook `.ipynb` which describes, documents, and plots the results from the given run.  Note these can be viewed, including plots, without even running the simulation.  This is where to understand what is being done in each run.

Running the demos
---------------------

Running all of the demos can take some time, but individual demos are often fairly quick.  To run a given demo, make sure `ats` is compiled and (preferably) in your path, and then:

```python run_demos.py path_to_suite.cfg```

or

```python run_demos.py path_to_suite.cfg -t suite_name-test_name```

Note that some individual runs may depend upon results from previous runs in that suite, and so all demos in that suite should be run.  This is particularly true for demos that show a full workflow, such as `ecohydrology` or `arctic_hydrology`.


Visualizing the results
------------------------

Inside each subdirectory is a jupyter notebook.  Jupyter comes fairly standard with most comprehensive python installations.  Anaconda python is the one most ATS developers use, and its default installation includes nearly all python packages used by ATS.


List of problem suites currently tested:
--------------------------------------------

* _richards_steadystate:_ Column of water, solves hydrostatic balance on the column to establish a water table.
* _richards:_ A set of independent runs showing subsurface flow using Richards equation.
* _surface_water:_ A set of independent runs showing surface flow using a diffusion wave approximation.
* _integrated_hydro:_ Runs demonstrating the coupling of surface and subsurface flow.
* _ecohydrology:_ A suite of runs, showing the variety of options for including evaporation and transpiration in runs of integrated hydrology.
* _arctic_hydrology:_ A suite of runs, showing how ecohydrology is typically done in permafrost-rich soils, especially as used in NGEE-Arctic.

