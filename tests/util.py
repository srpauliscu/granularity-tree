

# Contains hard-coded node samples for testing

# Import block
#from src.entities import *
import pandas as pd
#from src.kGraph import *
from src.gator import *
from pathlib import Path
import shutil
from collections.abc import Callable


TEST_GRAPH_NAME = 'testGraph'

# Files where the test data is stored
ZIP_TEST_FILE = Path("./tests/zips.csv")
COUNTY_TEST_FILE = Path("./tests/counties.csv")
STATE_TEST_FILE = Path("./tests/states.csv")
ADJ_TEST_FILE = Path("./tests/adjMat.csv")

COUNTY_ASSIGNMENT = {'s0': [f'c{i}' for i in range(0,4)],
                     's1': [f'c{i}' for i in range(4,6)],
                     's2': [f'c{i}' for i in range(6,9)],
                     's3': [f'c{i}' for i in range(9, 12)]
}


def BasicWeight(i, j, wm):
    return min(i,j) * wm

def HashWeight(i, j, wm):
    return hash((min(i,j), max(i, j)))

# Function to make the samples
def MakeTestSamples(sampleSize: int, weightModifier: float, WeightCalc: Callable):

    # Make the nodes programatically for testing
    sampleNodes = [Node(f"node{i}", {w: i for w in EdgeType}, GEID.TEST) for i in range(sampleSize)]

    # Need actual loops to form the numpy arrays
    # Note: This is NOT the array(s) that the graph keeps - 
    # this is just to organize the sample weights
    sampleGraphs = {w: np.zeros((sampleSize, sampleSize)) for w in EdgeType}
    for g in sampleGraphs:
        curGraph = sampleGraphs[g]

        for i in range(sampleSize):
            for j in range(sampleSize):
                weight = WeightCalc(i, j, weightModifier)
                curGraph[i,j] = weight
                curGraph[j,i] = weight
    

    return sampleNodes, sampleGraphs


def ResetForTest(sampleSize: int, weightModifier: float, testName: str, WeightCalc: Callable = BasicWeight):

    # Erase all of the files associated with the graph
    graphSaveDir = Path(f"./graphs/{TEST_GRAPH_NAME}")
    if graphSaveDir.exists():
        shutil.rmtree(graphSaveDir)

    # Get the samples
    sampleNodes, sampleGraphs = MakeTestSamples(sampleSize, weightModifier, WeightCalc)

    # Clear the log file if it exists
    logfile = Path(f"./logs/{testName}.log")
    if logfile.exists():
        logfile.unlink()
    
    # Instantiate the graph
    kGraph = GranularityGraph(TEST_GRAPH_NAME, logfile)

    return sampleNodes, sampleGraphs, kGraph


### Utility Functions for Test Case ###

def SampleValidityCheck(zips: pd.DataFrame, counties: pd.DataFrame,
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

def GetSampleDfs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    zips = pd.read_csv(ZIP_TEST_FILE)
    counties = pd.read_csv(COUNTY_TEST_FILE)
    states = pd.read_csv(STATE_TEST_FILE)

    return zips, counties, states



def GetSampleAdjMat() -> tuple[np.typing.NDArray, pd.DataFrame]:

    # Read in the dataframe
    adjDf = pd.read_csv(ADJ_TEST_FILE)

    # Return it as a numpy array, skipping the labels
    return adjDf.iloc[:, 1:].to_numpy(), adjDf


def GenerateSampleGraph(zips: pd.DataFrame, counties: pd.DataFrame,
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


def MakeSampleMatchAnswerKey(allNodes: dict[str, Node], 
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


### Utility functions for gator testing ###

def GetGatorSamples(gator: Gator, sampleSize: int, idCol: str, dataCol: str) \
    -> tuple[pd.DataFrame, pd.DataFrame]:

    # Use the gator to make the samples
    smallDf, largeDf = gator.MakeSample(sampleSize, idCol, dataCol)

    # We also 

    # Validate it via sum
    groupedDf = smallDf.groupby(gator.DEST_COL)
    tot = groupedDf[[gator.VALUE_FACTOR_COL]].sum()

    for ind, row in tot.iterrows():
        destId = ind[0]

        # Find the matching total in the largeDf
        destTot = largeDf.at[destId, dataCol]

        # Allow for float errors
        assert math.isclose(destTot, row[gator.VALUE_FACTOR_COL], abs_tol=.0001)

    # Check the lengths match
    assert tot.shape[0] == largeDf.shape[0]

    # Validate using distribute as well
    newDict = []
    for ind, row in largeDf.iterrows():

        destDict = row[gator.DEST_COL]
        vfDict = row[gator.VALUE_FACTOR_COL]

        for id in destDict:
            newDict.append(
                {
                    idCol: id,
                    dataCol: vfDict[id]
                }
            )
    
    resDf = pd.DataFrame(newDict)

    # Make sure the results match
    for ind, row in resDf.iterrows():
        
        # Find the match in the original
        destData = smallDf.at[ind, dataCol]

        # Allow for float errors
        assert math.isclose(destData, row[dataCol], abs_tol=.0001)

    # Make sure lengths match
    assert resDf.shape[0] == smallDf.shape[0]


    return smallDf, largeDf