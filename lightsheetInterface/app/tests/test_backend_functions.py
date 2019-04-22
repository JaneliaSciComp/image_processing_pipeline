from variables_for_testing import *
import os, sys
# Get path set to be able to load necessary functions
sys.path.insert(0, os.path.realpath(__file__).rsplit('/',3)[0] )

import pytest
from app import app
from app.utils import *
from app.jobs_io import *

def test_converted_jacs_time():
    converted_jacs_time = convert_jacs_time('2019-03-14T17:24:51.614+0000')
    converted_jacs_time_in_string = converted_jacs_time.strftime("%Y-%m-%d %H:%M:%S")
    assert "2019-03-14 13:24:51" == converted_jacs_time_in_string

def test_get_job_dictionary_as_list():
    actual_list_to_return = get_job_dictionary_as_list( get_job_dictionary_as_list_test_variables['parent_job_information'] )
    assert (get_job_dictionary_as_list( get_job_dictionary_as_list_test_variables['list_to_return'] ), actual_list_to_return)