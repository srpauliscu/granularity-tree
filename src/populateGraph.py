

import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import math

from entities import *
from kGraph import Node, GranularityGraph

# Global constants
OVERLAY_AREA_COLUMN = 'Overlay_Area'

# Load a logger
if __name__ == "__main__":
    populateLogger = logging.getLogger(__name__)
    logging.basicConfig(filename="./logs/populateGraph.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    populateLogger.info("\n\n")
else:
    populateLogger = None

def AddNodes(row, curGraph: GranularityGraph, edgeType: EdgeType):

    # Form the full values dict
    v1 = {w: None for w in EdgeType}
    v2 = {w: None for w in EdgeType}

    # We're populating area this time
    v1[edgeType] = row['Shape_Area_1']
    v2[edgeType] = row['Shape_Area_2']

    # Use the GISJOIN as the id
    node1 = Node(row['GISJOIN_1'], v1, GEID.TEST)
    node2 = Node(row['GISJOIN_2'], v2, GEID.TEST)

    # Add them to the graph
    status = curGraph.AddNodes(node1, node2, edgeType, row[OVERLAY_AREA_COLUMN])

    # Check that we didn't fail
    if status != Status.SUCCESS:
        msg = f"Failed to add {node1.id}, {node2.id}."
        if populateLogger:
            populateLogger.error(msg)
        raise RuntimeError(msg)
    
    return None

def AddLevel(curGraph: GranularityGraph, 
                     gdf1: gpd.GeoDataFrame,
                     gdf2: gpd.GeoDataFrame) -> GranularityGraph:
    
    ### Step 1: Calculate the overlap area

    # Only grab needed columns
    #neededColumns = ['GISJOIN', 'GEOIDFQ', 'Shape_Area', 'geometry']
    neededColumns = ['GISJOIN', 'Shape_Area', 'geometry']
    
    gdf1 = gdf1[neededColumns]
    gdf2 = gdf2[neededColumns]

    # Do the overlay calculation
    ov = gpd.overlay(gdf1, gdf2, how="intersection", keep_geom_type=False)

    # Add the area as an extra column
    ov[OVERLAY_AREA_COLUMN] = ov.geometry.area

    # Remove false positives
    ov = ov[ov[OVERLAY_AREA_COLUMN] > 0]

    # Step 2: Add a node for each entity, using the area as the edge weight
    ov.apply(AddNodes, axis=1, args=(curGraph, EdgeType.AREA))

    return curGraph



def NationRegion(nationGdf: gpd.GeoDataFrame | None, regionGdf: gpd.GeoDataFrame):
    pass

def RegionState(regionGdf: gpd.GeoDataFrame, stateGdf: gpd.GeoDataFrame):
    pass

def StateCounty():
    pass

def CountyCity():
    pass

def CountyZip():
    pass

def CountyZCTA():
    pass

def CountyBlockGroup():
    pass

def BlockGroupBlock():
    pass

def BlockTract():
    pass

def LoadShapefile(parentDir: Path, name: str) -> gpd.GeoDataFrame:

    # Each directory will only have one shapefile,
    # but use the loop to avoid hardcoding edge cases
    shapeFileFolder = (parentDir / Path(f"{name}/")).rglob("*.shp")
    for fp in shapeFileFolder:
        return gpd.read_file(fp)
    
    raise RuntimeError(f"Files not found in {str(shapeFileFolder)}")

def main(load: bool = True, overwrite: bool = True, relTol: float = .00001):

    # Folder information
    parentDir = Path("./data/tiger")
    graphsDir = Path("./graphs")

    # Load up the graph
    graph = GranularityGraph('firstGraph', Path('./logs/firstGraph.log'))
    if load:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)


    # Only load a few files at once to limit memory usage
    regionGdf = LoadShapefile(parentDir, 'region')
    stateGdf = LoadShapefile(parentDir, 'state')

    ### Region - State ###
    msg = "Starting Region-State overlay..."
    print(msg)
    populateLogger.info(msg)

    #graph = AddLevel(graph, regionGdf, stateGdf)




    ### State - County ###
    countyGdf = LoadShapefile(parentDir, 'county')
    msg = "Starting State-County overlay..."
    print(msg)
    populateLogger.info(msg)

    # For testing, just look at alabama
    countyGdf = countyGdf[countyGdf['STATEFP'] == '01']

    #graph = AddLevel(graph, stateGdf, countyGdf)

    # Validation: the weights for each county in a state should
    # add up to the state total area

    # Group by state FIPS code
    groupedDf = countyGdf.groupby('STATEFP')
    for group in groupedDf:
        # Check a node for that state exists
        stateId = f"G{group[0]}0"
        stateNode = graph.GetNode(stateId, GEID.TEST)

        # If it does, sum the weight of every edge between
        # each county and that state
        curSum = 0
        if stateNode:
            for countyId in group[1]['GISJOIN']:
                countyNode = graph.GetNode(countyId, GEID.TEST)
                curSum += graph.GetWeight(stateNode, countyNode, EdgeType.AREA)

            # Get the original area from the stateDf
            actualArea = stateGdf[stateGdf['GISJOIN'] == stateId]['Shape_Area'].item()

            # Make sure they match closely
            assert math.isclose(curSum, actualArea, rel_tol=relTol)
                

    ### State - ZCTA ###
    zctaGdf = LoadShapefile(parentDir, 'zcta')
    msg = "Starting State-ZCTA overlay..."
    print(msg)
    populateLogger.info(msg)

    # Just use a subset for testing
    origLen = zctaGdf.shape[0]
    zctaGdf = zctaGdf.head(n=10)


    graph = AddLevel(graph, stateGdf, zctaGdf)

    # Validation: each state should be fully
    # covered by ZCTAs

    # We can't just groupBy because ZCTAs can cover multiple states
    # so we have to go through all of them

    # Get node objects for all ZCTAs
    zctaGdf['NODE_OBJ'] = zctaGdf.apply(lambda x: graph.GetNode(x['GISJOIN'], GEID.TEST), axis=1)

    # Check that we aren't testing
    if origLen == zctaGdf.shape[0]:
        for i, row in stateGdf.iterrows():

            stateId = row['GISJOIN']

            # Get the node for that state
            stateNode = graph.GetNode(stateId, GEID.TEST)

            # Iterate through all ZCTAs and add up the weights of those
            # that overlap with the given state
            curSum = 0
            for zctaNode in zctaGdf['NODE_OBJ']:
                weight = graph.GetWeight(stateNode, zctaNode, EdgeType.AREA)
                if weight:
                    curSum += weight

            # The sum should match, at least when we have all the ZCTAs
            actualArea = stateGdf[stateGdf['GISJOIN'] == stateId]['Shape_Area'].item()
            assert math.isclose(curSum, actualArea, rel_tol=relTol)

    

    ### County - Tract ###
    tractGdf = LoadShapefile(parentDir, 'tract')
    msg = "Starting County-Tract overlay..."
    print(msg)
    populateLogger.info(msg)

    # Just use Alabama tracts for testing
    tractGdf = tractGdf[tractGdf['STATEFP'] == '01']

    graph = AddLevel(graph, countyGdf, tractGdf)

    # Validation: the weights for each tract in a county
    # should add up to the county total area

    # Calculate the state + county FIPS
    tractGdf['STATECOUNTYGISJOIN'] = \
        tractGdf.apply(lambda x: f"G{x['STATEFP']}0{x['COUNTYFP']}0", axis=1)

    # Group by county FIPS code
    groupedDf = tractGdf.groupby('STATECOUNTYGISJOIN')
    for group in groupedDf:
        # Check that a node for that county exists
        countyId = group[0]
        countyNode = graph.GetNode(countyId, GEID.TEST)

        # If it does, sum the weight of every edge between
        # each tract and that county
        curSum = 0
        if countyNode:
            for tractId in group[1]['GISJOIN']:
                tractNode = graph.GetNode(tractId, GEID.TEST)
                curSum += graph.GetWeight(countyNode, tractNode, EdgeType.AREA)
            
            # Get the original area from the countyDf
            actualArea = countyGdf[countyGdf['GISJOIN'] == countyId]['Shape_Area'].item()

            # Make sure they match closely
            assert math.isclose(curSum, actualArea, rel_tol=relTol)



    ### Tract - Block Group ###
    blockGroupGdf = LoadShapefile(parentDir, 'blockGroup')
    msg = "Starting Tract-Block group overlay..."
    print(msg)
    populateLogger.info(msg)

    # For testing, just look at alabama
    blockGroupGdf = blockGroupGdf[blockGroupGdf['STATEFP'] == '01']

    #graph = AddLevel(graph, tractGdf, blockGroupGdf)



    # Validation

    # Calculate the state + county + tract FIPS
    blockGroupGdf['SCTGISJOIN'] = \
        blockGroupGdf.apply(lambda x: f"G{x['STATEFP']}0{x['COUNTYFP']}0{x['TRACTCE']}", axis=1)
    

    # Group by full tract GISJOIN
    groupedDf = blockGroupGdf.groupby('SCTGISJOIN')
    for group in groupedDf:
        # Check that a node for that tract exists
        tractId = group[0]
        tractNode = graph.GetNode(tractId, GEID.TEST)

        # If it does, sum the weight of every edge
        # between each block group and that tract
        curSum = 0
        if tractNode:
            for bgId in group[1]['GISJOIN']:
                bgNode = graph.GetNode(bgId, GEID.TEST)
                curSum += graph.GetWeight(tractNode, bgNode, EdgeType.AREA)
            
            # Get the original area
            actualArea = tractGdf[tractGdf['GISJOIN'] == tractId]['Shape_Area'].item()

            # Make sure they match closely
            assert math.isclose(curSum, actualArea, rel_tol=relTol)
    


    ### Block Group - Block ###
    blockGdf = LoadShapefile(parentDir, 'block')
    msg = "Starting Tract-Block group overlay..."
    print(msg)
    populateLogger.info(msg)

    # For testing, just look at Alabama
    print(blockGdf.head())
    return
    blockGdf = blockGdf[blockGdf['STATEFP'] == '01']

    if overwrite:
        graph.SaveGraph(graphsDir)



    return

    #stateGdf = stateGdf[stateGdf['GISJOIN'] == "G120"]


    tractGdf = LoadShapefile(parentDir, 'tract')
    #print(tractGdf)

    cityGdf = LoadShapefile(parentDir, 'city')

    schoolGdf = LoadShapefile(parentDir, 'school')

    return

    graph = AddLevel(graph, stateGdf, countyGdf)

    if overwrite:
        graph.SaveGraph(graphsDir)


    return


    #RegionState(regionGdf, stateGdf)



    countyGdf = gpd.read_file(parentDir / Path("./county/US_county_2023.shp"))
    print(countyGdf.head(n=5))
    #countyGdf.plot()



    zctaGdf = gpd.read_file(parentDir / Path("./zcta/US_zcta_2023.shp"))
    # Rename the GEOIDFQ column to match the others
    zctaGdf = zctaGdf.rename({"GEOIDFQ20": "GEOIDFQ"})

    print(zctaGdf.head(n=5))

    tractGdf = gpd.read_file(parentDir / Path("./tract/US_tract_2023.shp"))
    print(tractGdf.head(n=5))

    

    #ov = gpd.overlay(nationGdf, countyGdf.head(n=1), how="intersection")
    #ov = gpd.overlay(stateGdf.head(n=1), countyGdf.head(n=70), how="intersection")
    

    #print(ov.head())
    #print(ov.geometry.area)


if __name__ == "__main__":
    main()