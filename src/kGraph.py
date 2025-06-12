


import numpy as np
import logging
import json
from pathlib import Path

from entities import *

class Node(object):

    """

    Class that represents a unique node for a given entity in the graph.
    
    """

    def __init__(self, _id: str, _values: dict[EdgeType, float] | None, _entityType: StrEnum):


        #: str: a globally unique ID
        # (e.g. for spatial data, the GISJOIN value as defined by NHGIS)
        self.id = _id 

        #: dict: kv pairs for data used to calculate edge weights
        self.values = _values

        #: StrEnum: An enum that says what this node represents (e.g. CITY, HOUR, etc.)
        self.entityType = _entityType

    pass

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, value) -> bool:
        """
        Determine if two nodes reference the same entity.

        Args:
            self (Node): This node object.
            value (Node): The node to compare against.
        
        Returns:
            bool: True if the two nodes reference the same entity.
        """

        # ID match should be enough, but use entityType as reassurance
        return self.id == value.id and self.entityType == value.entityType
    

class FusionPath(object):

    """
    Class that holds the instructions for how to get from one
        set of nodes to another.  Handles both aggregation and
        deaggregation.
    
    """

    def __init__(self):

        #: Node: The origin node.
        self.source = None

        #: Node: The destination node.
        self.destination = None

        #: list[Node]: 
        pass

