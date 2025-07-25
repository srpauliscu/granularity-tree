

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import math

from gator import *
from kGraph import Node, GranularityGraph
from populateGraph import AddLevel, AddNodes, LoadShapefile, OVERLAY_AREA_COLUMN

CT_FIPS = '09'

# Load a logger
if __name__ == "__main__":
    connecticutLogger = logging.getLogger(__name__)
    logging.basicConfig(filename="./logs/connecticutGraph.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    connecticutLogger.info("\n\n")
else:
    connecticutLogger = None

def LoadShapefile(parentDir: Path, name: str) -> gpd.GeoDataFrame:

    # Each directory will only have one shapefile,
    # but use the loop to avoid hardcoding edge cases
    shapeFileFolder = (parentDir / Path(f"{name}/")).rglob("*.shp")
    for fp in shapeFileFolder:
        return gpd.read_file(fp)
    
    raise RuntimeError(f"Files not found in {str(shapeFileFolder)}")

def CityIdConverter(row, cityDict: dict):

    cityName = row['Primary Customer City'].lower()
    if cityName in cityDict:
        return cityDict[cityName]
    else:
        return ""
    
def ZctaIdConverter(row, zctaDict: dict):

    zcta = row['ZCTA']
    if zcta in zctaDict:
        return zctaDict[zcta]
    else:
        return ""

def ZipZctaConverter(row, ztzDict: dict):
    
    z = row['zip']
    if z in ztzDict:
        return ztzDict[z]
    else:
        # Assume the zip == zcta
        return z

def cMain(load: bool = True, overwrite: bool = True, relTol: float = .00001):

    # Folder information
    parentDir = Path("./data/tiger")
    graphsDir = Path("./graphs")

    # Load up the graph
    graph = GranularityGraph('connecticutGraph', Path('./logs/connecticutGraph.log'))
    if load:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)

    # We only need city - zcta and zcta - county layers
    # We also need to map zip to zcta
    countyGdf = LoadShapefile(parentDir, 'county')
    countyGdf = countyGdf[countyGdf['STATEFP'] == CT_FIPS]

    cityGdf = LoadShapefile(parentDir, 'city')
    cityGdf = cityGdf[cityGdf['STATEFP'] == CT_FIPS]

    zctaGdf = LoadShapefile(parentDir, 'zcta')

    # Get the mapping from zip to zcta
    ztzGdf = gpd.read_file("./data/zipToZcta.csv")
    ztzGdf = ztzGdf[ztzGdf['STATE'] == 'CT']

    # Make a dictionary out of the two columns
    ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

    # Load the data
    evRegsGdf = gpd.read_file('./data/spatial/Electric_Vehicle_Registration_Data.csv')
    ratesGdf = gpd.read_file('./data/spatial/iou_zipcodes_2023.csv')
    ratesGdf = ratesGdf[ratesGdf['state'] == 'CT']

    # Do the conversion from zip to zcta
    ratesGdf['ZCTA'] = ratesGdf.apply(ZipZctaConverter, args=(ztzDict,), axis=1)


    # Make a city name: GISJOIN dict
    cityDict = pd.Series(cityGdf['GISJOIN'].values, index=cityGdf['NAME']).to_dict()
    # Make all the keys lowercase for consistency
    cityDictLower = {}
    for k in cityDict:
        cityDictLower[k.lower()] = cityDict[k]


    # Make a zcta: GISJOIN dict
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()

    # Add columns to each data gdf for the GISJOIN ids

    # Convert ZCTA to GISJOIN ID
    ratesGdf['GISJOIN'] = ratesGdf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)

    # Remove ZIPs we didn't have
    ratesGdf = ratesGdf[ratesGdf['GISJOIN'] != ""]

    # Converty city name to GISJOIN ID
    evRegsGdf['GISJOIN'] = evRegsGdf.apply(CityIdConverter, args=(cityDictLower,), axis=1)

    # Remove cities that we didn't have
    evRegsGdf = evRegsGdf[evRegsGdf['GISJOIN'] != ""]




    # Now, construct the graph
    msg = "Adding County-ZCTA layer..."
    print(msg)
    connecticutLogger.info(msg)
    graph = AddLevel(graph, countyGdf, zctaGdf,
                     n1Type=GEID.COUNTY, n2Type=GEID.ZCTA)

    msg = "Adding City-ZCTA layer..."
    print(msg)
    connecticutLogger.info(msg)
    graph = AddLevel(graph, cityGdf, zctaGdf,
                     n1Type=GEID.CITY, n2Type=GEID.ZCTA)

    msg = "Adding County-City layer..."
    print(msg)
    connecticutLogger.info(msg)
    graph = AddLevel(graph, countyGdf, cityGdf,
                     n1Type=GEID.COUNTY, n2Type=GEID.CITY)

    # Get a gator object
    gator = Gator(graph, Path('./logs/connecticutGator.log'))

    resDf = gator.Equalize()










    return



    # Only load a few files at once to limit memory usage
    regionGdf = LoadShapefile(parentDir, 'region')
    stateGdf = LoadShapefile(parentDir, 'state')

    ### Region - State ###
    msg = "Starting Region-State overlay..."
    print(msg)
    connecticutLogger.info(msg)

    graph = AddLevel(graph, regionGdf, stateGdf)




    ### State - County ###
    countyGdf = LoadShapefile(parentDir, 'county')
    msg = "Starting State-County overlay..."
    print(msg)
    connecticutLogger.info(msg)

    # For testing, just look at alabama
    #countyGdf = countyGdf[countyGdf['STATEFP'] == '01']

    graph = AddLevel(graph, stateGdf, countyGdf)

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
    connecticutLogger.info(msg)

    # Just use a subset for testing
    origLen = zctaGdf.shape[0]
    #zctaGdf = zctaGdf.head(n=10)


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
    connecticutLogger.info(msg)

    # Just use Alabama tracts for testing
    #tractGdf = tractGdf[tractGdf['STATEFP'] == '01']

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
    connecticutLogger.info(msg)

    # For testing, just look at alabama
    #blockGroupGdf = blockGroupGdf[blockGroupGdf['STATEFP'] == '01']

    graph = AddLevel(graph, tractGdf, blockGroupGdf)



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
    

    if overwrite:
        graph.SaveGraph(graphsDir)

    ### Block Group - Block ###

    msg = "Starting Tract-Block group overlay..."
    print(msg)
    connecticutLogger.info(msg)

    # For testing, just look at Alabama
    print(blockGdf.head())
    return
    blockGdf = blockGdf[blockGdf['STATEFP'] == '01']






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
    cMain()