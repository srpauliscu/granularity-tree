

import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import logging

from entities import *
from kGraph import Node, GranularityGraph

# Global constants
OVERLAY_AREA_COLUMN = 'Overlay_Area'

# Load a logger
if __name__ == "__main__":
    populateLogger = logging.getLogger(__file__)
    logging.basicConfig(filename="./logs/populateGraph.log", encoding='utf-8', level=logging.DEBUG)
else:
    populateLogger = None

def AddNodes(row, curGraph: GranularityGraph, edgeType: EdgeType):

    # Use the GISJOIN as the id
    node1 = Node(row['GISJOIN_1'])
    node2 = Node(row['GISJOIN_2'])

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
    neededColumns = ['GISJOIN', 'GEOIDFQ', 'Shape_Area', 'geometry']
    
    gdf1 = gdf1[neededColumns]
    gdf2 = gdf2[neededColumns]

    # Do the overlay calculation
    ov = gpd.overlay(gdf1, gdf2, how="intersection", keep_geom_type=False)

    # Add the area as an extra column
    ov[OVERLAY_AREA_COLUMN] = ov.geometry.area

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

def main(load: bool = False, overwrite: bool = True):

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

    # Region - State
    msg = "Starting Region-State overlay..."
    print(msg)
    populateLogger.info(msg)

    #graph = AddLevel(graph, regionGdf, stateGdf)

    # State - County
    countyGdf = LoadShapefile(parentDir, 'county')
    msg = "Starting State-County overlay..."
    print(msg)
    populateLogger.info(msg)

    # For testing, just look at alabama
    countyGdf = countyGdf[countyGdf['STATEFP'] == '01']

    print(stateGdf[stateGdf['GISJOIN'] == "G120"])
    #print(countyGdf)

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