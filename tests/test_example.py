from pathlib import Path

import pytest
import numpy as np

from samples import ResetForTest, TEST_GRAPH_NAME, HashWeight

# Gator imports the entities, so we don't need to import them here
from src.gator import * 

ZIP_TEST_FILE = Path("./tests/zips.csv")
COUNTY_TEST_FILE = Path("./tests/counties.csv")
STATE_TEST_FILE = Path("./tests/states.csv")
ADJ_TEST_FILE = Path("./tests/adjMat.csv")


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

COUNTY_ASSIGNMENT = {'s0': [f'c{i}' for i in range(0,4)],
                     's1': [f'c{i}' for i in range(4,6)],
                     's2': [f'c{i}' for i in range(6,9)],
                     's3': [f'c{i}' for i in range(9, 12)]
}

### Utility Functions ###

def ValidityCheck(zips: pd.DataFrame, counties: pd.DataFrame,
                  states: pd.DataFrame, adjMat: np.typing.NDArray):


    '''
    Function to make sure our numbers add up correctly.
    '''

    # Columns: ID, Area, Population, Total EVs

    # Make a dict for labels and looping
    dfs = {'ZIPS':zips, 'Counties': counties, 'States': states}

    for k0 in dfs:

        # Grab the df
        df0 = dfs[k0]

        # Areas should add up to 4000
        assert df0['Area'].sum() == 4000

        # All three columns should have the same total across the dfs
        for k1 in dfs:
            
            # No need to test the same df against itself
            if k0 == k1:
                continue

            # Grab the df
            df1 = dfs[k1]

            # Test each column except ID
            for c in df0:
                
                # Skip the IDs
                if c == 'ID':
                    continue


                # In case the test fails, print the column and frames
                #print(k0, k1, c)
                assert df0[c].sum() == df1[c].sum()
    
    # Make sure the adjMat is symmetric
    for i in range(adjMat.shape[0]):
        for j in range(i, adjMat.shape[1]):

            assert adjMat[i, j] == adjMat[j, i]

def GetDfs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    zips = pd.read_csv(ZIP_TEST_FILE)
    counties = pd.read_csv(COUNTY_TEST_FILE)
    states = pd.read_csv(STATE_TEST_FILE)

    return zips, counties, states



def GetAdjMat() -> tuple[np.typing.NDArray, pd.DataFrame]:

    # Read in the dataframe
    adjDf = pd.read_csv(ADJ_TEST_FILE)

    # Return it as a numpy array, skipping the labels
    return adjDf.iloc[:, 1:].to_numpy(), adjDf


def GenerateGraph(zips: pd.DataFrame, counties: pd.DataFrame,
                  states: pd.DataFrame, adjMat: np.typing.NDArray,
                  adjDf: pd.DataFrame) -> tuple[dict[str, Node], GranularityGraph]:

    # Make a blank graph
    graph = GranularityGraph('fakeEntitiesTest', Path('./logs/fakeEntitiesTest.log'))

    # Go through each dataframe and make nodes for each entity
    dfs = {GEID.ZIP: zips, GEID.COUNTY: counties, GEID.STATE: states}
    allNodes = {}
    for k in dfs:

        # Get the df
        df = dfs[k]

        for row in df.itertuples():
            
            # Make the node
            newNode = Node(row.ID, {EdgeType.AREA: row.Area}, k)
            allNodes[row.ID] = newNode

    # Now, add the nodes and edges
    # Use the column names to index the matrix
    ids = adjDf.columns[1:]
    
    for i, id0 in enumerate(ids):

        # Get the node
        n0 = allNodes[id0]

        for j, id1 in enumerate(ids):

            # Skip the diagonal
            if i == j:
                continue

            # Get the node
            n1 = allNodes[id1]

            # Get the weight
            weight = adjMat[i, j]

            # Try and add the edge
            status = graph.AddNodes(n0, n1, EdgeType.AREA, weight)
            assert status == Status.SUCCESS
    
    # Make sure everything was added
    assert len(graph) == zips.shape[0] + counties.shape[0] + states.shape[0]

    return allNodes, graph


### Test Functions ###

# Functions to check our test case is valid

@pytest.mark.valid
def testValidity():

    # Test to make sure our test case is correct
    # Doesn't actually test any functionality

    # Get the nodes
    zips, counties, states = GetDfs()

    # Form the adjMat from the CSV
    adjMat, _ = GetAdjMat()

    # Just call the validity check function
    ValidityCheck(zips, counties, states, adjMat)

@pytest.mark.basic
def testGraphInstantiation():


    # Test to make sure our nodes are loaded
    # in correctly

    # Get the info from the files
    zips, counties, states = GetDfs()
    adjMat, adjDf = GetAdjMat()

    # Make the graph
    allNodes, graph = GenerateGraph(zips, counties, states, adjMat, adjDf)

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

# Utility function
def MakeMatchAnswerKey(allNodes: dict[str, Node], 
                       adjMat: np.typing.NDArray,
                       adjDf: pd.DataFrame) -> dict[Node, dict[Node, float]]:

    # Use the column list to get the indices
    allIds = adjDf.columns[1:]

    # For each node, return exactly all nodes it has a match with
    # Use the adjMat to form the answer key
    answerKey = {}
    for i, sourceId in enumerate(allIds):

        sNode = allNodes[sourceId]
        answerKey[sNode] = {}

        # Go through and add all non-zero weights
        for j, destId in enumerate(allIds):

            # Skip the diag
            if i == j:
                continue

            # Check if the weight is zero
            weight = adjMat[i, j]
            if not weight == 0:
                answerKey[sNode][allNodes[destId]] = weight

    return answerKey


@pytest.mark.matching
def testGetMatches():

    # Get the info from the files
    zips, counties, states = GetDfs()
    adjMat, adjDf = GetAdjMat()

    # Make the graph
    allNodes, graph = GenerateGraph(zips, counties, states, adjMat, adjDf)

    # Make the answer key
    answerKey = MakeMatchAnswerKey(allNodes, adjMat, adjDf)

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
    zips, counties, states = GetDfs()
    adjMat, adjDf = GetAdjMat()

    # Make the graph
    allNodes, graph = GenerateGraph(zips, counties, states, adjMat, adjDf)

    # Make the answer key
    fullAnswerKey = MakeMatchAnswerKey(allNodes, adjMat, adjDf)

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







# Tests for each aggregation/deaggregation option

@pytest.mark.aggregate
def testMean():
    pass

@pytest.mark.aggregate
def testSum():
    pass

@pytest.mark.deaggregate
def testDistribute():
    pass

@pytest.mark.deaggregate
def testCopy():
    pass

