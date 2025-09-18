

# Functions to generate temporal test data
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import math
from tqdm import tqdm

from gator import *
from kGraph import Node, GranularityGraph
from populateGraph import AddLevel, AddNodes, LoadShapefile, OVERLAY_AREA_COLUMN
from connecticutGraph import ZipZctaConverter, ZctaIdConverter

# Global vars
CO_FIPS = "08"

SEG_ID_COL = "tmc"
COUNTY_COL = "county"
ZIP_COL = "zip"
ZCTA_COL = "ZCTA"

TIMESTAMP_COL = "measurement_tstamp"
SPEED_COL = "speed"
TRAVEL_TIME_COL = "travel_time_minutes"
INTERVAL_COL = "_time_interval_"


# Function to load in the data
def LoadData(parentDir: Path, numRows: int = 100):

    # Load in both files from the NTDAS download
    if numRows > 0:
        # Use a smaller sample for testing
        vehicleDf = pd.read_csv(parentDir / Path("Readings.csv"), nrows=numRows)
    else:
        vehicleDf = pd.read_csv(parentDir / Path("Readings.csv"))

    # Always read in all the roads
    roadDf = pd.read_csv(parentDir / Path("TMC_Identification.csv"))

    # Rename the id col so they match
    vehicleDf = vehicleDf.rename(columns={"tmc_code":SEG_ID_COL})

    # Make sure we are using timestamp objects
    vehicleDf[TIMESTAMP_COL] = pd.to_datetime(vehicleDf[TIMESTAMP_COL])

    return vehicleDf, roadDf


def CalcInterval(row: pd.Series):

    # Need to use apply() since pd.Timedelta won't
    # easily be vectorized (at least, I don't know how)

    endTime = row[TIMESTAMP_COL] + pd.Timedelta(minutes=row[TRAVEL_TIME_COL])

    return pd.Interval(row[TIMESTAMP_COL], endTime)

def main(load: bool = False, overwrite: bool = True):

    # Get the data
    dataDir = Path("./data/ntdas")
    vehicleDf, roadDf = LoadData(dataDir, numRows=10000)

    # We need to calculate an end timestamp for each measurement
    vehicleDf[INTERVAL_COL] = vehicleDf.apply(CalcInterval, axis=1)

    # Set up the graph
    graphsDir = Path("./graphs")
    graph = GranularityGraph('ntdasGraph', Path('./logs/ntdasGraph.log'))
    if load:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)
    
    # We need a zip - school district layer
    # We also need to convert zip to zcta first
    parentDir = Path("./data/tiger")
    sdGdf = LoadShapefile(parentDir, 'school')

    # We only need school districts in CO
    sdGdf = sdGdf[sdGdf['STATEFP'] == CO_FIPS]

    # Now, load in the zctas
    zctaGdf = LoadShapefile(parentDir, 'zcta')

    # Get the mapping from zip to zcta
    ztzGdf = gpd.read_file("./data/zipToZcta.csv")
    ztzGdf = ztzGdf[ztzGdf['STATE'] == 'CO']

    # Make a dictionary out of the two columns
    ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

    # Do the conversion from zip to zcta
    roadDf[ZCTA_COL] = roadDf.apply(ZipZctaConverter, args=(ztzDict,), axis=1)

    # Make a zcta: GISJOIN dict
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()

    # Add a column to the roads for the GISJOIN ID of their ZCTA
    roadDf['GISJOIN'] = roadDf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)

    # Remove ZIPs we didn't have
    roadDf = roadDf[roadDf['GISJOIN'] != ""]

    # Construct the graph, if needed
    if not load:
        msg = "Adding school district-ZCTA layer..."
        print(msg)
        graph = AddLevel(graph, sdGdf, zctaGdf,
                        n1Type=GEID.SD, n2Type=GEID.ZCTA)
        
        # Save it out
        if overwrite:
            graph.SaveGraph(graphsDir)
    
    # Get a gator object
    gator = Gator(graph, Path('./logs/ntdasGator.log'))

    # Before aggregation, we need to do a join
    # to assign ZCTAs to each vehicle reading

    # Get rid of unneeded columns before the join
    roadDf = roadDf[[SEG_ID_COL, "GISJOIN"]]

    # Do the join
    joinedDf = pd.merge(vehicleDf, roadDf, on=SEG_ID_COL, how='inner')

    print(joinedDf.head())

    # Do the scaling
    resDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                         TID.HOUR, GEID.ZCTA, GEID.SD,
                                         'GISJOIN', 'GISJOIN', INTERVAL_COL,
                                         None, SPEED_COL, AggMethod.MEAN,
                                         AggMethod.MEAN, EdgeType.AREA,
                                         True, True
                                         )
    
    pd.set_option('display.max_rows', None)
    
    # Fix the ordering of the multindex
    resDf = resDf.swaplevel().sort_index(level=0, inplace=False)

    print(resDf)
    #quit()
    
    #resDf = resDf.unstack(level=0)
    # Group them one at a time to spread out subplots
    # among multiple figures
    plotCount = 0
    for lv, group in resDf.groupby(level=0):
        if plotCount % 4 == 0:
            curFig, axisPairs = plt.subplots(2,2)
            axisPairs = axisPairs.flatten()

        # Do this to get rid of the GISJOIN as an axis label
        group = group.droplevel(0)
        
        # Pass a specific axis pair to pd.plot
        curAxPair = axisPairs[plotCount % 4]
        group.plot(kind='line', rot=0, ax=curAxPair)
        curAxPair.set_xlabel('Timestamp')
        #plt.tight_layout()

        plotCount += 1

        # For testing
        if plotCount >= 16:
            break
        
    # Use to plot all on one graph
    #ax = resDf.unstack(level=0).plot(kind='line', subplots=False, rot=0, figsize=(9,7), layout=(10,10))
    #plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()