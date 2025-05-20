


import numpy as np


from entities import *


import logging


class Entity(object):

    """
    Class for storing data in specific entities, forms the basis of the aggregation/deaggregation chain

    
    """

    def __init__(self) -> 'Entity':

        #: StrEnum: The id of the entity (currently a GEID or TID)
        self.id = None

        #: str: The name for this instance (e.g. "Illinois")
        self.name = None

        #: int: The value of interest (e.g. number of people with COVID)
        # Remains None if unknown
        self.value = None





class Node(object):

    """

    Class that represents a unique node for a given entity in the graph.

    Invariants:


    
    
    """

    def __init__(self) -> 'Node':


        #: list[DEdge]
        self.edges = None

        #: StrEnum (either GEID or TID for now)
        self.id = None

        #: str: Full chain of nodes from root to this one.  Not unique.
        self.path = None

        #: dict: kv pairs for data used to calculate edge weights
        self.values = None

    pass

    def __eq__(self, value: 'Node') -> bool:
        """
        Determine if two nodes reference the same entity.

        Args:
            self (Node): This node object.
            value (Node): The node to compare against.
        
        Returns:
            bool: True if the two nodes reference the same entity.
        """

        return self.path == value.path
    

class Edge(object):

    """
    Class that represents an undirected edge between two nodes.

    Invariants:
        The variables with specified types must always be those types or None.
        Weights must be >= 0.
    """

    def __init__(self, _n1: Node, _n2: Node) -> 'Edge':

        #: Node: One node of this edge
        self.n1 = _n1
        
        #: Node: The second node of this edge
        self.n2 = _n2

        #: dict: The set of weights that can be used for this edge
        self.weights = {}

        #: logging.logger
        self.logger = logging.getLogger(__name__)

        if not self.__CheckInvariants():
            raise RuntimeError("Cannot instantiate edge with given parameters.")


    def AddWeight(self, weightType: EdgeWeight, weight: float) -> None:

        """
        Add a new weight for this edge.

        Args:
            self (Edge): This edge.
            weightType (EdgeWeight): The type of the new weight.
            weight (float): The weight to be added.

        """

        # Overwrite the weight if it already exists
        self.weights[weightType] = weight

    def GetWeight(self, weightType: EdgeWeight) -> float:
        return self.weights[weightType]    
    
    def __CheckInvariants(self) -> bool:

        """
        Function that should be called whenever a change is made to ensure
        that the class invariants still hold true.
        """
        for w in self.weights:
            if w < 0:
                return False

        
        return True

class FusionPath(object):

    """
    Class that holds the instructions for how to get from one
        set of nodes to another.  Handles both aggregation and
        deaggregation.
    
    """

    def __init__(self) -> 'FusionPath':

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

    def __init__(self) -> 'GranularityGraph':

        """
        Each entry in the adjacency matrix is an Edge object that stores
        all known weights for that edge.  Essentially a dict of weights.

        """
        #: int: The current dimensions of the adj matrix
        self.maxSize = 8

        #: int: The number of valid rows/columns in the adj matrix
        self.size = 0

        #: np.array: The adjacency matrix
        self.graph = np.zeros(self.maxSize)

        #: dict: A map from node object to array index
        self.indexMap = {}



    def NodeExists(self, node: Node):
        return node in self.indexMap

    def EdgeExists(self, edge: Edge):
        # Get both nodes of the edge
        n1 = edge.n1
        n2 = edge.n2

        # Check that both nodes exist
        if not n1 in self.indexMap or not n2 in self.indexMap:
            return False
        
        # Check that there is an edge object there
        if np


        pass

    def AddNode(self, newEntity: StrEnum, existingNode: Node, weight: float) -> Node:

        """
        Function to add a new entity to the graph by creating an edge to the existing node with the given weight.

        Args:
            self (GranularityGraph): This graph.
            newNode (StrEnum): The name of the entity to be added.
            existingNode (Node): The node that exists in the graph to connect the new node to
            weight (float): The weight of the edge.

        Returns:
            Node: A reference to the new node object.
        
        """

    def AddEdge(self, n1: Node, n2: Node, weight: float) -> bool:

        """
        Add an edge between two nodes that already exist in the tree.

        Args:
            self (GranularityGraph): This graph.
            n1 (Node): The first node.
            n2 (Node): The second node.
            weight (float): The weight of the new edge
        
        
        """
        
        pass

    def RemoveNode(self, node: Node) -> None:

        """
        Delete an existing node and all of its edges.
        
        """
        
        raise NotImplementedError








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





