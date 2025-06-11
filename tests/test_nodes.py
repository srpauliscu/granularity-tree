
from pathlib import Path

import pytest
import numpy as np

from samples import ResetForTest, TEST_GRAPH_NAME, HashWeight

# kGraph imports the entities, so we only need to import kGraph
from src.kGraph import *

np.set_printoptions(precision=1)


@pytest.mark.basic
def testNodeBasic():

    # Extremely basic test, just to make sure things don't break
    # as new stuff is added

    sampleSize = 10
    nodes = []
    for i in range(sampleSize):

        n = Node('node{i}', {EdgeType.AREA: i}, GEID.TEST)
        nodes.append(n)

    # Make sure the equality function works
    for i in range(sampleSize):
        assert nodes[i] == nodes[i]

    

    