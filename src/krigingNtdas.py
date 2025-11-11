


import ntdas
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


def Kriging():

    # Grab the data
    dataDir = Path("./data/ntdas")

    vehicleDf, roadDf = ntdas.LoadData(dataDir, numRows=100)

    # Only get Denver zip codes for the roads
    #roadDf = roadDf[roadDf['zip'].isin(ntdas.DENVER_ZIPS)]

    # Take out rows with a travel time of 0 minutes
    vehicleDf = vehicleDf[vehicleDf[ntdas.TRAVEL_TIME_COL] > 0]

    # We need to calculate an end timestamp for each measurment
    vehicleDf[ntdas.INTERVAL_COL] = vehicleDf.apply(ntdas.CalcInterval, axis=1)

    # Calculate ratio of speed to reference speed
    vehicleDf[ntdas.SPEED_RATIO_COL] = vehicleDf[ntdas.SPEED_COL] / vehicleDf[ntdas.REFERENCE_COL]


    # We need to convert from ZIP to ZCTA
    parentDir = Path("./data/tiger")
    zctaGdf = LoadShapefile(parentDir, 'zcta')
    ztzGdf = gpd.read_file("./data/zipToZcta.csv")
    ztzGdf = ztzGdf[ztzGdf['STATE'] == 'CO']
    ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

    roadDf[ntdas.ZCTA_COL] = roadDf.apply(ZipZctaConverter, args=(ztzDict,), axis=1)

    # Convert from ZCTA to GISJOIN
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()
    roadDf['GISJOIN'] = roadDf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)


    # Join with the roadDf to assign ZCTAs to each vehicle
    joinedDf = pd.merge(vehicleDf, roadDf, on='tmc', how='inner')


    # Kriging start

    # Calculate an average speed ratio for each ZIP
    avgRatioByZip = joinedDf[['GISJOIN', ntdas.SPEED_RATIO_COL]].groupby('GISJOIN').mean()[ntdas.SPEED_RATIO_COL]

    print(avgRatioByZip.head())


if __name__ == "__main__":
    Kriging()