
from pathlib import Path

import pytest
import numpy as np

from samples import ResetForTest, TEST_GRAPH_NAME, HashWeight

# kGraph imports the entities, so we only need to import kGraph
from src.kGraph import *

np.set_printoptions(precision=1)

@pytest.mark.basic
def testAddBasic():

    # Reset for the test
    sampleSize = 10
    sampleNodes, sampleGraphs, kGraph = ResetForTest(sampleSize, 1, 'testAddBasic')

    # Check the default sizes
    assert kGraph.size == 0
    assert len(kGraph) == 0
    assert kGraph.maxSize == 8

    # Go ahead and add one node at a time
    for i, node in enumerate(sampleNodes):
        status = kGraph.AddNode(node)
        print(id(status))
        print(id(Status.SUCCESS))
        assert status == Status.SUCCESS
        assert len(kGraph) == i + 1

    # We've added 10 nodes, so the sizes should reflect that
    assert kGraph.size == 10
    assert len(kGraph) == 10
    assert kGraph.maxSize == 16

    # Make sure the nodes exist
    for node in sampleNodes:
        assert kGraph.NodeExists(node)

    
    # Try to re-add the same nodes
    for node in sampleNodes:
        status = kGraph.AddNode(node)
        assert status == Status.EXISTS

    # Make sure the graph hasn't changed size
    assert kGraph.size == 10
    assert len(kGraph) == 10
    assert kGraph.maxSize == 16

def testMultiAddBasic():

    # Reset for the test
    sampleSize = 10
    sampleNodes, sampleGraphs, kGraph = ResetForTest(sampleSize, 1, 'testMultiAddBasic')

    # Check the default sizes
    assert kGraph.size == 0
    assert len(kGraph) == 0
    assert kGraph.maxSize == 8

    # Use AddNodes to add the first 6 nodes, in distinct pairs
    # Edge weight doesn't matter, they're tested elsewhere
    i = 0
    while i < 6:

        # Get the nodes
        n1 = sampleNodes[i]
        n2 = sampleNodes[i + 1]

        # Try and add them
        status = kGraph.AddNodes(n1, n2, EdgeType.AREA, 1)
        assert status == Status.SUCCESS

        # Step size of 2
        i += 2
        assert len(kGraph) == i

    # Add the rest in non-distinct pairs, to test that we
    # check if they exist or not
    while i < sampleSize:

        # Get the nodes.  Swap them to test
        # that both args are checked
        if i % 2 == 0:
            n1 = sampleNodes[int(i / 2.)]
            n2 = sampleNodes[i]
        else:
            n1 = sampleNodes[i]
            n2 = sampleNodes[int(i / 2.)]

        status = kGraph.AddNodes(n1, n2, EdgeType.AREA, 1)
        assert status == Status.SUCCESS

        # Step size of 1 this time
        i += 1
        assert len(kGraph) == i

    # Make sure all of them were added
    for node in sampleNodes:
        assert kGraph.NodeExists(node)
    
    # Make sure the size matches expectations
    assert kGraph.size == sampleSize
    assert len(kGraph) == sampleSize

