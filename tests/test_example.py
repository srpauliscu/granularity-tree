from pathlib import Path

import pytest
import numpy as np

from tests.util import *

# Gator imports the entities, so we don't need to import them here
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

For simplicity, the ZIP codes are totally contained within the four states combined,
meaning that the total number of EVs for the 4 states == EVs for the ZIP codes

'''





### Test Functions ###

# Functions to check our test case is valid

@pytest.mark.valid
def testValidity():

    # Test to make sure our test case is correct
    # Doesn't actually test any functionality

    # Get the nodes
    zips, counties, states = GetSampleDfs()

    # Form the adjMat from the CSV
    adjMat, _ = GetSampleAdjMat()

    # Just call the validity check function
    SampleValidityCheck(zips, counties, states, adjMat)

@pytest.mark.basic
def testGraphInstantiation():


    # Test to make sure our nodes are loaded
    # in correctly

    # Get the info from the files
    zips, counties, states = GetSampleDfs()
    adjMat, adjDf = GetSampleAdjMat()

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, adjMat, adjDf)

    # Separate ids by type for testing
    zipIds = zips['ID']
    countyIds = counties['ID']
    stateIds = states['ID']

    # Make sure our numbers add up within each entity type
    tsArea = 0
    for sid in stateIds:

        # Each state should be the sum of exactly its counties
        # Only area for now
        counties = COUNTY_ASSIGNMENT[sid]
        tcArea = 0

        for cid in counties:

            # Get the node
            curNode = graph.GetNode(cid, GEID.COUNTY)
            assert not curNode is None
            assert not curNode.values is None

            # Add the node's weight to the total
            tcArea += curNode.values[EdgeType.AREA]
        
        assert tcArea == allNodes[sid].values[EdgeType.AREA]

        # Keep track of the state total too
        tsArea += tcArea

    # The total of all states should equal the total 
    # of all ZIPS
    tzArea = 0
    for zid in zipIds:

        # Get the node
        curNode = graph.GetNode(zid, GEID.ZIP)
        assert not curNode is None
        assert not curNode.values is None

        # Add the node's weight to the total
        tzArea += curNode.values[EdgeType.AREA]
    
    assert tsArea == tzArea

    # Now, make sure no weight is larger than the smaller
    # of the two values
    for k0 in allNodes:
        n0 = allNodes[k0]
        for k1 in allNodes:
            if k0 == k1:
                continue
            n1 = allNodes[k1]

            # Get the weight for this edge
            weight = graph.GetWeight(n0, n1, EdgeType.AREA)

            # If the edge exists, check its validity
            assert weight is None or weight <= min(n0.values[EdgeType.AREA],
                                                   n1.values[EdgeType.AREA])



# Test the match finding of the graph


@pytest.mark.matching
def testGetMatches():

    # Get the info from the files
    zips, counties, states = GetSampleDfs()
    adjMat, adjDf = GetSampleAdjMat()

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, adjMat, adjDf)

    # Make the answer key
    answerKey = MakeSampleMatchAnswerKey(allNodes, adjMat, adjDf)

    # Now, use the graph to do the same
    # The outputs should match
    nodeList = list(allNodes.values())
    for sk in allNodes:
        sourceNode = allNodes[sk]

        # Get the graph's output
        output = graph.GetMatches(sourceNode, nodeList, EdgeType.AREA)

        # Go through one by one for better error output
        curAnswerKey = answerKey[sourceNode]
        for dn in curAnswerKey:
            assert dn in output
            assert curAnswerKey[dn] == output[dn]

        # Checking the lengths ensures one-to-one
        assert len(curAnswerKey) == len(output)

        # Test for true negatives too
        output = graph.GetMatches(sourceNode, nodeList, EdgeType.POPULATION)
        assert len(output) == 0


@pytest.mark.matching
def testFindMatches():

    # Get the info from the files
    zips, counties, states = GetSampleDfs()
    adjMat, adjDf = GetSampleAdjMat()

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, adjMat, adjDf)

    # Make the answer key
    fullAnswerKey = MakeSampleMatchAnswerKey(allNodes, adjMat, adjDf)

    # Make a dict for type checking
    zipIds = zips['ID']
    countyIds = counties['ID']
    stateIds = states['ID']
    types = {}

    for nid in allNodes:
        if nid in zipIds.values:
            types[nid] = GEID.ZIP
        elif nid in countyIds.values:
            types[nid] = GEID.COUNTY
        elif nid in stateIds.values:
            types[nid] = GEID.STATE
    
    # Separate the answer key by type
    typedKey = {}
    idTypes = [GEID.ZIP, GEID.COUNTY, GEID.STATE]
    for sn in fullAnswerKey:
        typedKey[sn] = {t: {} for t in idTypes}
        
        for dn in fullAnswerKey[sn]:
            typedKey[sn][types[dn.id]][dn] = fullAnswerKey[sn][dn]
        

    # Use FindMatches to get matches for each type
    for sk in allNodes:
        sNode = allNodes[sk]
        curAnswerKey = typedKey[sNode]

        # Go through the types one at a time
        for t in idTypes:
            output = graph.FindMatches(sNode, t, EdgeType.AREA)

            # Loop over the answer key nodes for that type
            for dn in curAnswerKey[t]:
                assert dn in output
                assert curAnswerKey[t][dn] == output[dn]
                
            assert len(curAnswerKey[t]) == len(output)

            # Test for true negatives too
            output = graph.FindMatches(sNode, t, EdgeType.POPULATION)
            assert len(output) == 0



### Tests for the full equalize pipeline ###

@pytest.mark.equalize
def testEqualizeSumBasic():

    # Get the info from the files
    zips, counties, states = GetSampleDfs()
    adjMat, adjDf = GetSampleAdjMat()

    # Make sure the sample is valid
    SampleValidityCheck(zips, counties, states, adjMat)

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, adjMat, adjDf)

    # Make the gator
    gator = Gator(graph, Path('./logs/testSampleGator.log'))

    # Using the gator, try converting from granularity to granularity

    # Easiest one first- counties to states
    idCol = 'ID'
    dataCol = 'TotalEVs'
    geoCol = 'geo'
    resDf = gator.SpatialEqualize(counties, states, GEID.COUNTY, GEID.STATE,
                           idCol, idCol, dataCol, geoCol, geoCol, AggMethod.SUM, EdgeType.AREA)
    
    # Make sure the values match
    statesTemp = states.set_index('ID')
    for ind, row in statesTemp.iterrows():
        assert resDf.at[ind, dataCol] == row[dataCol]
    
    # Do the same with population, just for testing
    dataCol = 'Population'
    resDf = gator.SpatialEqualize(counties, states, GEID.COUNTY, GEID.STATE,
                           idCol, idCol, dataCol, geoCol, geoCol, AggMethod.SUM, EdgeType.AREA)
    
    for ind, row in statesTemp.iterrows():
        assert resDf.at[ind, dataCol] == row[dataCol]

@pytest.mark.equalize
def _testEqualizeSumHard():

    # Get the info from the files
    zips, counties, states = GetSampleDfs()
    adjMat, adjDf = GetSampleAdjMat()

    # Make sure the sample is valid
    SampleValidityCheck(zips, counties, states, adjMat)

    # Make the graph
    allNodes, graph = GenerateSampleGraph(zips, counties, states, adjMat, adjDf)

    # Make the gator
    gator = Gator(graph, Path('./logs/testSampleGator.log'))

    # Using the gator, try converting from granularity to granularity

    # ZIP to states is more obtuse
    idCol = 'ID'
    dataCol = 'TotalEVs'
    resDf = gator.SpatialEqualize(zips, states, GEID.ZIP, GEID.STATE,
                           idCol, idCol, dataCol, AggMethod.SUM, EdgeType.AREA)
    
    # TODO: how we do know if this is correct?  The answers won't match
    # even if the software works as intended because the assumption that
    # EVs scale with area isn't fully accurate

    assert False

    
    # Make sure the values match
    statesTemp = states.set_index('ID')
    for ind, row in statesTemp.iterrows():
        assert resDf.at[ind, dataCol] == row[dataCol]

    return
    
    # Do the same with population, just for testing
    dataCol = 'Population'
    resDf = gator.Equalize(zips, states, GEID.ZIP, GEID.STATE,
                           idCol, idCol, dataCol, AggMethod.SUM, EdgeType.AREA)
    
    for ind, row in statesTemp.iterrows():
        assert resDf.at[ind, dataCol] == row[dataCol]

