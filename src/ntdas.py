

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
REFERENCE_COL = "reference_speed"
TRAVEL_TIME_COL = "travel_time_minutes"
INTERVAL_COL = "_time_interval_"
SPEED_RATIO_COL = "_speed_ratio_col_"

# List of GISJOIN ids for Denver SDs
# Names included for convenience
DENVER_SD_IDS = {"G08006900": "Adams 12 Five Star Schools",
                "G13001440": "Commerce City School District",
                "G40008490": "Commerce Public Schools",
                "G08002340": "Adams-Arapahoe School District 28J",
                "G08002490": "Boulder Valley School District RE-2",
                "G08002910": "Cherry Creek School District 5",
                "G08003000": "Clear Creek School District RE-1",
                "G08003360": "Denver County School District 1",
                "G08003450": "Douglas County School District RE-1",
                "G08003720": "Elizabeth School District",
                "G08003780": "Englewood School District 1",
                "G08004230": "Gilpin County School District RE-1",
                "G08004800": "Jefferson County School District R-1",
                "G08005310": "Littleton School District 6",
                "G08005550": "Mapleton School District 1",
                "G08002370": "Platte Canyon School District 1",
                "G08002580": "School District 27J",
                "G08006540": "Sheridan School District 2",
                "G08007230": "Westminster Public School District"}


# Function to load in the data
def LoadData(parentDir: Path, numRows: int = 100, skiprows: int = 0):

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
    vehicleDf, roadDf = LoadData(dataDir, numRows=-1)

    # For bug testing
    #vehicleDf = vehicleDf.tail(n=5375000)
    dateCutoff = pd.Timestamp(year=2020, month=10, day=10, hour=0, minute=0, second=0)
    vehicleDf = vehicleDf[vehicleDf[TIMESTAMP_COL] < dateCutoff]
    #vehicleDf = vehicleDf.sample(n=10000, random_state=42)


    # Take out rows with a travel time of 0 minutes
    vehicleDf = vehicleDf[vehicleDf[TRAVEL_TIME_COL] > 0]

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

    # Calculate ratio of speed to reference speed
    vehicleDf[SPEED_RATIO_COL] = vehicleDf[SPEED_COL] / vehicleDf[REFERENCE_COL]

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

    # Drop NANs
    joinedDf = joinedDf.dropna(subset=[SPEED_RATIO_COL])

    print(joinedDf.head())

    # Do the scaling
    resDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                         TID.HOUR, GEID.ZCTA, GEID.SD,
                                         'GISJOIN', 'GISJOIN', INTERVAL_COL,
                                         None, SPEED_RATIO_COL, AggMethod.MEAN,
                                         AggMethod.MEAN, EdgeType.AREA,
                                         True, True
                                         )
    
    # Fix the ordering of the multindex
    resDf = resDf.swaplevel().sort_index(level=0, inplace=False)

    # For plotting purposes, just look at Denver districts
    resDf = resDf.loc[resDf.index.get_level_values(0).isin(list(DENVER_SD_IDS.keys()))]

    #print(resDf)
    #quit()
    
    #resDf = resDf.unstack(level=0)
    # Group them one at a time to spread out subplots
    # among multiple figures
    plotCount = 0
    figRows = 1
    figCols = 1
    for lv, group in resDf.groupby(level=0):
        if plotCount % (figRows * figCols) == 0:
            curFig, axisPairs = plt.subplots(figCols, figRows, figsize=(15,9))
            if figRows*figCols > 1:
                axisPairs = axisPairs.flatten()

        # Do this to get rid of the GISJOIN as an axis label
        group = group.droplevel(0)

        # Pass a specific axis pair to pd.plot
        if figRows*figCols > 1:
            curAxPair = axisPairs[plotCount % (figRows * figCols)]
        else:
            curAxPair = axisPairs

        # Now, we want to group and plot each day as separate lines
        days = group.groupby(group.index.get_level_values(0).day_name())
        legendList = []
        for day, dayGroup in days:

            if day == "Saturday" or day == "Sunday":
                # Skip weekends
                continue

            # Plot by hour of the day
            dayGroup.set_index(dayGroup.index.get_level_values(0).hour, inplace=True)
            dayGroup.plot(kind='line', rot=0, ax=curAxPair, linewidth=2.5)
            legendList.append(day)

        # Set labels
        curAxPair.set_xlabel('Hour of Day', fontsize=20)
        curAxPair.set_ylabel('Ratio of Recorded to Typical Speed', fontsize=20)
        curAxPair.set_title(DENVER_SD_IDS[lv] + ", 10/5/20 - 10/9/20", fontsize=24)

        # Fix tick font sizes
        curAxPair.tick_params(axis='x', which='major', labelsize=16)
        curAxPair.tick_params(axis='y', which='major', labelsize=16)
        curAxPair.tick_params(axis='x', which='minor', labelsize=16)

        # Fix the legend label
        curAxPair.legend(legendList, fontsize=16)

        plt.tight_layout()
        curFig.tight_layout()
        curFig.set_tight_layout(True)

        plotCount += 1

        plt.savefig(f"./data/ntdas/figures/{DENVER_SD_IDS[lv]}.svg", dpi=curFig.dpi)

        # For testing
        if plotCount >= 24:
            break
        
    # Use to plot all on one graph
    #ax = resDf.unstack(level=0).plot(kind='line', subplots=False, rot=0, figsize=(9,7), layout=(10,10))
    #plt.tight_layout()

    #plt.show()


if __name__ == "__main__":
    main()