#!/bin/env python
"""
Program to manage and run ATS demo problems.

With inspiration, and in some places just stolen, from Ben Andre's
PFloTran regression test suite.

Author: Ethan Coon (ecoon@lanl.gov)
"""
from __future__ import print_function

import sys,os
import argparse
import textwrap
import time

try:
    import test_manager
except ImportError:
    sys.path.append(os.path.join(os.environ['ATS_SRC_DIR'], 'tools', 'testing'))
    import test_manager

def commandline_options(args=None):
    """
    Process the command line arguments and return them as a dict.
    """
    parser = argparse.ArgumentParser(description='Run an collection of ATS demo problems.')

    parser.add_argument('--ats', default=None,
                        help='Path to ATS source directory')
    
    parser.add_argument('--backtrace', action='store_true',
                        help='show exception backtraces as extra debugging '
                        'output')

    parser.add_argument('--debug', action='store_true',
                        help='extra debugging output')

    parser.add_argument('-d', '--dry-run',
                        default=False, action='store_true',
                        help='perform a dry run, setup the test commands but '
                        'don\'t run them')

    parser.add_argument('-e', '--executable', default=None,
                        help='path to executable to use for testing')

    parser.add_argument('--list-available-suites', default=False, action='store_true',
                        help='print the list of test suites from the config '
                        'file and exit')

    parser.add_argument('--list-available-tests', default=False, action='store_true',
                        help='print the list of tests from the config file '
                        'and exit')

    parser.add_argument('--list-tests', default=False, action='store_true',
                        help='print the list of selected tests from the config '
                        'file and exit')

    parser.add_argument('-m', '--mpiexec', default=None,
                        help="path to the executable for mpiexec (mpirun, etc)"
                        "on the current machine.")

    parser.add_argument('--mpiexec-global-args', default=None,
                        help="arguments that must be provided to mpiexec executable")

    parser.add_argument('--mpiexec-numprocs-flag', default='-n',
                        help="mpiexec flag to set number of MPI ranks")

    parser.add_argument('--always-mpiexec', default=False, action='store_true',
                        help="use mpiexec to launch all tests")

    parser.add_argument('-r', '--rerun-failed', default=None, nargs='?', const=True,
                        help="Rerun only failed tests from a previous logfile.  If "
                        "a value is provided, it is the path to the logfile.  If no "
                        "value is provided, will search for the last logfile. "
                        "Note that a config file (or '.') must still be provided -- "
                        "only failed tests in the provided config files will be run.")

    parser.add_argument('-s', '--suites', nargs="+", default=[],
                        help='space separated list of test suite names')

    parser.add_argument('-t', '--tests', nargs="+", default=[],
                        help='space separated list of test names')

    parser.add_argument('--exclude', nargs="+", default=[],
                        help='space separated list of test names to exclude')

    parser.add_argument('--timeout', nargs=1, default=None,
                        help="test timeout (for assuming a job has hung and "
                        "needs to be killed)")

    parser.add_argument('configs', metavar='CONFIG_LOCATION', type=str,
                        nargs='+', help='list of directories and/or configuration '
                        'files to parse for suites and tests')
    
    options = parser.parse_args(args)
    return options


def main(options):
    txtwrap = textwrap.TextWrapper(width=78, subsequent_indent=4*" ")
    root_dir = os.getcwd()

    # find and import test_manager
    if options.ats is not None:
        sys.path.append(os.path.join(options.ats, 'tools', 'testing'))
    if 'ATS_SRC_DIR' in os.environ:
        sys.path.append(os.path.join(os.environ['ATS_SRC_DIR'], 'tools', 'testing'))
    import test_manager

    # create the logfile
    testlog = test_manager.setup_testlog(txtwrap, False)
    
    test_manager.check_options(options)

    # if using rerun-failed option, parse logfile for failed tests
    if options.rerun_failed:
        if isinstance(options.rerun_failed, bool):
            options.rerun_failed = test_manager.find_last_logfile()
        options.tests = test_manager.find_failed(options.rerun_failed)

        # need to short-circuit return here, because empty test list
        # will be interpreted as running all tests
        if len(options.tests) == 0:
            return 0

    executable = test_manager.check_for_executable(options, testlog)
    mpiexec = test_manager.check_for_mpiexec(options, testlog)
    config_file_list = test_manager.generate_config_file_list(options)

    print("Running ATS demo problems :")

    # loop through config files, cd into the appropriate directory,
    # read the appropriate config file and run the various tests.
    start = time.time()
    report = {}
    for config_file in sorted(config_file_list):
        print(80 * '=', file=testlog)
        print(f'Running {config_file}', file=testlog)
        header = os.path.split(config_file)[-1]
        if len(header) > 20:
            header = header[:20]
        else:
            header = header + ' '*(20-len(header))

        print(f'{header} | ', end='', file=sys.stdout)

        # get the absolute path of the directory
        test_dir = os.path.dirname(config_file)
        # cd into the test directory so that the relative paths in
        # test files are correct
        os.chdir(test_dir)
        if options.debug:
            print("Changed to working directory: {0}".format(test_dir))

        tm = test_manager.RegressionTestManager(executable, mpiexec, suffix='demo')

        if options.debug:
            tm.debug(True)

        # get the relative file name
        filename = os.path.basename(config_file)

        tm.generate_tests(filename,
                          options.suites,
                          options.tests,
                          options.exclude,
                          options.timeout,
                          False,
                          testlog)

        if options.debug:
            print(70 * '-')
            print(tm)

        if options.list_available_suites:
            tm.display_available_suites()

        if options.list_available_tests:
            tm.display_available_tests()

        if options.list_tests:
            tm.display_selected_tests()

        tm.run_tests(options.dry_run,
                     False,
                     False,
                     False,
                     True,
                     testlog)

        report[filename] = tm.run_status()

        # Not sure why this is needed to get proper printing when there are no tests...
        if tm.num_tests() == 0:
            print('', file=sys.stdout)

    os.chdir(root_dir)

    stop = time.time()
    status = 0
    if not options.dry_run and not options.list_tests:
        print("")
        run_time = stop - start
        test_manager.summary_report_by_file(report, testlog)
        test_manager.summary_report(run_time, report, testlog)
        status = test_manager.summary_report(run_time, report, sys.stdout)

    testlog.close()
    return status


def _preserve_cwd(function):
   def decorator(*args, **kwargs):
      cwd = os.getcwd()
      result = function(*args, **kwargs)
      os.chdir(cwd)
      return result
   return decorator


@_preserve_cwd
def run_demo_local(testnames, config_dir=None, options_list=None, force=False):
    """This is a short wrapper to run a demo not from the commandline."""
    if isinstance(testnames, str):
        testnames = [testnames,]
    
    if config_dir is None:
        config_dir = os.path.split(os.getcwd())[-1]
    
    workdir = os.path.join(os.environ['ATS_SRC_DIR'], 'docs', 'documentation', 'source', 'ats_demos')

    demodirs = [os.path.join(workdir, config_dir, testname+'.demo') for testname in testnames]
    testnames = [tname for (dd, tname) in zip(demodirs, testnames) if (not os.path.isdir(dd) or force)]

    if len(testnames) > 0:
        os.chdir(workdir)
        if options_list is None:
            options_list = []
        options_list += [config_dir, '-t'] + testnames
        opts = commandline_options(options_list)
        main(opts)


if __name__ == "__main__":
    cmdl_options = commandline_options()
    suite_status = main(cmdl_options)
    sys.exit(suite_status)

