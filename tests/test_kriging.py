
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

    # Data was generated arbitrarily, so
    # tests using the sample aren't very accurate
    return

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

    # Dict that holds what counties overlap with what states
    scd = {"s0": [f"c{i}" for i in [0,1,2,3]],
           "s1": ["c4", "c5"],
           "s2": [f"c{i}" for i in [6,7,8]],
           "s3": [f"c{i}" for i in [9,10,11]]}
    
    # Separate out the samples for each state
    stateResults = {}
    for stateId in scd:
        countyIds = scd[stateId]

        # Filter by county name
        # NOTE: there are too few counties to have separate, accurate
        # models for each state.  For now, use all counties for each state
        #curSamples = counties[counties[idCol].isin(countyIds)]
        curSamples = counties


        # Grab the geometry for the state
        goi = Polygon(states[states[idCol] == stateId][geoCol].item())

        # Do the kriging
        val, C, D, W = ManualBlockKriging(curSamples, idCol, dataCol,
                                          geoCol, goi, VariogramModel.LINEAR)
        
        # Save the result
        print(val)
        stateResults[stateId] = val
    
    assert False
    # Now, use a gator
    allNodes, graph = GenerateSampleGraph(zips, counties, states, regions, adjMat, adjDf)
    gator = Gator(graph, Path('./logs/testStateKriging.log'))

    for stateId in scd:
        curSamples = counties

        #val, matrices = gator.SpatialKriging()


def testDataGeneration():

    # This test is only good for manual inspection
    #return

    # Set a seed for repeatable results
    #np.random.seed(42)

    # Generate some fake test data
    idCol = 'id'
    dataCol = 'value'
    geoCol = 'geometry'

    allSamples, bbox = GenSyntheticData(idCol, dataCol, geoCol, 50, Point(0,0))

    # Pick some GOIs
    xmin, ymin, xmax, ymax = bbox.bounds
    xmin+=50
    ymin+=50
    xmax+=50
    ymax+=50
    

    gois = {'g0': Polygon(((xmin/10., ymin/10.), (xmin/10., ymax/10.),
                           (xmax/10., ymax/10.), (xmax/10., ymin/10.)))}
    
    #allSamples.plot()
    #plt.show()

    #assert False

    # Do the manual kriging
    manualResults = {}
    for k in gois:
        goi = gois[k]

        val, C, D, W = ManualBlockKriging(allSamples, idCol, dataCol,
                                          geoCol, goi, VariogramModel.EXPONENTIAL)
        
        plt.show()
        
        print(val)
        assert(False)
    

def testSimulatedData():

    # Using the data generation, create a few "states"
    # to run test kriging on

    # Set a seed for repeatable tests
    np.random.seed(42)

    # Generate some fake test data
    idCol = 'id'
    dataCol = 'value'
    geoCol = 'geometry'
    areaCol = 'area'

    # Generate 4 'states' with 'counties' inside them
    allStates = []
    allCountiesDf = None
    startingPoints = [Point(50,50), Point(50,100), Point(100,100), Point(100,50)]
    for i in range(4):

        # Generate the state's id
        newStateId = f's{i}'

        # Generate the data
        startVal = i*.15 + .1
        startPoint = startingPoints[i]

        countyVals, stateBbox = GenSyntheticData(idCol, dataCol, geoCol, areaCol, startVal, startPoint,
                                                 VariogramModel.EXPONENTIAL, [100,.01,0.005],
                                                 idPrefix=newStateId)
        
        
        # Setup the row for the new state
        newState = {idCol: newStateId,
                    dataCol: startVal,
                    geoCol: stateBbox}
        
        # Append the new data to the appropriate structures
        if allCountiesDf is None:
            allCountiesDf = countyVals
        else:
            allCountiesDf = gpd.GeoDataFrame(pd.concat([allCountiesDf, countyVals]).reset_index()).drop(['index'], axis=1)
        
        allStates.append(newState)

    # Form the states into a dataframe
    allStatesDf = gpd.GeoDataFrame(data=[allStates])


    # Now, we need node objects for everything
    # Start with states
    stateNodes = {}
    for index, row in allStatesDf.iterrows():

        # Make the node object        
        newNode = Node(row[idCol], {EdgeType.AREA: row[geoCol].area}, GEID.STATE, row[geoCol])

        # TODO: Checkpoint



    countyNodes = {}
    for index, row in allCountiesDf.iterrows():

        # Get the id
        curId = row[idCol]

        # Make the node object
        newNode = Node(curId, {EdgeType.AREA: row[areaCol]}, GEID.COUNTY, row[geoCol])





    print(allCountiesDf)

        
    
    assert False





    


