

# Contains hard-coded node samples for testing

# Import block
#from src.entities import *
import pandas as pd
#from src.kGraph import *
from src.gator import *
from pathlib import Path
import shutil
from collections.abc import Callable
import random

# To reduce code duplication
from src.connecticutGraph import LoadShapefile, AddLevel


TEST_GRAPH_NAME = 'testGraph'

# Files where the test data is stored
ZIP_TEST_FILE = Path("./tests/zips.csv")
COUNTY_TEST_FILE = Path("./tests/counties.csv")
STATE_TEST_FILE = Path("./tests/states.csv")
ADJ_TEST_FILE = Path("./tests/adjMat.csv")


# Global vars for column names
T_ID_COL = "timestamp_start__"
T_DATA_COL = "value__"
T_INTERVAL_COL = "interval__"
ZCTA_COL = 'ZCTA'

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
    sampleNodes = [Node(f"node{i}", {w: i for w in EdgeType}, GEID.TEST,
                        Polygon(((i, i), (i, i+2), (i+2, i+2), (i+2, i)))) for i in range(sampleSize)]

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
                #print(df0[c].sum(), df1[c].sum())
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

        for ind, row in df.iterrows():
            
            # Make the node, ignoring geometry
            newNode = Node(row['ID'], {EdgeType.AREA: row['Area']}, k, None)
            allNodes[row['ID']] = newNode

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


def GenerateTemporalSample(startTs: pd.Timestamp, endTs: pd.Timestamp,
                           unit: TID = TID.HOUR) \
    -> tuple[pd.DataFrame, pd.DataFrame]:

    # Use this function to generate temporal test data

    answerKeyRows = []
    sampleRows = []
    curStartTs = startTs
    argDict = {TID_TO_STRING[unit]: 1}
    ONE_UNIT = pd.DateOffset(**argDict)
    UNIT_TO_SEC_FACTOR = ((curStartTs + ONE_UNIT) - curStartTs).total_seconds()

    # Generate the test data in blocks of units that are subdivided
    # into intervals randomly

    while curStartTs < endTs:

        # Generate a random length
        numUnits = 5#random.randint(1,16)

        # Get the end point
        nextEndTs = min(curStartTs + (ONE_UNIT * numUnits), endTs)
        numUnits = (nextEndTs - curStartTs).total_seconds() / UNIT_TO_SEC_FACTOR

        # Generate some random data for it
        value = random.randint(1, 100)*numUnits

        # Each hour in the interval will evenly split the value
        lastTs = curStartTs
        curKeyRows = []
        while lastTs < nextEndTs:# and len(curKeyRows) <= numUnits:

            # Initialize a new row
            newKeyRow = {}

            # Use the temp timestamp as the "id"
            newKeyRow[T_ID_COL] = lastTs

            # Cut off the last interval so as to not mess with future intervals
            nextTs = min(lastTs + ONE_UNIT, nextEndTs)

            # Calculate the relative size of the current unit
            curSize = (nextTs - lastTs).total_seconds() / (numUnits * UNIT_TO_SEC_FACTOR)

            # Add in its share of the value
            newKeyRow[T_DATA_COL] = value * curSize

            # Add the row in
            curKeyRows.append(newKeyRow)

            # Increment the tempTs
            #lastTs += ONE_UNIT
            lastTs = nextTs


        # Generate a bunch of intervals of random lengths
        # and use their size to determine their value

        lastIntervalTs = curStartTs
        nextIntervalTs = None
        curSampleRows = []
        minIntervals = 4
        while lastIntervalTs < nextEndTs:

            # Initialize a new row
            newSampleRow = {}

            # Get the next endpoint based on a random number of mins
            # We should have multiple intervals per chunk
            numMins = random.randint(1, int((UNIT_TO_SEC_FACTOR / 60.) * numUnits / minIntervals))


            # Cut off the last interval so as to not mess with future intervals
            nextIntervalTs = min(lastIntervalTs + pd.Timedelta(numMins, unit=TID.MINUTE.value), nextEndTs)
            numMins = (nextIntervalTs - lastIntervalTs).total_seconds() / 60.

            # Form the interval
            curInterval = pd.Interval(left=lastIntervalTs, right=nextIntervalTs)
            newSampleRow[T_INTERVAL_COL] = curInterval

            # Calculate the value as a fraction of the total time
            newSampleRow[T_DATA_COL] = value * (numMins / (numUnits * (UNIT_TO_SEC_FACTOR / 60.)))

            # Add the row
            curSampleRows.append(newSampleRow)

            # Increment the counter
            lastIntervalTs = nextIntervalTs
        
        # Sanity checks:

        # The total value should match the original
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curKeyRows]))
        assert math.isclose(value, sum([row[T_DATA_COL] for row in curSampleRows]))

        # Make sure each interval value is realistic
        for row in curSampleRows:
            assert row[T_DATA_COL] <= (value * (1./minIntervals))

        
        # Add the rows to their respective lists
        answerKeyRows.extend(curKeyRows)
        sampleRows.extend(curSampleRows)

        # Increment the counter
        curStartTs = nextEndTs

    # Make them into dataframes
    answerKeyDf = pd.DataFrame(data=answerKeyRows)
    sampleDf = pd.DataFrame(data=sampleRows)

    # Final sanity check: the totals should match
    assert math.isclose(answerKeyDf[T_DATA_COL].sum(), sampleDf[T_DATA_COL].sum())

    return sampleDf, answerKeyDf

