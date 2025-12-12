
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
def testSinglePOIWeights():

    # Simple test that only calculate weights for one NOI

    # Get the nodes
    zips, counties, states, regions = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, adjDf = GetSampleAdjMat()

    # Do a validity check
    SampleValidityCheck(zips, counties, states, regions, adjMat)

    # Use the region as the area of interest
    goi = regions.head(n=1)['shape'].item()#.centroid

    # Use the manual kriging method to compute ground truth
    idCol = 'ID'
    dataCol = 'AvgEVs'
    geoCol = 'shape'

    #countyGt = ManualKriging(counties, idCol, dataCol, geoCol, poi)
    countyGt, C, D, W = ManualBlockKriging(counties, idCol,
                                           dataCol, geoCol,
                                           goi, VariogramModel.GAUSSIAN)
    
    #zipGt = ManualKriging(zips, idCol, dataCol, geoCol, poi)

    # Now, set up the example for the Gator

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, regions, adjMat, adjDf)

    # Make the gator
    gator = Gator(graph, Path('./logs/testSampleKrigingBasic.log'))

    # Using the gator, try to calculate the POI weights using each entity type as a base
    _, matrices  = gator.CalcKrigingWeights(counties, regions, GEID.COUNTY, GEID.REGION,
                                   idCol, idCol, dataCol, geoCol, geoCol,
                                   EdgeType.AREA, distFunc, VariogramModel.GAUSSIAN)
    
    # Unpack the matrices for the singular POI
    assert len(matrices) == 1
    Wm, Cm, Dm = matrices[list(matrices.keys())[0]]

    # Despite using float math, all values should be identical
    assert (W == Wm).all()
    assert (C == Cm).all()
    assert (D == Dm).all()


def testRegionKriging():

    '''
    Use ZIPS, counties, and states as origins
    for kriging to the region level

    This avoids partially overlapping entities,
    for a simpler test.
    '''

    # Get the nodes
    zips, counties, states, regions = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, adjDf = GetSampleAdjMat()

    # Do a validity check
    SampleValidityCheck(zips, counties, states, regions, adjMat)

    # Use the region as the area of interest
    goi = regions.head(n=1)['shape'].item()

    # Use the manual kriging method to compute ground truth
    # for each source type
    idCol = 'ID'
    dataCol = 'AvgEVs'
    geoCol = 'shape'

    zipGt, _, _, _  = ManualBlockKriging(zips, idCol,
                                         dataCol, geoCol,
                                         goi, VariogramModel.GAUSSIAN)
    
    countyGt, _, _, _ = ManualBlockKriging(counties, idCol,
                                           dataCol, geoCol,
                                           goi, VariogramModel.GAUSSIAN)
    '''
    stateGt, _, _, _ = ManualBlockKriging(states, idCol,
                                          dataCol, geoCol,
                                          goi, VariogramModel.GAUSSIAN)
    '''

    # Use a gator to do the kriging
    allNodes, graph = GenerateSampleGraph(zips, counties, states, regions, adjMat, adjDf)
    gator = Gator(graph, Path("./logs/testRegionKriging.log"))

    zipGatorDf = gator.SpatialKriging(zips, regions, GEID.ZIP, GEID.REGION,
                                      idCol, idCol, dataCol, geoCol, geoCol,
                                      EdgeType.AREA, distFunc,
                                      VariogramModel.GAUSSIAN)
    
    countyGatorDf = gator.SpatialKriging(counties, regions, GEID.COUNTY, GEID.REGION,
                                         idCol, idCol, dataCol, geoCol, geoCol,
                                         EdgeType.AREA, distFunc,
                                         VariogramModel.GAUSSIAN)
    
    # Since we have just one GOI here, pull out the numbers to compare
    zipGatorVal = zipGatorDf.head(n=1)[dataCol + '_est'].item()
    countyGatorVal = countyGatorDf.head(n=1)[dataCol + '_est'].item()

    assert math.isclose(zipGatorVal, zipGt)
    assert math.isclose(countyGatorVal, countyGt)


def testStateKriging():

    '''
    Use ZIPS and counties as origins
    for kriging to the state level
    '''

    # Get the nodes
    zips, counties, states, regions = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, adjDf = GetSampleAdjMat()

    # Do a validity check
    SampleValidityCheck(zips, counties, states, regions, adjMat)

    # Relevant column names
    idCol = 'ID'
    dataCol = 'AvgEVs'
    geoCol = 'shape'

    # Do the manual kriging for each state separately
    print(states)

    # Dict that holds what counties are for what states
    
    
    assert False



