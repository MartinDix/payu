import copy
import os
from pathlib import Path
import pdb
import pytest
import shutil
from unittest.mock import patch
import yaml

import payu
import payu.models.test

from .common import cd, make_random_file, get_manifests
from .common import tmpdir, ctrldir, labdir, workdir
from .common import sweep_work, payu_init, payu_setup
from .common import config as config_orig
from .common import write_config
from .common import make_exe, make_inputs, make_restarts, make_all_files

verbose = True

config = copy.deepcopy(config_orig)


def make_config_files():
    """
    Create files required for test model
    """

    config_files = payu.models.test.config_files
    for file in config_files:
        make_random_file(ctrldir/file, 29)


def setup_module(module):
    """
    Put any test-wide setup code in here, e.g. creating test files
    """
    if verbose:
        print("setup_module      module:%s" % module.__name__)

    # Should be taken care of by teardown, in case remnants lying around
    try:
        shutil.rmtree(tmpdir)
    except FileNotFoundError:
        pass

    try:
        tmpdir.mkdir()
        labdir.mkdir()
        ctrldir.mkdir()
        make_all_files()
    except Exception as e:
        print(e)

    write_config(config)


def teardown_module(module):
    """
    Put any test-wide teardown code in here, e.g. removing test outputs
    """
    if verbose:
        print("teardown_module   module:%s" % module.__name__)

    try:
        # shutil.rmtree(tmpdir)
        print('removing tmp')
    except Exception as e:
        print(e)

# These are integration tests. They have an undesirable dependence on each
# other. It would be possible to make them independent, but then they'd
# be reproducing previous "tests", like init. So this design is deliberate
# but compromised. It means when running an error in one test can cascade
# and cause other tests to fail.
#
# Unfortunate but there you go.


def test_init():

    # Initialise a payu laboratory
    with cd(ctrldir):
        payu_init(None, None, str(labdir))

    # Check all the correct directories have been created
    for subdir in ['bin', 'input', 'archive', 'codebase']:
        assert((labdir / subdir).is_dir())


def test_setup():

    # Create some input and executable files
    make_inputs()
    make_exe()

    bindir = labdir / 'bin'
    exe = config['exe']

    make_config_files()

    # Run setup
    payu_setup(lab_path=str(labdir))

    assert(workdir.is_symlink())
    assert(workdir.is_dir())
    assert((workdir/exe).resolve() == (bindir/exe).resolve())
    workdirfull = workdir.resolve()

    config_files = payu.models.test.config_files

    for f in config_files + ['config.yaml']:
        assert((workdir/f).is_file())

    for i in range(1, 4):
        assert((workdir/'input_00{i}.bin'.format(i=i)).stat().st_size
               == 1000**2 + i)

    with pytest.raises(SystemExit,
                       match="work path already exists") as setup_error:
        payu_setup(lab_path=str(labdir), sweep=False, force=False)
    assert setup_error.type == SystemExit

    payu_setup(lab_path=str(labdir), sweep=False, force=True)

    assert(workdir.is_symlink())
    assert(workdir.is_dir())
    assert((workdir/exe).resolve() == (bindir/exe).resolve())
    workdirfull = workdir.resolve()

    config_files = payu.models.test.config_files

    for f in config_files + ['config.yaml']:
        assert((workdir/f).is_file())

    for i in range(1, 4):
        assert((workdir/'input_00{i}.bin'.format(i=i)).stat().st_size
               == 1000**2 + i)


@pytest.mark.parametrize(
    "current_version, min_version",
    [
        ("2.0.0", "1.0.0"),
        ("v0.11.2", "v0.11.1"),
        ("1.0.0", "1.0.0"),
        ("1.0.0+4.gabc1234", "1.0.0"),
        ("1.0.0+0.gxyz987.dirty", "1.0.0"),
        ("1.1.5", 1.1)
    ]
)
def test_check_payu_version_pass(current_version, min_version):
    # Mock the payu version
    with patch('payu.__version__', current_version):
        # Avoid running Experiment init method
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            # Mock config.yaml
            expt.config = {
                "payu_minimum_version": min_version
            }
            expt.check_payu_version()


@pytest.mark.parametrize(
    "current_version, min_version",
    [
        ("1.0.0", "2.0.0"),
        ("v0.11", "v0.11.1"),
        ("1.0.0+4.gabc1234", "1.0.1"),
        ("1.0.0+0.gxyz987.dirty", "v1.2"),
    ]
)
def test_check_payu_version_fail(current_version, min_version):
    with patch('payu.__version__', current_version):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            expt.config = {
                "payu_minimum_version": min_version
            }

            with pytest.raises(RuntimeError):
                expt.check_payu_version()


@pytest.mark.parametrize(
    "current_version", ["1.0.0", "1.0.0+4.gabc1234"]
)
def test_check_payu_version_pass_with_no_minimum_version(current_version):
    with patch('payu.__version__', current_version):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            # Leave version out of config.yaml
            expt.config = {}

            # Check runs without an error
            expt.check_payu_version()


@pytest.mark.parametrize(
    "minimum_version", ["abcdefg", None]
)
def test_check_payu_version_configured_invalid_version(minimum_version):
    with patch('payu.__version__', "1.0.0"):
        with patch.object(payu.experiment.Experiment, '__init__',
                          lambda x: None):
            expt = payu.experiment.Experiment()

            expt.config = {
                "payu_minimum_version": minimum_version
            }

            with pytest.raises(ValueError):
                expt.check_payu_version()
