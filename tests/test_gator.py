from pathlib import Path

import pytest
import numpy as np

from samples import ResetForTest, TEST_GRAPH_NAME, HashWeight

# Gator imports the entities, so we only need to import gator
from src.gator import * 


'''
Test cases are based on the following (made up) data:
EV counts at the ZIP code, county, and state level

4 total states: s0-s3
Each state is 1000 area and has 2-4 counties:
    - s0: c0-c3
    - s1: c4, c5
    - s2: c6-c8
    - s3: c9-c11

The counties are mutually exclusive with themselves and their state,
so the states' total EVs are just the sum of their counties.

There are also ZIP codes which cross the state and county lines.  The ZIP codes
are mutually exclusive with each other but not with counties or states.




'''