@pytest.mark.basic
def testEdgeBasic():

    # Reset for the test, using a hash to make sure
    # we have the correct weights
    sampleSize = 10
    sampleNodes, sampleGraphs, kGraph = \
        ResetForTest(sampleSize, 1, 'testEdgeBasic', HashWeight)

    # Add all but one node to the graph, using the correct weights
    # Make it fully connected
    edgeType = EdgeType.AREA
    for i in range(sampleSize - 1):

        # Get the first node
        n1 = sampleNodes[i]

        for j in range(sampleSize - 1):
            
            # Skip the diagonal
            if i == j:
                continue

            # Get the second node
            n2 = sampleNodes[j]

            # Get their sample weight
            weight = sampleGraphs[edgeType][i, j]

            # Try and add them
            status = kGraph.AddNodes(n1, n2, edgeType, weight)
            assert status == Status.SUCCESS
    
    # Make sure they were all added
    assert len(kGraph) == sampleSize - 1

    # Check that all the edges exist
    for i in range(sampleSize - 1):

        # Get the first node
        n1 = sampleNodes[i]

        for j in range(sampleSize - 1):

            # Skip the diagonal
            if i == j:
                continue

            # Get the second node
            n2 = sampleNodes[j]

            assert kGraph.EdgeExists(n1, n2, edgeType)
            assert kGraph.EdgeExists(n2, n1, edgeType)

            # Make sure they only exist for the AREA edge type
            assert not kGraph.EdgeExists(n1, n2, EdgeType.POPULATION)

    # Test that the EdgeExists gets the true negatives too
    lastNode = sampleNodes[sampleSize - 1]
    for i in range(sampleSize - 1):
        n = sampleNodes[i]
        assert not kGraph.EdgeExists(n, lastNode, edgeType)
        assert not kGraph.EdgeExists(lastNode, n, edgeType)

        # Make sure GetWeight also handles this correctly
        assert kGraph.GetWeight(n, lastNode, edgeType) is None
        assert kGraph.GetWeight(lastNode, n, edgeType) is None

    
    # Make sure the existing weights match
    for i in range(sampleSize - 1):
        
        # Get the first node
        n1 = sampleNodes[i]

        for j in range(sampleSize - 1):

            # Skip the diagonal
            if i == j:
                continue

            # Get the second node
            n2 = sampleNodes[j]

            # Make sure the graph is symmetric
            weight1 = kGraph.GetWeight(n1, n2, edgeType)
            weight2 = kGraph.GetWeight(n2, n1, edgeType)
            assert weight1 == weight2

            # Make sure the correct weight was stored
            assert weight1 == sampleGraphs[edgeType][i, j]


@pytest.mark.checkpointing
def testSaveLoad():

    # Reset and get samples and a graph object
    # Use hash weights to make sure the arrays are preserved
    sampleSize = 50
    sampleNodes, sampleGraphs, kGraph = ResetForTest(sampleSize, 1, 'SaveLoad', HashWeight)

    # Add all the nodes with their weights
    edgeType = EdgeType.AREA
    for i in range(sampleSize):

        # Get the first node
        n1 = sampleNodes[i]

        # Only need one half of the matrix
        for j in range(i + 1, sampleSize):
            
            # Get the second node
            n2 = sampleNodes[j]

            # Get the weight
            weight = sampleGraphs[edgeType][i, j]

            # Add the nodes
            status = kGraph.AddNodes(n1, n2, edgeType, weight)
            assert status == Status.SUCCESS

    # Save out the graph
    saveDir = Path("./graphs")
    kGraph.SaveGraph(saveDir)

    # Load the graph into a new object
    loadedKGraph = GranularityGraph(TEST_GRAPH_NAME, Path('./logs/loadedGraphTest.log'))
    loadedKGraph.LoadGraph(saveDir)

    # Go through and check that all of the simple member variables match
    assert kGraph.name == loadedKGraph.name
    assert kGraph.size == loadedKGraph.size
    assert kGraph.maxSize == loadedKGraph.maxSize

    # Check the node map node-by-node
    for n in kGraph.indexMap:
        assert n in loadedKGraph.indexMap
        assert kGraph.indexMap[n] == loadedKGraph.indexMap[n]
    
    # Check that the lists are one-to-one
    for n in loadedKGraph.indexMap:
        assert n in kGraph.indexMap

    # Check each graph individually
    for w in kGraph.graphs:
        assert w in loadedKGraph.graphs
        assert (kGraph.graphs[w] == loadedKGraph.graphs[w]).all()

    # Also check that the graphs are one-to-one
    for w in loadedKGraph.graphs:
        assert w in kGraph.graphs

    

        

    



        



