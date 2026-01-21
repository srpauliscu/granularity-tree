
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

    # We need to normalize the data
    normFactor = max(counties[dataCol].max(), regions[dataCol].max())
    counties[dataCol] /= normFactor
    regions[dataCol] /= normFactor

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
    areaCol = 'area'

    allSamples, bbox = GenSyntheticData(idCol, dataCol, geoCol, areaCol, 50, Point(0,0),
                                        VariogramModel.EXPONENTIAL, [25, 2, 1])
    
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
        
        #plt.show()
        
        print(val)
    

def testSimulatedData():

    # Using the data generation, create a few "states"
    # to run test kriging on

    # Set a seed for repeatable tests
    #np.random.seed(42)

    # Generate some fake test data
    idCol = 'id'
    dataCol = 'value'
    geoCol = 'geometry'
    areaCol = 'area'
    stateIdCol = 'stateId'

    # Generate 4 'states' with 'counties' inside them
    allStates = []
    stateGeos = {}
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
        
        # Save the geometry separately for later
        stateGeos[newStateId] = stateBbox
        
        # Also add the state ID as a column for easy filtering later
        countyVals[stateIdCol] = newStateId
        
        # Append the new data to the appropriate structures
        if allCountiesDf is None:
            allCountiesDf = countyVals
        else:
            allCountiesDf = gpd.GeoDataFrame(pd.concat([allCountiesDf, countyVals]).reset_index()).drop(['index'], axis=1)
        
        allStates.append(newState)

    # Form the states into a dataframe
    allStatesDf = gpd.GeoDataFrame(data=allStates)

    # Make an empty graph
    graph = GranularityGraph('simulatedDataTest', Path('./logs/simulatedDataTest.log'))

    # Now, we need node objects for everything
    # Start with states
    stateNodes = {}
    for index, row in allStatesDf.iterrows():


        # Make the node object        
        newNode = Node(row[idCol], {EdgeType.AREA: row[geoCol].area}, GEID.STATE, row[geoCol])

        # Save the node object
        stateNodes[row[idCol]] = newNode


    # Form the county nodes and add each to the graph
    for index, row in allCountiesDf.iterrows():

        # Get the id
        curCountyId = row[idCol]

        # Make the node object
        newNode = Node(curCountyId, {EdgeType.AREA: row[areaCol]}, GEID.COUNTY, row[geoCol])

        # Grab the matching state node
        stateId = curCountyId[:2]
        stateNode = stateNodes[stateId]

        # Add the pair to the graph, using (arbitrarily) the 
        # county area as the weight
        status = graph.AddNodes(stateNode, newNode, EdgeType.AREA, row[areaCol])
        assert status == Status.SUCCESS
    
    # Make sure everything was added
    assert len(graph) == allStatesDf.shape[0] + allCountiesDf.shape[0]

    # TODO: Remove this
    # For quick testing, just do one state

    # Have the manual kriger calculate results for each state
    stateGroups = allCountiesDf.groupby(stateIdCol)
    groundTruths = {}
    for stateId, counties in stateGroups:

        # We need to reset the index so that the matrices are set up correctly
        counties = counties.reset_index().drop(columns=['index'])

        # Manual kriging
        curCountyGt, _, _, _ = ManualBlockKriging(counties, idCol,
                                                  dataCol, geoCol,
                                                  stateGeos[stateId], VariogramModel.EXPONENTIAL)
        
        # Save out the group truth
        groundTruths[stateId] = curCountyGt
    


    # Now, have a gator do the kriging
    gator = Gator(graph, Path("./logs/testSimulatedData.log"))

    resDf = gator.SpatialEqualize(allCountiesDf, allStatesDf, GEID.COUNTY, GEID.STATE,
                                  idCol, idCol, dataCol, geoCol, geoCol, AggMethod.KRIGING,
                                  EdgeType.AREA, distFunction=distFunc, model=VariogramModel.EXPONENTIAL)
    
    # Compare the results to each other
    for sid in groundTruths:
        gt = groundTruths[sid]
        res = resDf[resDf[idCol] == sid]['value_est'].item()

        assert math.isclose(gt, res)

        # We can also check if it's close to the original value
        # but with more leniency (10% error)
        ov = int(sid[-1])*.15 + .1
        assert math.isclose(gt, ov, rel_tol=.20)

    
    print(groundTruths)
    print(resDf)
    
