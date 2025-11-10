

# Functions to generate temporal test data
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import math
from tqdm import tqdm
import time

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
INTERVAL_COL = "a_time_interval_"
SPEED_RATIO_COL = "a_speed_ratio_col_"

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

# ZIP codes for the roads
DENVER_ZIPS = [80002, 80003, 80004, 80005, 80007]
DENVER_ZIPS.extend([i for i in range(80010, 80020)])
DENVER_ZIPS.extend([80303, 80305, 80301])
DENVER_ZIPS.extend([i for i in range(80601, 80604)])
DENVER_ZIPS.extend([80020, 80021, 80023, 80108, 80022, 80025])
DENVER_ZIPS.extend([i for i in range(80202, 80235)])
DENVER_ZIPS.extend([i for i in range(80110, 80114)])
DENVER_ZIPS.extend([80516, 80118, 80401, 80403, 80640, 80126, 80129, 80130])
DENVER_ZIPS.extend([80026, 80503, 80504, 80501, 80027])
DENVER_ZIPS.extend([i for i in range(80121, 80128)])
DENVER_ZIPS.extend([80465, 80134, 80138, 80108, 80030, 80031])
#DENVER_ZIPS = [str(v) for v in DENVER_ZIPS]

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

def LoadSavedDFs(parentDir: Path) -> tuple[pd.DataFrame, gpd.GeoDataFrame, pd.DataFrame, gpd.GeoDataFrame]:

    # Load the vehicle, school district, and road
    # DFS that were already converted

    vehicleDf = pd.read_csv(parentDir / Path("vehicleDf.csv"))
    sdGdf = gpd.read_file(parentDir / Path("sdGdf.geojson"))
    roadDf = pd.read_csv(parentDir / Path("roadDf.csv"))
    zctaGdf = gpd.read_file(parentDir / Path("zctaGdf.geojson"))


    return vehicleDf, sdGdf, roadDf, zctaGdf



