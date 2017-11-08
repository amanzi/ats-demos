#!/bin/env python
"""
Program to manage and run ATS regression tests.

With inspiration, and in some places just stolen, from Ben Andre's
PFloTran regression test suite.

Author: Ethan Coon (ecoon@lanl.gov)
"""

from __future__ import print_function
from __future__ import division

import sys

if sys.hexversion < 0x02070000:
    print(70*"*")
    print("ERROR: The regression test manager requires python >= 2.7.x. ")
    print("It appears that you are running python {0}.{1}.{2}".format(
        sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    print(70*"*")
    sys.exit(1)

import argparse
import datetime
import os
#import pprint
import shutil
import subprocess
import textwrap
import time
import traceback
import distutils.spawn
import numpy

sys.path.append("scripts")
import ats_h5

class NoCatchException(Exception):
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

if sys.version_info[0] == 2:
    from ConfigParser import SafeConfigParser as config_parser
else:
    from configparser import ConfigParser as config_parser


class TestStatus(object):
    """
    Simple class to hold status info.
    """
    def __init__(self):
        self.fail = 0
        self.warning = 0
        self.error = 0
        self.skipped = 0
        self.test_count = 0

    def __str__(self):
        message = "fail = {0}\n".format(self.fail)
        message += "warning = {0}\n".format(self.warning)
        message += "error = {0}\n".format(self.error)
        message += "skipped = {0}\n".format(self.skipped)
        message += "test_count = {0}\n".format(self.test_count)
        return message


class RegressionTest(object):
    """
    Class to collect data about a test problem, run the problem, and
    compare the results to a known result.
    """
    # things to compare
    _TIME = "time"
    _TIMESTEPS = "timesteps"
    _DEFAULT = "default" # compare a variable
    
    # ways to compare it
    _ABSOLUTE = "absolute"
    _RELATIVE = "relative"
    _PERCENT = "percent"
    _DISCRETE = "discrete"

    # ways to measure what to compare
    _NORM = numpy.inf

    def __init__(self):
        self._EXECUTABLE = "ats"
        self._SUCCESS = 0
        self._RESERVED = [self._TIME, self._TIMESTEPS]

        # misc test parameters
        #        self._pprint = pprint.PrettyPrinter(indent=2)
        self._txtwrap = textwrap.TextWrapper(width=78, subsequent_indent=4*" ")
        self._executable = None
        self._input_arg = "--xml_file="
        self._input_suffix = "xml"
        self._np = None
        self._timeout = 162.0
        self._skip_check_gold = False
        self._check_performance = False
        self._num_failed = 0
        self._test_name = None

        # assign default tolerances for different classes of variables
        # absolute min and max thresholds for determining whether to
        # compare to baseline, i.e. if (min_threshold <= abs(value) <=
        # max_threshold) then compare values. By default we use the
        # python definitions for this platform
        self._default_tolerance = {}
        self._default_tolerance[self._TIME] = [5.0, self._PERCENT, \
                                               0.0, sys.float_info.max]
        self._default_tolerance[self._TIMESTEPS] = [5, self._RELATIVE, \
                                                    0, sys.maxsize]
        self._default_tolerance[self._DISCRETE] = [0, self._ABSOLUTE, 0, sys.maxsize]
        
        self._default_tolerance[self._DEFAULT] = [1.0e-12, self._RELATIVE, \
                                                  0.0, sys.float_info.max]
        self._eps = 1.e-14

        self._checkpoint = None
        
        # dictionary indexed by domain, each of which is a dictionary of
        # (key, tolerance) pairs
        self._criteria = {}
        self._file_format_with_domain = "visdump_{0}_data.h5"        
        self._file_format_no_domain = "visdump_data.h5"        

    def __str__(self):
        message = "  {0} :\n".format(self.name())
        message += "    timeout = {0}\n".format(self._timeout)
        message += "    np = {0}\n".format(self._np)
        message += "    ATS args :\n"
        message += "        exec  : {0}\n".format(self._executable)
        message += "        input : {0}../{1}.{2}\n".format(
            self._input_arg,self._test_name,self._input_suffix)
        for domain,criteria in self._criteria.iteritems():
            message += "    test criteria on \"{0}\" :\n".format(domain)
            for key,tol in criteria.iteritems():
                message += "        {0} : {1} [{2}] : {3} <= abs(value) <= {4}\n".format(
                    key, tol[0], tol[1], tol[2], tol[3])
        return message

    def setup(self, cfg_criteria, test_data,
              timeout, check_performance, testlog):
        """
        Setup the test object

        cfg_criteria - dict from cfg file, all tests in file
        test_data - dict from cfg file, test specific
        timeout - list(?) from command line option
        check_performance - bool from command line option
        """
        self._test_name = test_data.pop('name')
        self._np = test_data.pop('np', None)
        self._skip_check_gold = test_data.pop('skip_check_gold', None)
        self._check_performance = check_performance

        # timeout : preference (1) command line (2) test data (3) class default
        self._timeout = float(cfg_criteria.pop('timeout', self._timeout))
        self._timeout = float(test_data.pop('timeout', self._timeout))
        if timeout is not None:
            self._timeout = float(timeout[0])

        # check whether this is a checkpoint
        checkpoint = test_data.pop('checkpoint',
                                   cfg_criteria.pop('checkpoint', None))
        if checkpoint is not None: 
            self._checkpoint = checkpoint
        
        # pop a default and/or default discrete
        default = test_data.pop(self._DEFAULT,
                                cfg_criteria.pop(self._DEFAULT, None))
        if default is not None:
            tol = self._validate_tolerance(self._DEFAULT, self._DEFAULT, default)
            self._default_tolerance[self._DEFAULT] = tol

        discrete = test_data.pop(self._DISCRETE,
                                cfg_criteria.pop(self._DISCRETE, None))
        if discrete is not None:
            tol = self._validate_tolerance(self._DISCRETE, self._DISCRETE, discrete)
            self._default_tolerance[self._DISCRETE] = tol
            
        # requested criteria, skipping time and timesteps
        for key in set(cfg_criteria.keys() + test_data.keys()):
            if key != self._TIME and key != self._TIMESTEPS:
                self._set_criteria(key, cfg_criteria, test_data)

        # criteria defaults
        # - time exists on all domains, but must make sure it is on a valid one
        if self._check_performance:
            self._set_criteria("({0})".format(self._criteria.keys()[0])+self._TIME,
                               cfg_criteria, test_data)

        # - timestep exists on all domains, but must make sure it is on a valid one
        if self._checkpoint is None:
            self._set_criteria("({0})".format(self._criteria.keys()[0])+self._TIMESTEPS,
                               cfg_criteria, test_data)
                
    def name(self):
        return self._test_name

    def dirname(self, gold=False):
        suffix = ".regression"
        if gold:
            suffix += ".gold"
        return self.name() + suffix        

    def filename(self, domain, gold=False):
        if self._checkpoint is not None:
            return os.path.join(self.dirname(gold),
                            self._checkpoint)
        else:
            if domain == "":
                return os.path.join(self.dirname(gold),
                                    self._file_format_no_domain)
            else:
                return os.path.join(self.dirname(gold),
                                    self._file_format_with_domain.format(domain))

    def run(self, mpiexec, executable, dry_run, status, testlog):
        """
        Run the test.
        """
        self._cleanup_generated_files()
        self._run_test(mpiexec, executable, self.name(), dry_run, status,
                       testlog)

    def _run_test(self, mpiexec, executable, test_name, dry_run, status, testlog):
        """
        Build up the run command, including mpiexec, np, ats,
        input file, output file. Then run the job as a subprocess.

        * NOTE(bja) - starting in python 3.3, we can use:

          subprocess.Popen(...).wait(timeout)

          to catch hanging jobs, but for python < 3.3 we have to
          manually manage the timeout...?
        """
        command = []
        if self._np is not None:
            if mpiexec:
                command.append(mpiexec)
                command.append("-np")
                command.append(self._np)
            else:
                # parallel test, but don't have mpiexec, we mark the
                # test as skipped and bail....
                message = self._txtwrap.fill(
                    "WARNING : mpiexec was not provided for a parallel test '{0}'.\n"
                    "This test was skipped!".format(self.name()))
                print(message, file=testlog)
                status.skipped = 1
                return None

        command.append(executable)
        command.append("{0}../{1}.{2}".format(self._input_arg,test_name,self._input_suffix))

        test_directory = os.getcwd()
        run_directory = os.path.join(test_directory, self.dirname())
        os.mkdir(run_directory)
        os.chdir(run_directory)
        
        print("    cd {0}".format(run_directory), file=testlog)
        print("    {0}".format(" ".join(command)), file=testlog)

        if not dry_run:
            run_stdout = open(test_name + ".stdout", 'w')
            start = time.time()
            proc = subprocess.Popen(command,
                                    shell=False,
                                    stdout=run_stdout,
                                    stderr=subprocess.STDOUT)
            while proc.poll() is None:
                time.sleep(0.1)
                if time.time() - start > self._timeout:
                    proc.kill()
                    time.sleep(0.1)
                    message = self._txtwrap.fill(
                        "ERROR: job '{0}' has exceeded timeout limit of "
                        "{1} seconds.".format(test_name, self._timeout))
                    print(''.join(['\n', message, '\n']), file=testlog)
            finish = time.time()
            print("    # {0} : run time : {1:.2f} seconds".format(test_name, finish - start), file=testlog)
            ierr_status = abs(proc.returncode)
            run_stdout.close()

            if ierr_status != self._SUCCESS:
                status.fail = 1
                message = self._txtwrap.fill(
                    "FAIL : {name} : {execute} return an error "
                    "code ({status}) indicating the simulation may have "
                    "failed. Please check '{name}.stdout' "
                    "for error messages (included below).".format(
                        execute=self._EXECUTABLE, name=test_name, status=ierr_status))

                print("".join(['\n', message, '\n']), file=testlog)
                print("~~~~~ {0}.stdout ~~~~~".format(test_name), file=testlog)
                try:
                    with open("{0}.stdout".format(test_name), 'r') as tempfile:
                        shutil.copyfileobj(tempfile, testlog)
                except Exception as e:
                    print("   Error opening file: {0}.stdout\n    {1}".format(test_name, e))
                print("~~~~~~~~~~", file=testlog)

        os.chdir(test_directory)

    def _cleanup_generated_files(self):
        """Cleanup old generated files that may be hanging around from a
        previous run.
        """
        run_dir = self.dirname(False)
        shutil.rmtree(run_dir, ignore_errors=True)


    def check(self, status, testlog):
        """
        Check the test results against the gold standard
        """

        for domain in self._criteria.keys():
            self._check_gold(status, domain, testlog)

    def update(self, status, testlog):
        """
        Update the gold standard test results to the current
        output. Both the current regression output and a gold file
        must exist.
        """
        gold_dir = self.dirname(True)
        run_dir = self.dirname(False)
        old_gold_dir = gold_dir+".old"

        # verify that the gold file exists
        if not os.path.isdir(gold_dir):
            print("ERROR: test '{0}' results cannot be updated "
                  "because a gold directory does not "
                  "exist!".format(self.name()), file=testlog)
            status.error = 1
                
        # verify that the regression directory exists
        if not os.path.isdir(run_dir):
            print("ERROR: test '{0}' results cannot be updated "
                  "because no regression run directory "
                  "exists!".format(self.name()), file=testlog)
            status.error = 1

        # check that the regression file was created in the regression directory
        if (not status.error and not status.fail):
            for domain in self._criteria.keys():
                reg_name = self.filename(domain, False)

                if not os.path.isfile(reg_name):
                    print("ERROR: run for "
                          "test '{0}' did not create the needed regression file "
                          "'{1}', not updating!".format(self.name(),
                                                        reg_name), file=testlog)
                    status.fail = 1

        if not status.error and not status.fail:
            # remove old-old gold
            if os.path.isdir(old_gold_dir):
                try:
                    shutil.rmtree(old_gold_dir)
                except Exception as error:
                    message = str(error)
                    message += "\nFAIL : Could not remove old gold '{0}'. ".format(old_gold_dir)
                    message += "Please remove the directory manually!"
                    message += "    rm -rf {0}".format(old_gold_dir)
                    print(message, file=testlog)
                    status.fail = 1

            # move gold -> old_gold
            if not status.fail:
                try:
                    os.rename(gold_dir, old_gold_dir)
                except Exception as error:
                    message = str(error)
                    message += "\nFAIL : Could not back up gold '{0}' as '{1}'. ".format(
                        gold_dir, old_gold_dir)
                    message += "Please rename or remove the gold directory manually!"
                    message += "    mv {0} {1}".format(gold_dir, old_gold_dir)
                    print(message, file=testlog)
                    status.fail = 1

            if not status.fail:
                # move run -> gold
                try:
                    os.rename(run_dir, gold_dir)
                except Exception as error:
                    message = str(error)
                    message += "\nFAIL : Could not move '{0}' to '{1}'. ".format(
                        run_dir, gold_dir)
                    message += "Please rename the directory manually!"
                    message += "    mv {0} {1}".format(run_dir, gold_dir)
                    print(message, file=testlog)
                    status.fail = 1

        print("done", file=testlog)

    def new_test(self, status, testlog):
        """
        A new test does not have a gold standard regression test. We
        will check to see if a gold standard file exists (an error),
        then create the gold file by copying the current regression
        file to gold.
        """
        gold_dir = self.dirname(True)
        run_dir = self.dirname(False)

        # verify that the gold file does not exisit
        if os.path.isdir(gold_dir) or os.path.isfile(gold_dir):
            print("ERROR: test '{0}' was classified as new, "
                               "but a gold file already "
                               "exists!".format(self.name()), file=testlog)
            status.error = 1

        # verify that the run directory exists
        if not os.path.isdir(run_dir):
            print("ERROR: test '{0}' results cannot be new "
                  "because no run directory "
                  "exists!".format(self.name()), file=testlog)
            status.error = 1
        
        # verify that the run directory created good files
        if (not status.error and not status.fail):
            for domain in self._criteria.keys():
                reg_name = self.filename(domain, False)

                if not os.path.isfile(reg_name):
                    print("ERROR: run for "
                          "test '{0}' did not create the needed regression file "
                          "'{1}', not making new gold!".format(self.name(),
                                                    reg_name), file=testlog)
                    status.fail = 1

        # move the run to gold
        if not status.error and not status.fail:
            print("  creating gold directory '{0}'... ".format(self.name()),
                  file=testlog)
            try:
                os.rename(run_dir, gold_dir)
            except Exception as error:
                message = str(error)
                message += "\nFAIL : Could not move '{0}' to '{1}'. ".format(
                    run_dir, gold_dir)
                message += "Please rename the directory manually!"
                message += "    mv {0} {1}".format(run_dir, gold_dir)
                print(message, file=testlog)
                status.fail = 1

        print("done", file=testlog)


    def _check_gold(self, status, domain, testlog):
        """
        Test the output from the run against the known "gold standard"
        output and determine if the test succeeded or failed.

        We return zero on success, one on failure so that the test
        manager can track how many tests succeeded and failed.
        """
        if self._skip_check_gold:
            message = "    Skipping comparison to regression gold file (only test if model runs to completion)."
            print("".join(['\n', message, '\n']), file=testlog)
            return

        gold_filename = self.filename(domain, True)
        if not os.path.isfile(gold_filename):
            message = self._txtwrap.fill(
                "FAIL: could not find regression test gold file "
                "'{0}'. If this is a new test, please create "
                "it with '--new-test'.".format(gold_filename))
            print("".join(['\n', message, '\n']), file=testlog)
            status.fail = 1
            return

        current_filename = self.filename(domain, False)
        if not os.path.isfile(current_filename):
            message = self._txtwrap.fill(
                "FAIL: could not find regression test file '{0}'."
                " Please check the standard output file for "
                "errors.".format(current_filename))
            print("".join(['\n', message, '\n']), file=testlog)
            status.fail = 1
            return

        try:
            h5_current = ats_h5.File(current_filename)
        except Exception as e:
            print("    FAIL: Could not open file: '{0}'".format(current_filename), file=testlog)
            status.fail = 1
            h5_current = None

        try:
            h5_gold = ats_h5.File(gold_filename)
        except Exception as e:
            print("    FAIL: Could not open file: '{0}'".format(gold_filename), file=testlog)
            status.fail = 1
            h5_gold = None

        if h5_gold is not None and h5_current is not None:
            self._compare(h5_current, h5_gold, domain, status, testlog)

        h5_gold.close()
        h5_current.close()
        
    def _compare(self, h5_current, h5_gold, domain, status, testlog):
        """Check that output hdf5 file has not changed from the baseline.
        """
        for key, tolerance in self._criteria[domain].iteritems():
            if key == self._TIME:
                self._compare_time(h5_current, h5_gold, tolerance,
                                   status, testlog)
            elif key == self._TIMESTEPS:
                self._compare_timesteps(h5_current, h5_gold, tolerance,
                                        status, testlog)
            else:
                self._compare_values(h5_current, h5_gold, key, tolerance,
                                     status, testlog)
        if status.fail == 0:
            print("    Passed tests.", file=testlog)

    def _compare_time(self, h5_current, h5_gold, tolerance, status, testlog):
        self._check_tolerance(h5_current.simulationTime(), h5_gold.simulationTime(),
                              self._TIME, tolerance, status, testlog)

    def _compare_timesteps(self, h5_current, h5_gold, tolerance, status, testlog):
        self._check_tolerance(h5_current.numSteps(), h5_gold.numSteps(),
                              self._TIMESTEPS, tolerance, status, testlog)

    def _compare_values(self, h5_current, h5_gold, key, tolerance, status, testlog):
        if len(set(h5_current.matches(key))) != len(set(h5_gold.matches(key))):
            status.fail = 1
            print("    FAIL: {0} : {1} :".format(self.name(), key), file=testlog)
            print("        gold matches: {0}".format(";".join(h5_gold.matches(key))),
                  file=testlog)
            print("        current matches: {0}".format(";".join(h5_current.matches(key))),
                  file=testlog)
            
        elif (len(h5_gold.matches(key)) == 0):
            status.fail = 1
            print("    FAIL: Could not find gold variable match for: '{0}'".format(key), file=testlog)

        else:
            if self._checkpoint is not None:
                for k1,k2 in zip(h5_gold.matches(key),h5_current.matches(key)):
                    self._check_tolerance(h5_current[k2][:], h5_gold[k1][:],
                                          k2, tolerance, status, testlog)
            else:
                for k1,k2 in zip(h5_gold.matches(key),h5_current.matches(key)):
                    for i_current, i_gold in zip(h5_current.steps(), h5_gold.steps()):
                        key_with_index = "{0} [{1}]".format(k1, i_gold)
                        self._check_tolerance(h5_current[k2][i_current][:],
                                              h5_gold[k1][i_gold][:],
                                              key_with_index, tolerance,
                                              status, testlog)

    def _norm(self, diff):
        """
        Determine the difference between two values
        """
        if type(diff) is numpy.ndarray:
            delta = numpy.linalg.norm(diff.flatten(), self._NORM)
        else:
            delta = abs(diff)
        return delta
                
    def _check_tolerance(self, current, gold, key, tolerance, status, testlog):
        """
        Compare the values using the appropriate tolerance and criteria.
        """
        my_status = 0

        # unpack the tolerance
        tol, tol_type, min_threshold, max_threshold = tuple(tolerance)

        if tol_type == self._ABSOLUTE:
            delta = self._norm(current-gold)

        elif (tol_type == self._RELATIVE or
              tol_type == self._PERCENT):

            if type(gold) is numpy.ndarray:
                rel_to = numpy.where(gold > self._eps, gold, current)
                filter = numpy.where(rel_to > self._eps)[0]            
                if filter.shape[0] == 0:
                    delta = 0
                else:
                    delta = self._norm((gold[filter] - current[filter]) / rel_to[filter])

            else:
                if gold > self._eps:
                    delta = self._norm((gold - current) / gold)
                elif current > self._eps:
                    delta = self._norm((gold - current) / current)
                else:
                    delta = 0
                
            if tol_type == self._PERCENT:
                delta *= 100.0
        else:
            # should never get here....
            raise RuntimeError("ERROR: unknown test tolerance_type '{0}' for "
                               "variable '{1}, {2}.'".format(tol_type,
                                                          self.name(), key))

        if delta > tol:
            status.fail = 1
            print("    FAIL: {0} : {1} : {2} > {3} [{4}]".format(
                    self.name(), key, delta, tol, tol_type), file=testlog)
        else:
            print("    PASS: {0} : {1} : {2} <= {3} [{4}]".format(
                self.name(), key, delta, tol, tol_type), file=testlog)
        return

    def _set_criteria(self, key, cfg_criteria, test_data):
        """
        Our preferred order for selecting test criteria is:
        (1) test data section of the config file
        (2) config-file wide defaults
        (3) hard coded class default
        """
        # strip the domain prefix
        if key.startswith("("):
            domain,varname = key[1:].split(")")
        elif "-" in key:
            domain = key.split("-")[0]
            varname = key            
        else:
            domain = ""
            varname = key

        # parse the criteria
        if key in test_data:
            criteria = domain, varname, self._validate_tolerance(key, varname, test_data[key])
        elif key in cfg_criteria:
            criteria = domain, varname, self._validate_tolerance(key, varname, cfg_criteria[key])
        elif varname == self._TIME:
            criteria = domain, self._TIME, self._default_tolerance[self._TIME]
        elif varname == self._TIMESTEPS:
            criteria = domain, self._TIMESTEPS, self._default_tolerance[self._TIMESTEPS]
        else:
            criteria = domain, varname, self._default_tolerance[self._DEFAULT]

        if criteria is not None:
            domain,varname,tol = criteria
            if tol is not None:
                domain_dict = self._criteria.setdefault(domain,dict())
                domain_dict[varname] = tol

    def _validate_tolerance(self, key, varname, test_data):
        """
        Validate the tolerance string from a config file.

        Valid input configurations are:
        
        * (domain)varname = 
        * (domain)varname = default
        * (domain)varname = no
        * (domain)varname = tolerance type
        * (domain)varname = tolerance type [, min_threshold value] [, max_threshold value]

        where the first two use defaults, the third turns the test
        off, and the last two specify the tolerance explicitly, where
        min_threshold and max_threshold are optional

        """
        # deal with defaults first
        if test_data.lower() == "none" or test_data.lower() == "no" or test_data.lower() == "n":
            return None
        if test_data == "" or test_data.lower() == self._DEFAULT:
            return self._default_tolerance[self._DEFAULT]
        if test_data == self._DISCRETE:
            return self._default_tolerance[self._DISCRETE]

        # if we get here, parse the string
        criteria = 4*[None]
        test_data = test_data.split(",")
        test_criteria = test_data[0]
        value = test_criteria.split()[0]

        try:
            value = float(value)
        except Exception:
            raise RuntimeError("ERROR : Could not convert '{0}' test criteria "
                               "value '{1}' into a float!".format(key, value))
        criteria[0] = value

        criteria_type = test_criteria.split()[1]
        if (criteria_type.lower() != self._PERCENT and
            criteria_type.lower() != self._ABSOLUTE and
                criteria_type.lower() != self._RELATIVE):
            raise RuntimeError("ERROR : invalid test criteria string '{0}' "
                               "for '{1}'".format(criteria_type, key))
        criteria[1] = criteria_type

        thresholds = {}
        for t in range(1, len(test_data)):
            name = test_data[t].split()[0].strip()
            value = test_data[t].split()[1].strip()
            try:
                value = float(value)
            except Exception:
                raise RuntimeError(
                    "ERROR : Could not convert '{0}' test threshold '{1}'"
                    "value '{2}' into a float!".format(key, name, value))
            thresholds[name] = value
        value = thresholds.pop("min_threshold", None)
        criteria[2] = value
        value = thresholds.pop("max_threshold", None)
        criteria[3] = value
        if len(thresholds) > 0:
            raise RuntimeError("ERROR: test {0} : unknown criteria threshold: {1}",
                               key, thresholds)
        
        return criteria


            
class RegressionTestManager(object):
    """
    Class to open a configuration file, process it into a group of
    tests, and manage running the tests.

    Notes:

        * The ConfigParser class converts all section names and key
          names into lower case. This means we need to preprocess user
          input names to lower case.

    """

    def __init__(self):
        self._debug = False
        self._file_status = TestStatus()
        self._config_filename = None
        self._default_test_criteria = {}
        self._available_tests = {}
        self._available_suites = {}
        self._tests = []
        self._txtwrap = textwrap.TextWrapper(width=78, subsequent_indent=4*" ")
        #        self._pprint = pprint.PrettyPrinter(indent=2)

    def __str__(self):
        data = "Regression Test Manager :\n"
        data += "    configuration file : {0}\n".format(self._config_filename)
        data += "    default test criteria :\n"
        data += self._dict_to_string(self._default_test_criteria)
        data += "    suites :\n"
        data += self._dict_to_string(self._available_suites)
        data += "    available tests :\n"
        data += self._dict_to_string(self._available_tests)

        data += "Tests :\n"
        for test in self._tests:
            data += test.__str__()

        return data

    def debug(self, debug):
        self._debug = debug

    def num_tests(self):
        return len(self._tests)

    def generate_tests(self, config_file, user_suites, user_tests,
                       timeout, check_performance, testlog):
        """
        Read the config file, validate the input and generate the test objects.
        """
        self._read_config_file(config_file)
        self._validate_suites()
        user_suites, user_tests = self._validate_user_lists(user_suites,
                                                            user_tests, testlog)
        self._create_tests(user_suites, user_tests, timeout, check_performance,
                           testlog)

    def run_tests(self, mpiexec, executable,
                  dry_run, update, new_test, check_only, testlog):
        """
        Run the tests specified in the config file.

        * dry_run - flag indicates that the test is setup then print
          the command that would be used, but don't actually run
          anything or compare results.

        * new_test - flag indicates that the test is a new test, and
          there should not be a gold standard regression file
          present. Run the executable and create the gold file.

        * update - flag indicates that the output from ats has
          changed, and we want to update the gold standard regression
          file to reflect this. Run the executable and replace the
          gold file.

        * check_only - flag to indicate just diffing the existing
          regression files without rerunning ats.
        """
        if self.num_tests() > 0:
            if new_test:
                self._run_new(mpiexec, executable, dry_run, testlog)
            elif update:
                self._run_update(mpiexec, executable, dry_run, testlog)
            elif check_only:
                self._check_only(dry_run, testlog)
            else:
                self._run_check(mpiexec, executable, dry_run, testlog)
        else:
            self._file_status.test_count = 0

    def _run_check(self, mpiexec, executable, dry_run, testlog):
        """
        Run the test and check the results.
        """
        if dry_run:
            print("Dry run:")
        print("Running tests from '{0}':".format(self._config_filename), file=testlog)
        print(50 * '-', file=testlog)

        for test in self._tests:
            status = TestStatus()
            self._test_header(test.name(), testlog)

            test.run(mpiexec, executable, dry_run, status, testlog)

            if not dry_run and status.skipped == 0:
                test.check(status, testlog)

            self._add_to_file_status(status)

            self._test_summary(test.name(), status, dry_run,
                               "passed", "failed", testlog)

        self._print_file_summary(dry_run, "passed", "failed", testlog)

    def _check_only(self, dry_run, testlog):
        """
        Recheck the regression files from a previous run.
        """
        if dry_run:
            print("Dry run:")
        print("Checking existing test results from '{0}':".format(
            self._config_filename), file=testlog)
        print(50 * '-', file=testlog)

        for test in self._tests:
            status = TestStatus()
            self._test_header(test.name(), testlog)

            if not dry_run and status.skipped == 0:
                test.check(status, testlog)

            self._add_to_file_status(status)

            self._test_summary(test.name(), status, dry_run,
                               "passed", "failed", testlog)

        self._print_file_summary(dry_run, "passed", "failed", testlog)

    def _run_new(self, mpiexec, executable, dry_run, testlog):
        """
        Run the tests and create new gold files.
        """
        if dry_run:
            print("Dry run:")

        print("New tests from '{0}':".format(self._config_filename), file=testlog)
        print(50 * '-', file=testlog)

        for test in self._tests:
            status = TestStatus()
            self._test_header(test.name(), testlog)
	    
            test.run(mpiexec, executable, dry_run, status, testlog)

            if not dry_run and status.skipped == 0:
                test.new_test(status, testlog)
            self._add_to_file_status(status)
            self._test_summary(test.name(), status, dry_run,
                               "created", "error creating new test files.", testlog)

        self._print_file_summary(dry_run, "created", "could not be created", testlog)

    def _run_update(self, mpiexec, executable, dry_run, testlog):
        """
        Run the tests and update the gold file with the current output
        """
        if dry_run:
            print("Dry run:")
        print("Updating tests from '{0}':".format(self._config_filename), file=testlog)
        print(50 * '-', file=testlog)

        for test in self._tests:
            status = TestStatus()
            self._test_header(test.name(), testlog)
            test.run(mpiexec, executable, dry_run, status, testlog)

            if not dry_run and status.skipped == 0:
                test.update(status, testlog)
            self._add_to_file_status(status)
            self._test_summary(test.name(), status, dry_run,
                               "updated", "error updating test.", testlog)

        self._print_file_summary(dry_run, "updated", "could not be updated", testlog)

    def _test_header(self, name, testlog):
        """
        Write a header to the log file to separate tests.
        """
        print(40 * '-', file=testlog)
        print("{0}... ".format(name), file=testlog)

    def _test_summary(self, name, status, dry_run,
                      success_message, fail_message, testlog):
        """
        Write the test status information to stdout and the test log.
        """
        if dry_run:
            print("D", end='', file=sys.stdout)
            print(" dry run.", file=testlog)
        else:
            if (status.fail == 0 and
                    status.warning == 0 and
                    status.error == 0 and
                    status.skipped == 0):
                print(".", end='', file=sys.stdout)
                print("{0}... {1}.".format(name, success_message), file=testlog)
            elif status.fail != 0:
                print("F", end='', file=sys.stdout)
                print("{0}... {1}.".format(name, fail_message), file=testlog)
            elif status.warning != 0:
                print("W", end='', file=sys.stdout)
            elif status.error != 0:
                print("E", end='', file=sys.stdout)
            elif status.skipped != 0:
                print("S", end='', file=sys.stdout)
                print("{0}... skipped.".format(name), file=testlog)
            else:
                print("?", end='', file=sys.stdout)

        sys.stdout.flush()

    def _print_file_summary(self, dry_run, success_message, fail_message, testlog):
        """
        Print a summary of the results for this config file
        """
        print("", file=sys.stdout)
        print(50 * '-', file=testlog)
        if dry_run:
            print("{0} : dry run.".format(self._config_filename), file=testlog)
        elif self._file_status.test_count == 0:
            print("{0} : no tests run.".format(self._config_filename), file=testlog)
        else:
            line = "{0} : {1} tests : ".format(self._config_filename,
                                               self._file_status.test_count)
            if self._file_status.fail > 0:
                line = "{0} {1} tests {2}, ".format(
                    line, self._file_status.fail, fail_message)
            if self._file_status.skipped > 0:
                line = "{0} {1} tests {2}, ".format(
                    line, self._file_status.skipped, "skipped")
            num_passed = (self._file_status.test_count -
                          self._file_status.fail - self._file_status.skipped)
            line = "{0} {1} tests {2}".format(line, num_passed, success_message)
            print(line, file=testlog)

    def _add_to_file_status(self, status):
        """
        Add the current test status to the overall status for the file.
        """
        self._file_status.fail += status.fail
        self._file_status.warning += status.warning
        self._file_status.error += status.error
        self._file_status.skipped += status.skipped
        self._file_status.test_count += 1

    def run_status(self):
        return self._file_status

    def display_available_tests(self):
        print("Available tests: ")
        for test in sorted(self._available_tests.keys()):
            print("    {0}".format(test))

    def display_available_suites(self):
        print("Available test suites: ")
        for suite in self._available_suites:
            print("    {0} :".format(suite))
            for test in self._available_suites[suite].split():
                print("        {0}".format(test))

    def _read_config_file(self, config_file):
        """
        Read the configuration file.

        Sections : The config file will have known sections:
        "suites", "default-test-criteria".

        All other sections are assumed to be test names.
        """
        if config_file is None:
            raise RuntimeError("Error, must provide a config filename")
        self._config_filename = config_file
        config = config_parser()
        config.read(self._config_filename)

        if config.has_section("default-test-criteria"):
            self._default_test_criteria = \
                self._list_to_dict(config.items("default-test-criteria"))

        if config.has_section("suites"):
            self._available_suites = \
                self._list_to_dict(config.items("suites"))

        self._identify_tests(config)

    def _identify_tests(self, config):
        """
        Create a list of all tests in a config file.

        Assumes every section is a test except for some fixed section
        names

        """
        # section names are test names
        test_names = config.sections()

        # remove the fixed section names
        if config.has_section("default-test-criteria"):
            test_names.remove("default-test-criteria")
        if config.has_section("suites"):
            test_names.remove("suites")

        # all remaining sections should be individual tests
        for test in test_names:
            self._available_tests[test] = self._list_to_dict(config.items(test))
            self._available_tests[test]['name'] = test

    def _dict_to_string(self, data):
        """
        Format dictionary key-value pairs in a string
        """
        temp = ""
        for key, value in data.items():
            temp += "        {0} : {1}\n".format(key, value)
        return temp

    def _list_to_dict(self, input_list):
        """
        Convert a list of key-value pairs into a dictionary.
        """
        output_dict = {}
        for item in input_list:
            output_dict[item[0]] = item[1]
        return output_dict

    def _validate_suites(self):
        """
        Validates the suites defined in configuration file by
        checking that each test in a suite is one of the available
        tests.

        If the config file has an empty suite, we report that to the
        user then remove it from the list.
        """
        invalid_tests = []
        empty_suites = []
        for suite in self._available_suites:
            suite_tests = self._available_suites[suite].split()
            if len(suite_tests) == 0:
                empty_suites.append(suite)
            else:
                # validate the list
                for test in suite_tests:
                    if test not in self._available_tests:
                        name = "suite : '{0}' --> test : '{1}'".format(
                            suite, test)
                        invalid_tests.append(name)

        for suite in empty_suites:
            # empty suite, warn the user and remove it from the list
            del self._available_suites[suite]
            print("DEV WARNING : {0} : cfg validation : empty suite "
                  ": '{1}'".format(self._config_filename, suite))

        if len(invalid_tests) != 0:
            raise RuntimeError("ERROR : suites contain unknown tests in "
                               "configuration file '{0}' : {1}".format(
                                   self._config_filename, invalid_tests))

    def _validate_user_lists(self, user_suites, user_tests, testlog):
        """
        Check that the list of suites or tests passed from the command
        line are valid.
        """
        # if no suites or tests is specified, use all available tests
        if len(user_suites) == 0 and len(user_tests) == 0:
            u_suites = []
            u_tests = self._available_tests
        else:
            # check that the processed user supplied names are valid
            # convert user supplied names to lower case
            u_suites = []
            for suite in user_suites:
                if suite.lower() in self._available_suites:
                    u_suites.append(suite.lower())
                else:
                    message = self._txtwrap.fill(
                        "WARNING : {0} : Skipping requested suite '{1}' (not "
                        "present, misspelled or empty).".format(
                            self._config_filename, suite))
                    print(message, file=testlog)

            u_tests = []
            for test in user_tests:
                if test in self._available_tests:
                    u_tests.append(test.lower())
                else:
                    message = self._txtwrap.fill(
                        "WARNING : {0} : Skipping test '{1}' (not present or "
                        "misspelled).".format(self._config_filename, test))
                    print(message, file=testlog)

        return u_suites, u_tests

    def _create_tests(self, user_suites, user_tests, timeout, check_performance,
                      testlog):
        """
        Create the test objects for all user specified suites and tests.
        """
        all_tests = user_tests
        for suite in user_suites:
            for test in self._available_suites[suite].split():
                all_tests.append(test)

        for test in all_tests:
            try:
                new_test = RegressionTest()
                criteria = self._default_test_criteria.copy()
                new_test.setup(criteria,
                               self._available_tests[test], timeout,
                               check_performance, testlog)
                self._tests.append(new_test)
            except Exception as error:
                raise RuntimeError("ERROR : could not create test '{0}' from "
                                   "config file '{1}'. {2}".format(
                                       test, self._config_filename, str(error)))


def commandline_options():
    """
    Process the command line arguments and return them as a dict.
    """
    parser = argparse.ArgumentParser(description='Run an ATS regression '
                                     'tests or suite of tests.')

    parser.add_argument('--backtrace', action='store_true',
                        help='show exception backtraces as extra debugging '
                        'output')

    parser.add_argument('--check-only', action='store_true', default=False,
                        help="diff the existing regression files without "
                        "running ATS again.")

    parser.add_argument('--check-performance', action='store_true', default=False,
                        help="include the performance metrics ('SOLUTION' blocks) "
                        "in regression checks.")

    parser.add_argument('--debug', action='store_true',
                        help='extra debugging output')

    parser.add_argument('-d', '--dry-run',
                        default=False, action='store_true',
                        help='perform a dry run, setup the test commands but '
                        'don\'t run them')

    parser.add_argument('-e', '--executable', nargs=1, default=None,
                        help='path to executable to use for testing')

    parser.add_argument('--list-suites', default=False, action='store_true',
                        help='print the list of test suites from the config '
                        'file and exit')

    parser.add_argument('--list-tests', default=False, action='store_true',
                        help='print the list of tests from the config file '
                        'and exit')

    parser.add_argument('-m', '--mpiexec', nargs=1, default=None,
                        help="path to the executable for mpiexec (mpirun, etc)"
                        "on the current machine.")

    parser.add_argument('-n', '--new-tests',
                        action="store_true", default=False,
                        help="indicate that there are new tests being run. "
                        "Skips the output check and creates a new gold file.")

    parser.add_argument('-s', '--suites', nargs="+", default=[],
                        help='space separated list of test suite names')

    parser.add_argument('-t', '--tests', nargs="+", default=[],
                        help='space separated list of test names')

    parser.add_argument('--timeout', nargs=1, default=None,
                        help="test timeout (for assuming a job has hung and "
                        "needs to be killed)")

    parser.add_argument('-u', '--update',
                        action="store_true", default=False,
                        help='update the tests listed by the "--tests" '
                        'option, with the current output becoming the new '
                        'gold standard')

    parser.add_argument('configs', metavar='CONFIG_LOCATION', type=str,
                        nargs='+', help='list of directories and/or configuration '
                        'files to parse for suites and tests')
    
    options = parser.parse_args()
    return options


def config_list_includes_search(options):
    """
    Check if there are any directories in the config list.
    """
    for f in options.configs:
        if (os.path.isdir(f)):
            return True
    return False

def generate_config_file_list(options):
    """
    Try to generate a list of configuration files from the commandline
    options.
    """
    config_file_list = []
    # loop through the list, adding files and searching through directories
    for f in options.configs:
        if not os.path.isabs(f):
            f = os.path.abspath(f)

        if os.path.isfile(f):
            config_file_list.append(f)
        elif os.path.isdir(f):
            search_for_config_files(f, config_file_list)
        else:
            raise RuntimeError("ERROR: specified config file/search "
                               "directory '{0}' does not "
                               "exist!".format(f))

    if options.debug:
        print("\nFound config files:")
        for config_file in config_file_list:
            print("    {0}".format(config_file))

    if len(config_file_list) == 0:
        raise RuntimeError("ERROR: no config files were found. Please specify a "
                           "config file or search directory containing config files.")

    return config_file_list


def search_for_config_files(base_dir, config_file_list):
    """
    recursively search the directory tree, creating a list of all config files
    """
    for root, dirnames, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith(".cfg") and os.path.isfile(os.path.join(root, filename)):
                config_file_list.append(os.path.join(root, filename))

def check_options(options):
    """
    Run some sanity checks on the commandline options.
    """
    # prevent the user from updating regression output during a
    # recursive search for config files
    if options.update and config_list_includes_search(options):
        raise RuntimeError("ERROR: cannot update gold regression files "
                           "during a recursive search for config files.")

    if options.update and options.new_tests:
        raise RuntimeError("ERROR: cannot create new tests and update gold "
                           "regression files at the same time.")


def check_for_executable(options, testlog):
    """
    Try to verify that we have something reasonable for the executable
    """
    # check the executable
    if options.executable is None:
        # try to detect from env
        try:
            executable = distutils.spawn.find_executable("ats")
        except Exception:
            executable = None
        finally:
            if executable is None:
                options.dry_run = True

    else:
        # absolute path to the executable
        executable = os.path.abspath(options.executable[0])
        # is it a valid file?
        if not os.path.isfile(executable):
            raise RuntimeError("ERROR: executable is not a valid file: "
                               "'{0}'".format(executable))

    if executable is None:
        message = ("\n** WARNING ** : ATS executable was not provided on the command line\n"
                   "               and was not found in the PATH.  Will run as 'dry run.'\n")
        print(message, file=sys.stdout)
        print(message, file=testlog)
        executable = "/usr/bin/false"
        
    return executable


def check_for_mpiexec(options, testlog):
    """
    Try to verify that we have something reasonable for the mpiexec executable

    Notes:

    geh: need to add code to determine full path of mpiexec if not specified

    bja: the problem is that we don't know how to get the correct
    mpiexec. On the mac, there is a system mpiexe that shows up in the
    path, but this is provided by apple and it is not the correct one
    to use because it doesn't include a fortran compiler. We need the
    exact mpiexec/mpirun that was used to compile petsc, which may
    come from a system installed package in /usr/bin or /opt/local/bin
    or maybe petsc compiled it. This is best handled outside the test
    manager, e.g. use make to identify mpiexec from the petsc
    variables
    """

    # check for mpiexec
    mpiexec = None
    if options.mpiexec is not None:
        # mpiexec = os.path.abspath(options.mpiexec[0])
        mpiexec = options.mpiexec[0]
        # try to log some info about mpiexec
        print("MPI information :", file=testlog)
        print("-----------------", file=testlog)
        tempfile = "{0}/tmp-ats-regression-test-mpi-info.txt".format(os.getcwd())
        command = [mpiexec, "--version"]
        append_command_to_log(command, testlog, tempfile)
        print("\n\n", file=testlog)
    else:
        message = ("\n** WARNING ** : mpiexec was not provided on the command line.\n"
                   "                All parallel tests will be skipped!\n")
        print(message, file=sys.stdout)
        print(message, file=testlog)

    return mpiexec


def summary_report_by_file(report, outfile):
    """
    Summarize the results for each config file.
    """
    print(70 * '-', file=outfile)
    print("Regression test file summary:", file=outfile)
    for filename in report:
        line = "    {0}... {1} tests : ".format(filename, report[filename].test_count)
        if report[filename].warning > 0:
            line = "{0} {1} test warnings, ".format(line, report[filename].warning)
        if report[filename].error > 0:
            line = "{0} {1} test errors, ".format(line, report[filename].error)

        if report[filename].test_count == 0:
            line = "{0}... no tests were run.".format(line)
        else:
            if report[filename].fail > 0:
                line = "{0} {1} tests failed, ".format(line, report[filename].fail)
            if report[filename].skipped > 0:
                line = "{0} {1} tests skipped, ".format(line, report[filename].skipped)
            if report[filename].fail == 0 and report[filename].skipped == 0:
                line = "{0} all tests passed".format(line)
            else:
                num_passed = (report[filename].test_count - report[filename].fail -
                              report[filename].skipped)
                line = "{0} {1} passed.".format(line, num_passed)

        print("{0}".format(line), file=outfile)

    print("\n", file=outfile)


def summary_report(run_time, report, outfile):
    """
    Overall summary of test results
    """
    print(70 * '-', file=outfile)
    print("Regression test summary:", file=outfile)
    print("    Total run time: {0:4g} [s]".format(run_time), file=outfile)
    test_count = 0
    num_failures = 0
    num_errors = 0
    num_warnings = 0
    num_skipped = 0
    for filename in report:
        test_count += report[filename].test_count
        num_failures += report[filename].fail
        num_errors += report[filename].error
        num_warnings += report[filename].warning
        num_skipped += report[filename].skipped

    print("    Total tests : {0}".format(test_count), file=outfile)

    if num_skipped > 0:
        print("    Skipped : {0}".format(num_skipped), file=outfile)
        success = False

    print("    Tests run : {0}".format(test_count - num_skipped), file=outfile)

    success = True
    if num_failures > 0:
        print("    Failed : {0}".format(num_failures), file=outfile)
        success = False

    if num_errors > 0:
        print("    Errors : {0}".format(num_errors), file=outfile)
        success = False

    if num_warnings > 0:
        print("    Warnings : {0}".format(num_warnings), file=outfile)
        success = False

    if success:
        print("    All tests passed.", file=outfile)

    print("\n", file=outfile)
    return num_failures


def append_command_to_log(command, testlog, tempfile):
    """
    Append the results of a shell command to the test log
    """
    print("$ {0}".format(" ".join(command)), file=testlog)
    testlog.flush()
    with open(tempfile, "w") as tempinfo:
        subprocess.call(command, shell=False,
                        stdout=tempinfo,
                        stderr=subprocess.STDOUT)
        # NOTE(bja) 2013-06 : need a short sleep to ensure the
        # contents get written...?
        time.sleep(0.01)
    with open(tempfile, 'r') as tempinfo:
        shutil.copyfileobj(tempinfo, testlog)
    os.remove(tempfile)    

def setup_testlog(txtwrap):
    """
    Create the test log and try to add some useful information about
    the environment.
    """
    now = datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join("LOGS", "ats-tests-{0}.testlog".format(now))
    testlog = open(filename, 'w')
    print("  Test log file : {0}".format(filename))

    print("ATS Regression Test Log", file=testlog)
    print("Date : {0}".format(now), file=testlog)
    print("System Info :", file=testlog)
    print("    platform : {0}".format(sys.platform), file=testlog)
    test_dir = os.getcwd()
    print("Test directory : ", file=testlog)
    print("    {0}".format(test_dir), file=testlog)

    if os.environ.has_key("ATS_SRC_DIR"):
        tempfile = "{0}/tmp-ats-regression-test-hg-info.txt".format(test_dir)

        print("\nATS repository status :", file=testlog)
        print("----------------------------", file=testlog)
        if os.path.isdir("{0}/.hg".format(os.environ["ATS_SRC_DIR"])):
            cmd = ["hg", "parent"]
            append_command_to_log(cmd, testlog, tempfile)
            cmd = ["hg", "status", "-q"]
            append_command_to_log(cmd, testlog, tempfile)
            print("\n\n", file=testlog)
        else:
            print("    unknown", file=testlog)

    return testlog


def main(options):
    txtwrap = textwrap.TextWrapper(width=78, subsequent_indent=4*" ")
    testlog = setup_testlog(txtwrap)

    root_dir = os.getcwd()

    check_options(options)
    executable = check_for_executable(options, testlog)
    mpiexec = check_for_mpiexec(options, testlog)
    config_file_list = generate_config_file_list(options)

    print("Running ATS regression tests :")

    # loop through config files, cd into the appropriate directory,
    # read the appropriate config file and run the various tests.
    start = time.time()
    report = {}
    for config_file in config_file_list:
        # try:
            # NOTE(bja): the try block is inside this loop so that if
            # a single test throws an exception in a large batch of
            # tests, we can recover and at least try running the other
            # config files.
            print(80 * '=', file=testlog)

            # get the absolute path of the directory
            test_dir = os.path.dirname(config_file)
            # cd into the test directory so that the relative paths in
            # test files are correct
            os.chdir(test_dir)
            if options.debug:
                print("Changed to working directory: {0}".format(test_dir))

            test_manager = RegressionTestManager()

            if options.debug:
                test_manager.debug(True)

            # get the relative file name
            filename = os.path.basename(config_file)

            test_manager.generate_tests(filename,
                                        options.suites,
                                        options.tests,
                                        options.timeout,
                                        options.check_performance,
                                        testlog)

            if options.debug:
                print(70 * '-')
                print(test_manager)

            if options.list_suites:
                test_manager.display_available_suites()

            if options.list_tests:
                test_manager.display_available_tests()

            test_manager.run_tests(mpiexec,
                                   executable,
                                   options.dry_run,
                                   options.update,
                                   options.new_tests,
                                   options.check_only,
                                   testlog)

            report[filename] = test_manager.run_status()
            os.chdir(root_dir)
        # except Exception as error:
        #     message = txtwrap.fill(
        #         "ERROR: a problem occured in file '{0}'.  This is "
        #         "probably an error with commandline options, the "
        #         "configuration file, or an internal error.  The "
        #         "error is:\n{1}".format(config_file, str(error)))
        #     print(''.join(['\n', message, '\n']), file=testlog)
        #     if options.backtrace:
        #         traceback.print_exc()
        #     print('F', end='', file=sys.stdout)
        #     report[filename] = TestStatus()
        #     report[filename].fail = 1

            
    stop = time.time()
    status = 0
    if not options.dry_run and not options.update:
        print("")
        run_time = stop - start
        summary_report_by_file(report, testlog)
        summary_report(run_time, report, testlog)
        status = summary_report(run_time, report, sys.stdout)

    if options.update:
        message = txtwrap.fill(
            "Test results were updated! Please document why you modified the "
            "gold standard test results in your revision control commit message!\n")
        print(''.join(['\n', message, '\n']))

    testlog.close()

    return status

if __name__ == "__main__":
    cmdl_options = commandline_options()
    #    try:
    suite_status = main(cmdl_options)
    #sys.exit(suite_status)
    # except Exception as error:
    #     print(str(error))
    #     if cmdl_options.backtrace:
    #         traceback.print_exc()
    #     sys.exit(1)