def GenerateSTSample(startTs: pd.Timestamp, endTs: pd.Timestamp,
                     tUnit: TID = TID.HOUR,
                     load: bool = True,
                     overwrite: bool = True,
                     relTol: float = .00001):

    # Form a spatial dataframe based on Rhode Island ZCTA codes
    # RI only has 5 counties
    STATE_FIPS = "44"
    parentDir = Path("./data/tiger")

    # Let's just get county and ZCTA information
    countyGdf = LoadShapefile(parentDir, 'county')
    countyGdf = countyGdf[countyGdf['STATEFP'] == STATE_FIPS]

    zctaGdf = LoadShapefile(parentDir, 'zcta')

    # Not exactly just RI, but close enough
    zctaGdf = zctaGdf[zctaGdf['GISJOIN'].str.contains('G028') | 
                      zctaGdf['GISJOIN'].str.contains('G029')]

    zctaSeries = zctaGdf['GISJOIN']

    # For each ZCTA, generate a random temporal sample
    allSamples = []
    allAnswerKeys = []
    for zcta in zctaSeries:

        tSampleDf, tAnswerKeyDf = GenerateTemporalSample(startTs, endTs, tUnit)

        # Copy in the zcta as a new column
        tSampleDf[ZCTA_COL] = zcta
        tAnswerKeyDf[ZCTA_COL] = zcta

        # Provide dummy geometries
        tSampleDf['geometry'] = Polygon(((0,0), (0,2), (2,2), (2,0)))
        tAnswerKeyDf['geometry'] = tSampleDf['geometry']

        # Save them
        allSamples.append(tSampleDf)
        allAnswerKeys.append(tAnswerKeyDf)

    # Concatenate all samples into two dataframes
    allSamplesDf = pd.concat(allSamples)
    allAnswerKeysDf = pd.concat(allAnswerKeys)

    # Sanity check: the sums should be the same
    assert math.isclose(allSamplesDf[T_DATA_COL].sum(), allAnswerKeysDf[T_DATA_COL].sum())

    # Now, we have data for the ZCTAs in RI between start and end timestamps

    # Construct the graph
    graphsDir = Path("./graphs")
    graph = GranularityGraph('stTest', Path('./logs/stTestGraph.log'))
    if load:
        graph.LoadGraph(graphsDir)

    if not load or len(graph) == 0:
        graph = AddLevel(graph, countyGdf, zctaGdf,
                        n1Type=GEID.COUNTY, n2Type=GEID.ZCTA)
        
        # Save, if specified
        if overwrite:
            graph.SaveGraph(graphsDir)
        
    # Get a gator object
    gator = Gator(graph, Path('./logs/stTestGator.log'))

    return allSamplesDf, allAnswerKeysDf, countyGdf, gator
