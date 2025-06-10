

# Contains hard-coded node samples for testing

# Import block
from src.entities import *
from src.kGraph import *
import pytest
from pathlib import Path
import shutil
from collections.abc import Callable

TEST_GRAPH_NAME = 'testGraph'

def BasicWeight(i, j, wm):
    return min(i,j) * wm

def HashWeight(i, j, wm):
    return hash((min(i,j), max(i, j)))

# Function to make the samples
def MakeTestSamples(sampleSize: int, weightModifier: float, WeightCalc: Callable):

    # Make the nodes programatically for testing
    sampleNodes = [Node(f"node{i}", {w: i for w in EdgeType}) for i in range(sampleSize)]

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
    shutil.rmtree(graphSaveDir)

    # Get the samples
    sampleNodes, sampleGraphs = MakeTestSamples(sampleSize, weightModifier)

    # Clear the log file if it exists
    logfile = Path(f"./logs/{testName}.log")
    if logfile.exists():
        logfile.unlink()
    
    # Instantiate the graph
    kGraph = GranularityGraph(TEST_GRAPH_NAME, logfile)

    return sampleNodes, sampleGraphs, kGraph
