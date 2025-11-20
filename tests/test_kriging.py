
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
    zips, counties, states, regions = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, _ = GetSampleAdjMat()

    # Just call the validty check function
    SampleValidityCheck(zips, counties, states, regions, adjMat)


@pytest.mark.basic
def testSinglePOI():

    # Simple test that only estimates one POI

    # Get the nodes
    zips, counties, states, regions = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, adjDf = GetSampleAdjMat()

    # Do a validity check
    SampleValidityCheck(zips, counties, states, regions, adjMat)

    # Pick the center of the region as the poi (arbitrarily)
    poi = regions.head(n=1)['shape'].item().centroid

    # Use the manual kriging method to compute ground truth
    idCol = 'ID'
    dataCol = 'AvgEVs'
    geoCol = 'shape'

    countyGt = ManualKriging(counties, idCol, dataCol, geoCol, poi)
    #zipGt = ManualKriging(zips, idCol, dataCol, geoCol, poi)

    # Now, set up the example for the Gator

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, regions, adjMat, adjDf)

    # Make the gator
    gator = Gator(graph, Path('./logs/testSampleKrigingBasic.log'))

    # Using the gator, try to calculate the POI using each entity type as a base

    # Temporary testing
    distFunc = lambda x,y: math.floor(distance(x,y) / 5.)
    val = gator.CalcKrigingWeights(counties, regions, GEID.COUNTY, GEID.REGION,
                                   idCol, idCol, dataCol, geoCol, geoCol,
                                   EdgeType.AREA, distFunc, VariogramModel.EXPONENTIAL)

    assert False

    