class GranularityGraph(object):

    """
    Class that handles all nodes and edges as well as aggregation,
    deaggregation, and pathfinding for fusion processes.

    Invariants:
        Each unique entity has exactly one node.  Note that counties with the same name
            in different states are unique and would need unique nodes, eg.  In other words,
            the path from the root to each node must be unique, ignoring edge weights/labels.
        The graph is stored as a symmetric matrix, so if i,j exists, j,i must also exist and match.
    """

    def __init__(self, _name: str, logFile: Path):

        """
        Each entry in the adjacency matrix is the weight, and there
        is a matrix for each weight type.  This allows us
        to use numpy arrays for the matrices.

        """

        #: str: The name of this graph
        self.name = _name

        #: int: The current dimensions of the adj matrices
        self.maxSize = 8

        #: int: The number of valid rows/columns in the adj matrices
        self.size = 0

        #: dict[EdgeWeight: np.array]: The adjacency matrices
        self.graphs = {w: np.zeros((self.maxSize, self.maxSize)) for w in EdgeType}

        # Initialize them with None to identify invalid accesses
        #for k in self.graphs:
        #    self.graphs[k][:] = None

        #: dict[Node: int]: A map from node object to array index
        self.indexMap = {}

        #: logging.Logger: A logging object
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=str(logFile), encoding='utf-8', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        self.logger = logger

    def __len__(self):
        # Returns number of nodes
        return len(self.indexMap)


    def NodeExists(self, node: Node) -> bool:
        return node in self.indexMap

    '''
    def EdgeExists(self, edge: Edge):
        # Get both nodes of the edge
        n1 = edge.n1
        n2 = edge.n2

        # Check that both nodes exist
        if not self.NodeExists(n1) or not self.NodeExists(n2):
            return False
        
        # Check that there is an edge object there
        if 


        pass
    '''

    def EdgeExists(self, n1: Node, n2: Node, edgeType: EdgeType) -> bool:

        """
        Check if an edge exists between n1 and n2 of the specified type
        """

        # Check that both nodes exist
        if not self.NodeExists(n1) or not self.NodeExists(n2):
            return False
        
        # Check that there exists an edge of that type
        adjMat = self.graphs[edgeType]             
        n1i = self.indexMap[n1]
        n2i = self.indexMap[n2]

        # Check for symmetry (internal sanity check)
        if not adjMat[n1i, n2i] == adjMat[n2i, n1i]:
            msg = f'Matrix symmetry broken at {n1i},{n2i}\n{adjMat}'
            self.logger.error(msg)
            raise RuntimeError(msg)

        return not adjMat[n1i, n2i] == 0
    
    def GetWeight(self, n1: Node, n2: Node, edgeType: EdgeType):
        """
        Get the weight for the edge between the two nodes, if it exists
        """

        # Check that the edge exists
        if not self.EdgeExists(n1, n2, edgeType):
            #self.logger.warning(f"Tried to access {n1.id} - {n2.id} but failed.")
            return None

        adjMat = self.graphs[edgeType]
        n1i = self.indexMap[n1]
        n2i = self.indexMap[n2]

        return adjMat[n1i, n2i]


    def AddNode(self, newNode: Node) -> Status:

        """
        Function to add a new, unconnected Node to the graph
        Args:
            self (GranularityGraph): This graph.
            newNode (Node): The node to be added.

        Returns:
            Node: A reference to the new node object.
        
        """

        try:
            # Check if the node exists already
            if self.NodeExists(newNode):
                return Status.EXISTS
            
            # Add the new node to the array, resizing as needed
            if self.size == self.maxSize:

                # Pad the existing arrays with Nones, doubling the size
                for k in self.graphs:
                    print(self.graphs[k])
                    self.graphs[k] = np.pad(self.graphs[k], (0, self.maxSize), mode='constant', constant_values=0)

                # Record the new max size
                self.maxSize *= 2
                
            # Assign the current size as the index of the new node
            self.indexMap[newNode] = self.size

            # Update the valid size
            self.size += 1

            return Status.SUCCESS

            
        except Exception as e:
            self.logger.error(e)
            return Status.ERROR

    def UpdateEdge(self, n1: Node, n2: Node,  edgeType: EdgeType, weight: float) -> Status:

        """
        Add or update an edge between two nodes that already exist in the tree.

        Args:
            self (GranularityGraph): This graph.
            n1 (Node): The first node.
            n2 (Node): The second node.
            weight (float): The weight of the new edge.
            edgeType (EdgeType): The type of the new edge.
        
        """

        try:

            # Check that both nodes exist
            if not self.NodeExists(n1) or not self.NodeExists(n2):
                return Status.NOTEXISTS
            
            # Get their indices
            n1i = self.indexMap[n1]
            n2i = self.indexMap[n2]

            # If the indices match but the nodes aren't equal, error
            if (not n1 == n2) and n1i == n2i:
                msg = f"Nodes {n1.id} and {n2.id} were assigned same index."
                raise RuntimeError(msg)


            # Update both i,j and j,i to maintain symmetry
            adjMat = self.graphs[edgeType]
            adjMat[n1i, n2i] = weight
            adjMat[n2i, n1i] = weight

            # Make sure the graph is saved again
            self.graphs[edgeType] = adjMat

        except Exception as e:
            self.logger.error(e)
            return Status.ERROR
        
        
        return Status.SUCCESS
    

    def AddNodes(self, n1: Node, n2: Node, edgeType: EdgeType, weight: float) -> Status:

        # Use existing nodes if possible, otherwise add them
        if not self.NodeExists(n1):
            status = self.AddNode(n1)
            if status != Status.SUCCESS:
                self.logger.warning(f"Tried to add node {n1.id} but failed with status {status}")
                return status
            
        if not self.NodeExists(n2):
            status = self.AddNode(n2)
            if status != Status.SUCCESS:
                self.logger.warning(f"Tried to add node {n2.id} but failed with status {status}")
                return status
            
        # Call update edge
        return self.UpdateEdge(n1, n2, edgeType, weight)


    
    def SaveGraph(self, parentDir: Path):

        try:

            # We need to flatten the object
            resDict = {}

            # Save the individual stats
            resDict['maxSize'] = self.maxSize
            resDict['size'] = self.size

            # Need to save the info from each node separately
            resDict['indexMap'] = {}
            for node in self.indexMap:
                resDict['indexMap'][self.indexMap[node]] = node.__dict__

            # Make the folder, if needed
            saveDir = parentDir / Path(self.name)
            if not saveDir.exists():
                saveDir.mkdir(parents=True)

            # We need to save each numpy matrix as its own file
            graphFiles = {}
            for k in self.graphs:

                # Use the type to form the filename
                # TODO: May need to access k.value directly
                curFilepath = saveDir / Path(k.value)

                # Save the array out
                np.save(curFilepath, self.graphs[k])

                # Save the filepath
                # TODO: May need to access k.value directly
                graphFiles[k.value] = str(curFilepath)

            # Put the filenames in the final file
            resDict['graphFilenames'] = graphFiles

            # Dump the dict to a json
            with open(saveDir / Path('main.json'), "w") as f:
                json.dump(resDict, f)
            


        except Exception as e:
            self.logger.error(e)
            raise e
        
    def LoadGraph(self, parentDir: Path) -> Status:

        # Function to load a graph from files

        # First, check that the folder for this graph exists
        saveDir = parentDir / Path(self.name)
        if not saveDir.exists():
            return Status.NOTEXISTS
        
        try:

            # Grab the main file first
            with open(saveDir / Path('main.json'), 'r') as f:
                mainDict = json.load(f)

            # Get the main parameters
            self.maxSize = mainDict['maxSize']
            self.size = mainDict['size']

            # Need to instantiate node objects manually
            indexMap = mainDict['indexMap']
            self.indexMap = {}
            for matIndex in indexMap:

                # Instantiate blank node object
                newNode = Node("", None, None)

                # Load all member variables
                for k in indexMap[matIndex]:
                    newNode.__dict__[k] = indexMap[matIndex][k]
                
                # Go through the values and instantiate EdgeType objects
                newVals = {EdgeType(w): newNode.values[w] for w in newNode.values}
                newNode.values = newVals

                # Add it to the final indexMap
                self.indexMap[newNode] = int(matIndex)

            # Load the graphs from the files
            graphFiles = mainDict['graphFilenames']
            self.graphs = {}
            for k in graphFiles:
                # Instantiate as Paths to avoid any weirdness
                fileName = Path(graphFiles[k] + '.npy')
                graph = np.load(fileName)

                # Put it in the main graphs dict
                self.graphs[EdgeType(k)] = graph
                 

        
        except Exception as e:
            self.logger.error(e)
            return Status.ERROR
        
        return Status.SUCCESS



    def RemoveNode(self, node: Node) -> None:

        """
        Delete an existing node and all of its edges.
        
        """
        
        raise NotImplementedError
    
    def GetMatches(self, source: Node, destNodes: list[Node], edgeType: EdgeType) -> dict[Node, float]:

        """
        Check destNodes for all matches with source and return the weights of the matches.
        
        """

        output = {}
        for dn in destNodes:
            weight = self.GetWeight(source, dn, edgeType)
            if not weight is None:
                output[dn] = weight

        return output

    def FindMatches(self, source: Node, destType: GEID | TID, edgeType: EdgeType) -> dict[Node, float]:

        """
        For the given node, find all nodes of the desired type that the source node
        has a connection with (i.e. an edge exists).

        There may be multiple (i.e. a ZIP code crossing state lines) - return all matching nodes
        
        """

        # Make sure the node exists
        if not self.NodeExists(source):
            self.logger.warning(f"Tried to find matches for {source} but it doesn't exist.")
            return None

        # Grab the index and graph for this node and edgeType
        sourceI = self.indexMap[source]
        adjMat = self.graphs[edgeType]

        # Go through all other nodes and check if a weight exists
        destNodes = {}
        for n in self.indexMap:
            # Skip when the nodes are the same
            if n == source:
                continue

            # Check that the node is the correct type
            if not n.entityType == destType:
                continue

            # Check if the weight is non-zero
            if adjMat[sourceI, self.indexMap[n]] > 0:
                destNodes[n] = adjMat[sourceI, self.indexMap[n]]

        return destNodes
    
