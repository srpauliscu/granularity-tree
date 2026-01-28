

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

def StateAcToFips(row, stateDict: dict, col: str):

    # Account for an empty cell
    try:
        retVal = stateDict[row[col]]
    except:
        return ""
    return retVal

def CityTupleIdConverter(row, cityDict: dict, cityCol: str, stateFipsCol: str):

    # Account for empty cell
    try:
        cityName = row[cityCol].lower()
        sFips = row[stateFipsCol]
    except AttributeError as e:
        # Empty cell
        return ""

    if (cityName, row[stateFipsCol]) in cityDict:
        return cityDict[(cityName, sFips)]
    else:
        # Check if the city name is in part of the cityDict key
        for kPair in cityDict:
            if cityName in kPair[0] and sFips == kPair[1]:
                return cityDict[kPair]
            
        # No partial matches found
        return ""



def CityIdConverter(row, cityDict: dict, col: str):

    # Account for empty cell
    try:
        cityName = row[col].lower()
    except AttributeError as e:
        # Empty cell
        return ""

    if cityName in cityDict:
        return cityDict[cityName]
    else:
        return ""
    
def ZctaIdConverter(row, zctaDict: dict):

    zcta = row['ZCTA']
    if zcta in zctaDict:
        return zctaDict[zcta]
    
    # Account for differing data types
    elif str(zcta) in zctaDict:
        return zctaDict[str(zcta)]
    
    # Add a leading 0
    elif f"0{zcta}" in zctaDict:
        return zctaDict[f"0{zcta}"]
    
    else:
        return ""

def ZipZctaConverter(row, ztzDict: dict, col: str = 'zip'):
    
    z = row[col]
    if z in ztzDict:
        return ztzDict[z]
    
    # Account for differing data types
    elif str(z) in ztzDict:
        return ztzDict[str(z)]
    
    # Add in a leading 0
    elif f"0{z}" in ztzDict:
        return ztzDict[f"0{z}"]
    
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
    evRegsGdf = gpd.read_file('./evaluation/spatial/ev_registration.csv')
    ratesGdf = gpd.read_file('./evaluation/spatial/iou_zipcodes_2023.csv')
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
    evRegsGdf['GISJOIN'] = evRegsGdf.apply(CityIdConverter, args=(cityDictLower, 'Primary Customer City'), axis=1)

    # Remove cities that we didn't have
    evRegsGdf = evRegsGdf[evRegsGdf['GISJOIN'] != ""]
    

    # Now, construct the graph if needed
    if not load:
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
        

        # Save the graph
        if overwrite:
            graph.SaveGraph(graphsDir)

    # Get a gator object
    gator = Gator(graph, Path('./logs/connecticutGator.log'))

    # Make the data column a float for mathmatical operations
    evRegsGdf['Vehicle Year'] = evRegsGdf['Vehicle Year'].astype(np.float64)

    resDf = gator.SpatialEqualize(evRegsGdf, ratesGdf, GEID.CITY, GEID.ZCTA,
                           'GISJOIN', 'GISJOIN', 'Vehicle Year', None, None,
                           AggMethod.COUNT, EdgeType.AREA, ignoreIncomplete=True,
                           ignoreMissing=True)
    
    print(resDf['Vehicle Year'].sum())
    print(evRegsGdf.shape)

    # Now, I have the approx. number of EVs registered
    # in each ZCTA.  Rename for clarity
    resDf = resDf.rename(columns={'Vehicle Year': 'Number of EVs'})

    # We can just plot them now: rate vs. # vehicles

    # Join the rates df with the registration df
    joinedGdf = pd.merge(ratesGdf, resDf, left_on='GISJOIN', right_index=True)

    print(joinedGdf.head())

    # Sort by number of EVs
    joinedGdf = joinedGdf.sort_values(by=['Number of EVs'], ascending=True)

    # We also need to convert the price columns to floats
    joinedGdf['comm_rate'] = joinedGdf['comm_rate'].astype(dtype='float64')
    joinedGdf['ind_rate'] = joinedGdf['ind_rate'].astype(dtype='float64')
    joinedGdf['res_rate'] = joinedGdf['res_rate'].astype(dtype='float64')

    



    joinedGdf.plot(x='Number of EVs', y='res_rate', kind='scatter')
    joinedGdf.plot(x='Number of EVs', y='comm_rate', kind='scatter')
    plt.show()












    return


    #print(ov.geometry.area)


if __name__ == "__main__":
    cMain()