def main(load: bool = True, overwrite: bool = False):

    # Get the data
    dataDir = Path("./data/ntdas")
    dfCacheDir = Path("./data/ntdas/gdfs")

    # Check if the gdfs already exist
    if dfCacheDir.exists() and load:
        print("Loading gdfs...")
        vehicleDf, sdGdf, roadDf, zctaGdf = LoadSavedDFs(dfCacheDir)

    # Otherwise, load from scratch
    else:
        print("Making gdfs...")
        vehicleDf, roadDf = LoadData(dataDir, numRows=-1)
        #vehicleDf, roadDf = LoadData(dataDir, numRows=100)

        # Only get specific dates of data
        #dateCutoff = pd.Timestamp(year=2020, month=10, day=9, hour=23, minute=59, second=59)
        dateCutoff = pd.Timestamp(year=2020, month=10, day=7, hour=0, minute=0, second=0)
        vehicleDf = vehicleDf[vehicleDf[TIMESTAMP_COL] < dateCutoff]
        #vehicleDf = vehicleDf.sample(n=1000000, random_state=42)

        # Only get Denver zip codes for the roads
        roadDf = roadDf[roadDf['zip'].isin(DENVER_ZIPS)]

        # Take out rows with a travel time of 0 minutes
        vehicleDf = vehicleDf[vehicleDf[TRAVEL_TIME_COL] > 0]

        # We need to calculate an end timestamp for each measurement
        vehicleDf[INTERVAL_COL] = vehicleDf.apply(CalcInterval, axis=1)
    
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

        # Write out the adjusted source files
        '''
        if not dfCacheDir.exists():
            dfCacheDir.mkdir()
        vehicleDf.to_csv(dfCacheDir / Path("vehicleDf.csv"))
        sdGdf.to_file(dfCacheDir / Path("sdGdf.geojson"), driver="GeoJSON")
        roadDf.to_csv(dfCacheDir / Path("roadDf.csv"))
        zctaGdf.to_file(dfCacheDir / Path("zctaGdf.geojson"), driver="GeoJSON")
        '''

    print("Constructing graph...")
    

    # Construct the graph, if needed
    graphsDir = Path("./graphs")
    graph = GranularityGraph('ntdasGraph', Path('./logs/ntdasGraph.log'))
    if load and not overwrite:
        # This will run even if we don't have a save file
        graph.LoadGraph(graphsDir)
    else:
        msg = "Adding school district-ZCTA layer..."
        print(msg)
        graph = AddLevel(graph, sdGdf, zctaGdf,
                        n1Type=GEID.SD, n2Type=GEID.ZCTA)
        
        # Save it out
        if overwrite:
            graph.SaveGraph(graphsDir)
    
    # Check if we have an existing result file first
    fname = Path("./data/ntdas/shouldHaveDoneThisSooner.csv")
    if fname.exists():
        resDf = pd.read_csv(fname)

        # Make the interval column timestamps
        resDf[INTERVAL_COL] = pd.to_datetime(resDf[INTERVAL_COL])

        # Reform the multiindex
        resDf = resDf.set_index(['GISJOIN', INTERVAL_COL])

    else:
            
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

        #print(joinedDf.head())

        # Do the scaling
        st = time.time()
        resDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                            TID.HOUR, GEID.ZCTA, GEID.SD,
                                            'GISJOIN', 'GISJOIN', INTERVAL_COL,
                                            None, SPEED_RATIO_COL, AggMethod.MEAN,
                                            AggMethod.MEAN, EdgeType.AREA,
                                            True, True
                                            )
        print(f"Runtime: {time.time() - st}")
        
        # Fix the ordering of the multindex
        resDf = resDf.swaplevel().sort_index(level=0, inplace=False)

        # For plotting purposes, just look at Denver districts
        resDf = resDf.loc[resDf.index.get_level_values(0).isin(list(DENVER_SD_IDS.keys()))]

        # Save it for speed ups
        #resDf.to_csv("./data/ntdas/shouldHaveDoneThisSooner.csv")


    #resDf = resDf.unstack(level=0)
    # Group them one at a time to spread out subplots
    # among multiple figures
    plotCount = 0
    figRows = 1
    figCols = 1
    dayOrder = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    print("Beginning plotting...")

    return
    
    for lv, group in tqdm(resDf.groupby(level=0)):

        # We only need a couple specific plots
        if not ("Denver" in DENVER_SD_IDS[lv] or "Gilpin" in DENVER_SD_IDS[lv]):
            continue

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
        handleList = []
        for day, dayGroup in days:

            if day == "Saturday" or day == "Sunday":
                # Skip weekends
                continue

            # Plot by hour of the day
            dayGroup.set_index(dayGroup.index.get_level_values(0).hour, inplace=True)
            dayGroup.plot(kind='line', rot=0, ax=curAxPair, linewidth=2.5)

            # Save handles and labels to fix legend later
            handleList.append(curAxPair.get_lines()[-1])
            legendList.append(day)

        # Set labels
        curAxPair.set_xlabel('Hour of Day', fontsize=20)
        curAxPair.set_ylabel('Ratio of Recorded to Typical Speed', fontsize=20)
        curAxPair.set_title(DENVER_SD_IDS[lv] + ", 10/5/20 - 10/9/20", fontsize=24)

        # Set limits for specific graphs
        if 'Denver' in DENVER_SD_IDS[lv]:
            curAxPair.set_ylim(bottom=0.5, top=1.0)
        elif 'Gilpin' in DENVER_SD_IDS[lv]:
            curAxPair.set_ylim(bottom=0.6, top=1.2)

        # Fix tick sizes and fonts
        curAxPair.tick_params(axis='x', which='major', labelsize=16)
        curAxPair.tick_params(axis='y', which='major', labelsize=16)
        curAxPair.tick_params(axis='x', which='minor', labelsize=16)
        curAxPair.tick_params(axis='both', length=12, width=3)

        # Reorder the legend labels
        newHandleList = []
        for d in dayOrder:
            curI = legendList.index(d)
            newHandleList.append(handleList[curI])


        # Fix the legend label
        curAxPair.legend(newHandleList, dayOrder, fontsize=16)

        # Add lines for the times
        xticks = curAxPair.get_xticks()
        ymin, ymax = curAxPair.get_ylim()
        for i, xt in enumerate(xticks):
            if i==0:
                continue
            curAxPair.vlines(xt, ymin-.2, ymax+.2, color='gray', linestyle=':', linewidth=1.25)

        # Fix overlapping labels
        plt.tight_layout()
        curFig.tight_layout()
        curFig.set_tight_layout(True)


        plotCount += 1

        plt.savefig(f"./data/ntdas/smallerFigs/{DENVER_SD_IDS[lv]}.png", dpi=1600)

        # Clear figures and axes for memory issues
        plt.clf()
        plt.cla()
        plt.close()

        # For testing
        if plotCount >= 24:
            break
        
    # Use to plot all on one graph
    #ax = resDf.unstack(level=0).plot(kind='line', subplots=False, rot=0, figsize=(9,7), layout=(10,10))
    #plt.tight_layout()

    #plt.show()


if __name__ == "__main__":
    main()