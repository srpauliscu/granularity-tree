

# Contains hard-coded node samples for testing

# Import block
#from src.entities import *
import pandas as pd
from src.kGraph import *
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
