
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

def distFunc(x,y,binSize=-1.):

    #if binSize > 0:
    #    return (math.floor(distance(x,y) / binSize)*binSize)+.5*binSize
    #else:
    #    return distance(x,y)
    
    if x == y:
        if binSize > 0:
            return .5*binSize
        else:
            return 0
    else:
        if binSize > 0:
            return (math.floor(distance(x,y) / binSize)*binSize)+.5*binSize
        else:
            return distance(x,y)

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

    #countyGt = ManualKriging(counties, idCol, dataCol, geoCol, poi)
    countyGt, C, D, W = ManualKriging(counties, idCol, dataCol, geoCol, poi, VariogramModel.GAUSSIAN)
    #zipGt = ManualKriging(zips, idCol, dataCol, geoCol, poi)

    # Now, set up the example for the Gator

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, regions, adjMat, adjDf)

    # Make the gator
    gator = Gator(graph, Path('./logs/testSampleKrigingBasic.log'))

    # Using the gator, try to calculate the POI using each entity type as a base
    Wm, Cm, Dm = gator.CalcKrigingWeights(counties, regions, GEID.COUNTY, GEID.REGION,
                                   idCol, idCol, dataCol, geoCol, geoCol,
                                   EdgeType.AREA, distFunc, VariogramModel.GAUSSIAN)

    # Despite using float math, all values should be identical
    assert (W == Wm).all()
    assert (C == Cm).all()
    assert (D == Dm).all()
    





