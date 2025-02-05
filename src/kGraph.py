





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


class DEdge(object):

    """
    Class that represents a directed edge between two nodes.

    Invariants:
        self.weight must be between 0 and 1, inclusive, or None.
        The variables with specified types must always be those types or None.
    """

    def __init__(self) -> 'DEdge':

        #: Node: The origin node of this edge.
        self.source = None
        
        #: Node
        self.destination = None

        #: float
        self.weight = None

        #: EdgeWeight
        self.label = None

        #: logging.logger
        self.logger = logging.getLogger(__name__)


    
    def __CheckInvariants(self) -> bool:

        """
        Function that should be called whenever a change is made to ensure
        that the class invariants still hold true.
        """

        pass


class Node(object):

    """

    Class that represents a unique node for a given entity in the graph.

    Invariants:


    
    
    """

    def __init__(self) -> 'Node':


        #: list[DEdge]
        self.outgoing = None
        
        #: list[DEdge]
        self.incoming = None

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
        The root node has no incoming edges.
        Leaf nodes have no outgoing edges.
        For each edge from node x to node y, there must be an edge going from node y to node x.
    """

    def __init__(self) -> 'GranularityGraph':

        #: Node: The 'root' node
        self.root = None

        #: list[Node]: All the nodes of this tree, excluding the root.
        self.nodes = None

        pass

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