'''


    def FindPaths(self, sources: list[Node], destinations: list[Node]):

        # Check that all nodes in each list are the same entity type
        for i in range(len(sources) - 1):
            if sources[i].entityType != sources[i+1].entityType:
                msg = f"Each node in the source list must be the same entityType, \
                    but nodes {i} and {i+1} aren't."
                self.logger.error(msg)
                raise RuntimeWarning(msg)
            
        for i in range(len(destinations) - 1):
            if destinations[i].entityType != destinations[i+1].entityType:
                msg = f"Each node in the destination list must be the same entityType, \
                    but nodes {i} and {i+1} aren't."
                self.logger.error(msg)
                raise RuntimeWarning(msg)

        """
        This function needs to do the following:
            For each node in sources, find the shortest path to one of the nodes in the destination.
            Use the inverse of the weights as the edge weights for e.g. Dijkstra's Algorithm.  Thus, the
            'shortest' path would be the one with the most overlap.  The overlap is calculated as a fraction
            as compared to the smallest of the two nodes in question.

            Example:
                The city of Chicago has an area of 234 sq miles and is contained entirely within the
                state of Illinois, which has an area of ~58,000 sq miles.
                Their weight on the graph would be 234, since Chicago is entirely inside Illinois.
                For the weight for shortest path, it would be 1 / (234/234) = 1, which is the cheapest
                possible path between two nodes.

            Then, depending on which is the smaller area (current node or next node), we aggregate or deaggregate

            TODO: Just make each edge weight the overlapping area / smaller area of the two nodes.  From this,
            we can calculate anything
        
            Note: Instead, we can do a "fully connected" graph such that if there is any overlapping between two
            entities, the weight between them in the graph reflects that, even if it skips granularity levels.
            For example, say a ZIP code crosses a state line.  Even though there are levels of granularity between
            state and ZIP (e.g. county), we can just aggregate directly.  This removes any concept of a 'tree', as
            there will no longer be levels of granularity.

            Instead, the bigger problem is:
                For aggregation, we need to determine if we can fully cover an entity through unions of mutually
                    exclusive entities (e.g. can we count for 100% of Illinois by combining ZIP codes?)
                For deaggregation, we need to find the other entities that match the target's EntityType so we can
                estimate each entity (e.g. we have data for all of Illinois, but we need data by ZIP code)
        
        """





    def FindPath(self, source: list[Node] | Node, destination: Node | list[Node]) -> list[StrEnum]:
        
        """
        Function that calculates the steps to get from source to destination, returning the IDs.

        Example: source is list[GEID.Tracts], destination is GEID.State -> return value
            would be [GEID.Tracts, GEID.County, GEID.State]
        
        Args:
            self (GranularityGraph): This graph.
            source: Either a list of nodes to start from (for aggregation, of which we pick one) or a
                single node (deaggregation).
            destination: Either a single node (for aggregation) or a list of nodes (for deaggregation,
                of which we pick one).
        
        Returns:
            list: An ordered sequence of IDs denoting the steps to get from source to destination.
        """

        """
        Steps:
            1.) Locate either one node of the list of sources or the sole source node in the graph.
            2.) Check the root path to see if the destination is in the path.
            3.) If yes, cut out the IDs, put them in a list, and return.
            4.) If no, use Dijkstra's algorithm to find the best path from source to destination,
                using the inverse edge weight as the weights.  The resulting path will require the
                least amount of guessing (i.e. making as few estimations as possible without 100% of
                a given entity).
        """

        pass

    def PerformFusion(self, source: list[Entity] | Entity, destination: Entity | list[Entity]) -> Entity | list[Entity]:

        """
        Function that takes in entities and calculates the value of interest for the destination.

        Args:
            self (GranularityGraph): This graph.
            source: Either a list of entities to aggregate up from or a single
                entity to deaggregate down from.
            destination: Either a single entity to aggregate up to or a list
                of entities to deaggregate down to.

        Returns:
            Entity: The destination entity with a calculated value.
            OR
            list[Entity]: All destination entities with calculated values.
        """
        

        """
        Steps:
            1.) Identify the path to get from source(s) to destination(s).
            2.) Base case: if the path is one step (i.e. ZIP -> County), we can actually do
                the calculation and return the destination's value.
            3.) Recursive case: If the path is more than one step, break it down into individual,
                one step conversions, and call this function on them.
            
            Example: Say we want to calculate total COVID cases in the state of Illinois but only have
                tract level data.
                1.) Calculate the path: Tract -> County -> State
                2.) Path is longer than one step, so break it down into Tract -> County and County -> State
                3.) Call this function on each step individually and sequentially to calculate the final value
        """
''' 

# Dead simple test
def main():

    graph = GranularityGraph('test', Path('./logs/test.log'))

if __name__ == "__main__":
    main()



