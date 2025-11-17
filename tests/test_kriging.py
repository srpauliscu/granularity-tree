
from pathlib import Path

import pytest
import numpy as np

from tests.util import *

# Gator imports the entities, so we don't need to import them here
from src.gator import *



### Test Functions ###

@pytest.mark.valid
def testAreaValidity():

    # Basic sanity check for the example geometries

    # Get the nodes
    zips, counties, states = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, _ = GetSampleAdjMat()

    # Just call the validty check function
    SampleValidityCheck(zips, counties, states, adjMat)


@pytest.mark.basic
def testSinglePOI():

    # Simple test that only estimates one POI

    # Get the nodes
    zips, counties, states = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, _ = GetSampleAdjMat()

    # Do a validity check
    SampleValidityCheck(zips, counties, states, adjMat)

    # Pick the center of the states as the poi (arbitrarily)
    SL = math.sqrt(4000)
    poi = centroid(Polygon((
       (0,0),
       (0,SL),
       (SL,SL),
       (SL,0)
    )))


    # Use the manual kriging method to compute ground truth
    gt = ManualKriging(states, 'ID', 'TotalEVs')





    pass