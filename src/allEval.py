
from pathlib import Path

import numpy as np
import time
import matplotlib
import matplotlib.pyplot as plt

# Get functions for loading the NTDAS data for CS 3
import ntdas

from gator import *

import pytz

# Import functions for graph creation from shapefiles
from connecticutGraph import *

matplotlib.use('qt5agg')

# Figure parameters
FIG_SIZE_FACTOR = 3
FIG_SIZE = (6.4*FIG_SIZE_FACTOR, 4.8*FIG_SIZE_FACTOR)

FIG_LABEL_FONT_SIZE = 36#24
FIG_TITLE_FONT_SIZE = 48#32

FIG_MAJOR_AXIS_TICK_SIZE = 24#16
FIG_MINOR_AXIS_TICK_SIZE = 21#14


# State acronym to FIPS code map
STATE_AC_TO_FIPS = {

    'AL': '01',
    'AK': '02',
    'AZ': '04',
    'AR': '05',
    'CA': '06',
    'CO': '08',
    'CT': '09',
    'DE': '10',
    'DC': '11',
    'FL': '12',
    'GA': '13',
    'HI': '15',
    'ID': '16',
    'IL': '17',
    'IN': '18',
    'IA': '19',
    'KS': '20',
    'KY': '21',
    'LA': '22',
    'ME': '23',
    'MD': '24',
    'MA': '25',
    'MI': '26',
    'MN': '27',
    'MS': '28',
    'MO': '29',
    'MT': '30',
    'NE': '31',
    'NV': '32',
    'NH': '33',
    'NJ': '34',
    'NM': '35',
    'NY': '36',
    'NC': '37',
    'ND': '38',
    'OH': '39',
    'OK': '40',
    'OR': '41',
    'PA': '42',
    'RI': '44',
    'SC': '45',
    'SD': '46',
    'TN': '47',
    'TX': '48',
    'UT': '49',
    'VT': '50',
    'VA': '51',
    'WA': '53',
    'WV': '54',
    'WI': '55',
    'WY': '56',

    'AS': '60',
    'FM': '64',
    'GU': '66',
    'MH': '68',
    'MP': '69',
    'PW': '70',
    'PR': '72',
    'UM': '74',
    'VI': '78'






}

# State acronyms to full state names
ACRO_TO_STATE = {

    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "AS": "American Samoa",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "GU": "Guam",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "MP": "Northern Mariana Islands",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "TT": "Trust Territories",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "VI": "Virgin Islands",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "UM": "Minor Outlying Islands"
    }

# Reverse it to get full state names to acro
STATE_TO_ACRO = {}
for k in ACRO_TO_STATE:
    STATE_TO_ACRO[ACRO_TO_STATE[k]] = k

# Ranges of ZIP codes for each relevant state,
# with edge cases
STATE_AC_ZIP_RANGE = {
     
     'CO': (80001, 81658),
     'ME': (3901, 4992),
     'MN': (55001, 56763),
     'NY': (10001, 14975, 6390),
     'NJ': (7001, 8989),
     'NM': (87001, 88441),
     'NC': (27006, 28909),
     'OR': (97001, 97920),
     'TX': (75001, 79999, 73301),
     'TXEP': (88510, 88589),
     'VT': (5001, 5907)

}

# pytz has no PDT or PST timezones, so we
# need to map them to the canonical names

# Might as well map everything for consistency
US_TIMEZONE_DICT = {

    'PDT': ('US/Pacific', True),
    'PST': ('US/Pacific', False),

    'MDT': ('US/Mountain', True),
    'MST': ('US/Mountain', False),

    'EDT': ('US/Eastern', True),
    'EST': ('US/Eastern', False),

    'UTC': ('UTC', False)

}

# Distance function that accounts for binning
def distFunc(x: Point, y: Point, binSize=-1.):

    if x == y:
        if binSize > 0:
            # Return the midway point of the bin
            return .5*binSize
        else:
            return 0
    else:
        if binSize > 0:
            return (math.floor(distance(x,y) / binSize)*binSize)+.5*binSize
        else:
            return distance(x,y)


def SpatialEval(dirPath: Path, loadGraph: bool = True):

    ''' Outline
    Want: EV registration vs. utility rates
    Have: EV registration by city, rates by ZIP
    Need: EV Registration by ZIP

    Procedure: Scale by areal overlap, city -> ZIP
    '''

    # Generate a logger for this evaluation
    logger = logging.getLogger('SpatialEval')
    logging.basicConfig(filename="./logs/spatialEval.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")


    # Important paths
    sfDir = Path("./data/tiger")
    graphsDir = Path("./graphs")


    # Load in the CSVs
    regsDf = pd.read_csv(dirPath / "ev_registration.csv")
    iouRatesDf = pd.read_csv(dirPath / "iou_zipcodes_2023.csv")

    # We need the regs states as FIPS codes
    regsDf['STATEFIPS'] = regsDf.apply(StateAcToFips, args=(STATE_AC_TO_FIPS, 'Primary Customer State'), axis=1)

    # Drop rows with an invalid state
    regsDf = regsDf[regsDf['STATEFIPS'] != '']

    # Only use one state for now
    regsDf = regsDf[regsDf['Primary Customer State'] == 'CT']#.head(n=1000)
    iouRatesDf = iouRatesDf[iouRatesDf['state'] == 'CT']#.head(n=1000)

    # We are only doing American locations, so drop BC and ON from the list
    regsDf = regsDf[(regsDf['Primary Customer State'] != 'BC') & 
                  (regsDf['Primary Customer State'] != 'ON')]

    # We need information for ZIPS and cities

    ### Cities ###
    cityGdf = LoadShapefile(sfDir, 'city')

    # Make the city names lower case for consistency
    cityGdf['NAME'] = cityGdf['NAME'].str.lower()
    
    # Make a city name: GISJOIN dict
    cityDict = pd.Series(cityGdf['GISJOIN'].values, index=[cityGdf['NAME'], cityGdf['STATEFP']]).to_dict()


    # Convert city name to GISJOIN ID
    regsDf['GISJOIN'] = regsDf.apply(CityTupleIdConverter, args=(cityDict, 'Primary Customer City', 'STATEFIPS'), axis=1)


    # Remove cities that we didn't have
    regsDf = regsDf[regsDf['GISJOIN'] != ""]
    

    ### ZCTAs/ZIPs ###

    # Use ZCTAs to approx. ZIPs
    zctaGdf = LoadShapefile(sfDir, 'zcta')

    # Get the mapping from zip to zcta
    ztzGdf = gpd.read_file("./data/zipToZcta.csv")
    ztzGdf = ztzGdf[ztzGdf['STATE'] == 'CT']

    # Make a dictionary out of the two columns
    ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

    # Do the conversion from ZIP to ZCTA
    iouRatesDf['ZCTA'] = iouRatesDf.apply(ZipZctaConverter, args=(ztzDict,), axis=1)

    # Now, convert from ZCTA to GISJOIN ID
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()
    iouRatesDf['GISJOIN'] = iouRatesDf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)

    # Remove ZIPs we didn't have 
    iouRatesDf = iouRatesDf[iouRatesDf['GISJOIN'] != ""]

    # All of the above is needed even if the graph is loadable
    # because we need to convert to GISJOIN IDs

    # TODO: Graph holding all ZCTAs and cities needs too much
    # memory.  Need to add a "pager"
    # For now, just use one state
    cityGdf = cityGdf[cityGdf['STATEFP'] == '09']


    # Start graph setup
    graph = GranularityGraph('spatialEval', Path('./logs/spatialEval.log'))

    # If specified, try loading a graph from disk first
    status = Status.NOTEXISTS
    if loadGraph:
        status = graph.LoadGraph(Path("./graphs"))

    # If needed, create a fresh graph
    if status != Status.SUCCESS:

        # Construct the graph
        msg = "Adding City-ZCTA layer..."
        print(msg)
        logger.info(msg)

        # Try adding one state at a time
        groupedGdf = cityGdf.groupby('STATEFP')
        for group in groupedGdf:
            msg = f"Adding layer for state {group[0]}..."
            print(msg)
            logger.info(msg)

            curGdf = group[1]
            graph = AddLevel(graph, curGdf, zctaGdf,
                                n1Type=GEID.CITY, n2Type=GEID.ZCTA)
        
        # Save the graph
        msg = "Saving the graph..."
        print(msg)
        logger.info(msg)
        graph.SaveGraph(graphsDir)
        
    else:
        # Log that we loaded the graph
        msg = "Graph loaded successfully."
        print(msg)
        logger.info(msg)

    
    # Get a gator object
    gator = Gator(graph, Path('./logs/spatialEvalGator.log'))

    # Make the data column a float for mathmatical operations
    regsDf['Vehicle Year'] = regsDf['Vehicle Year'].astype(np.float64)

    #print(cityGdf)

    resDf = gator.SpatialEqualize(regsDf, iouRatesDf, GEID.CITY, GEID.ZCTA,
                                  'GISJOIN', 'GISJOIN', 'Vehicle Year', None, None,
                                  AggMethod.COUNT, EdgeType.AREA, ignoreMissing=True,
                                  ignoreIncomplete=True)

    # Now, I have the approx. number of EVs registered
    # in each ZCTA.  Rename for clarity
    resDf = resDf.rename(columns={'Vehicle Year': 'Number of EVs'})

    # We can just plot them now: rate vs. # vehicles

    # Join the rates df with the registration df
    joinedGdf = pd.merge(iouRatesDf, resDf, left_on='GISJOIN', right_index=True)

    # Sort by number of EVs
    joinedGdf = joinedGdf.sort_values(by=['Number of EVs'], ascending=True)

    # We also need to convert the price columns to floats
    joinedGdf['comm_rate'] = joinedGdf['comm_rate'].astype(dtype='float64')
    joinedGdf['ind_rate'] = joinedGdf['ind_rate'].astype(dtype='float64')
    joinedGdf['res_rate'] = joinedGdf['res_rate'].astype(dtype='float64')

    # Plot it
    joinedGdf.plot(y='Number of EVs', x='res_rate', kind='scatter')
    joinedGdf.plot(y='Number of EVs', x='comm_rate', kind='scatter')
    plt.show()


def ConvertToDt(row, tsCol: str, tzCol: str):

    # Grab the timezone
    tz = row[tzCol]

    # Get the corresponding name and DST flag
    tzName, dst = US_TIMEZONE_DICT[tz]

    # Use to_datetime and tz_localize
    try:
        return pd.to_datetime(row[tsCol]).tz_localize(tzName, ambiguous=dst, nonexistent='shift_forward').tz_convert('UTC')
    except Exception as e:

        # It may already be tz-aware, so skip tz_localize
        try:
            return pd.to_datetime(row[tsCol]).tz_convert('UTC')
        except Exception as e2:
            return 0

def FormInterval(row, startTsCol: str, endTsCol: str):
        
        # Grab the timestamps
        ts0 = row[startTsCol]
        ts1 = row[endTsCol]

        # Check for invalid timestamps
        if ts1 < ts0:
            print(ts0)
            print(ts1)

            # Just swap them?
            temp = ts0
            ts0 = ts1
            ts1 = temp
        
        # Check for invalid timestamps
        return pd.Interval(ts0, ts1)

def TemporalEval(dirPath: Path):

    ''' Outline
    Want: Total power draw per hour for chargers
    Have: Charging sessions in minute intervals
    Need: Convert from minute intervals to hourly sums

    Procedure: Scale by temporal overlap, minutes -> hours
    '''

    # Generate a logger for this evaluation
    logger = logging.getLogger('TemporalEval')
    logging.basicConfig(filename="./logs/temporalEval.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Load the data
    dataDf = pd.read_csv(dirPath / 'EVChargingStationUsage.csv', low_memory=False)

    # Rename the columns to remove all special characters
    # so itertuples works
    fixedCols = {c: c.replace(' ', '').replace('(','').replace(')','').replace(':','') 
                 for c in dataDf.columns}
    
    dataDf = dataDf.rename(columns=fixedCols)

    # For testing
    #dataDf = pd.concat([dataDf.head(n=500), dataDf.tail(n=500)])
    #dataDf = dataDf.tail(n=500)

    # First, convert to actual timestamps
    startTsCol = 'StartDate'
    startTzCol = 'StartTimeZone'
    endTsCol = 'EndDate'
    endTzCol = 'EndTimeZone'

    dataDf[startTsCol] = dataDf.apply(ConvertToDt, args=(startTsCol, startTzCol), axis=1)
    dataDf[endTsCol] = dataDf.apply(ConvertToDt, args=(endTsCol, endTzCol), axis=1)

    # Remove invalid rows
    dataDf = dataDf[(dataDf[startTsCol] != 0) & (dataDf[endTsCol] != 0)]

    # Make an actual Interval object
    intervalCol = 'TIME_INTERVAL'

    # Duration for dataset statistics
    dataDf['duration'] = pd.to_datetime(dataDf[endTsCol]) - pd.to_datetime(dataDf[startTsCol])

    dataDf[intervalCol] = dataDf.apply(FormInterval, args=(startTsCol, endTsCol), axis=1)

    # Get a gator object
    gator = Gator(None, Path('./logs/temporalEvalGator.log'))

    # Aggregate to the month level
    dataCol = 'EnergykWh'

    st = time.time()
    monthlyResDf = gator.TemporalEqualize(dataDf, TID.MONTH, intervalCol,
                                   dataCol, AggMethod.SUM)
    runTime = time.time() - st

    print(f"Final runtime for monthly data: {runTime} seconds")

    # Now, select data for, arbitrarily, the first week of October, 2019
    startTs = pd.Timestamp(year=2019, month=10, day=1, hour=0, minute=0, second=0, tz='US/Pacific')
    endTs = pd.Timestamp(year=2019, month=10, day=7, hour=0, minute=0, second=0, tz='US/Pacific')
    dataDf = dataDf[(dataDf[startTsCol] >= startTs) & (dataDf[endTsCol] < endTs)]
    
    st = time.time()
    dailyResDf = gator.TemporalEqualize(dataDf, TID.HOUR, intervalCol,
                                        dataCol, AggMethod.SUM)
    runTime = time.time() - st

    print(f"Final runtime for hourly data: {runTime} seconds")

    # Begin plotting the hourly data
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    dailyResDf.plot(y=dataCol, ax=ax)

    # Fix font sizes
    plt.xlabel('Time', fontsize=FIG_LABEL_FONT_SIZE)
    plt.ylabel('Total Energy Used (kWh)', fontsize=FIG_LABEL_FONT_SIZE)
    plt.title('Total Hourly Energy Used By EV Chargers, Palo Alto', fontsize=FIG_TITLE_FONT_SIZE)

    # Fix font sizes for axis ticks
    ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
    ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

    # Fix legend fontsize
    ax.legend(fontsize=FIG_MINOR_AXIS_TICK_SIZE)

    figDir = dirPath / Path("figures/")
    if not figDir.exists():
        figDir.mkdir()

    plt.savefig(figDir / Path("daily-charger-energy.png"))
    #plt.show()
    
    # Begin plotting
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    monthlyResDf.plot(y=dataCol, ax=ax)

    # Fix legend fontsize
    ax.legend(fontsize=FIG_MINOR_AXIS_TICK_SIZE)

    # Set labels and font sizes
    plt.xlabel('Date', fontsize=FIG_LABEL_FONT_SIZE)
    plt.ylabel('Total Energy Used (kWh)', fontsize=FIG_LABEL_FONT_SIZE)
    plt.title('Total Monthly Energy Used By EV Chargers, Palo Alto', fontsize=FIG_TITLE_FONT_SIZE)

    # Fix font sizes for axis ticks
    ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
    ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

    # Save the figure out
    figDir = dirPath / Path("figures/")
    if not figDir.exists():
        figDir.mkdir()

    plt.savefig(figDir / Path("monthly-charger-energy.png"))
    plt.show()

def STEval(dataDir: Path, shapefileDir: Path = Path("./data/tiger"),
           loadGraph: bool = True, graphsDir: Path = Path("./graphs"),
           loadResults: bool = True, resFile: Path = Path("./evaluation/st/results.csv")
           ):

    ''' Outline
    Scenario: Planning new bus routes and we want to know traffic trends.

    Want: Traffic density by school district (avg speed reduction per hour per district)
    Have: Average speed data for vehicles during travel at individual TSs where location
    is given by ZIP code
    
    Need: Avg speed reduction per hour, group by school district via areal overlap

    Procedure: Scale by temporal overlap, minutes -> hours
    '''
    
    # Generate a logger for this evaluation
    logger = logging.getLogger('STEval')
    logging.basicConfig(filename="./logs/stEval.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Grab the data
    # NOTE: Caching is difficult because data types would get messed up
    vehicleDf, roadDf = ntdas.LoadData(dataDir, numRows=-1)

    # Let's start with specific dates of data
    #dateCutoff = pd.Timestamp(year=2020, month=10, day=7, hour=0, minute=0, second=0)
    dateCutoff = pd.Timestamp(year=2020, month=10, day=9, hour=23, minute=59, second=59)
    vehicleDf = vehicleDf[vehicleDf[ntdas.TIMESTAMP_COL] < dateCutoff]

    # We only want Denver ZIP codes for the roads
    roadDf = roadDf[roadDf['zip'].isin(ntdas.DENVER_ZIPS)]

    # Take out rows with a travel time of 0 minutes
    vehicleDf = vehicleDf[vehicleDf[ntdas.TRAVEL_TIME_COL] > 0]



    print(vehicleDf)
    print(vehicleDf[ntdas.TIMESTAMP_COL].min())
    print(vehicleDf[ntdas.TIMESTAMP_COL].max())

    # We need to calculate an end timestamp for each measurement
    vehicleDf[ntdas.INTERVAL_COL] = vehicleDf.apply(ntdas.CalcInterval, axis=1)

    # Calculate ratio of speed to reference speed
    vehicleDf[ntdas.SPEED_RATIO_COL] = vehicleDf[ntdas.SPEED_COL] / vehicleDf[ntdas.REFERENCE_COL]

    # We need to convert from ZIP to ZCTA
    zctaGdf = LoadShapefile(shapefileDir, 'zcta')

    ztzGdf = gpd.read_file("./data/zipToZcta.csv")

    # For now, only use CO data
    ztzGdf = ztzGdf[ztzGdf['STATE'] == 'CO']

    ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

    # Do the actual conversion
    roadDf[ntdas.ZCTA_COL] = roadDf.apply(ZipZctaConverter, args=(ztzDict,), axis=1)

    # Convert from ZCTA to GISJOIN
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()
    roadDf['GISJOIN'] = roadDf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)

    # Remove rows with ZIPS we didn't have
    roadDf = roadDf[roadDf['GISJOIN'] != ""]

    # Get the school districts now
    sdGdf = LoadShapefile(shapefileDir, 'school')

    # We only need CO school districs
    sdGdf = sdGdf[sdGdf['STATEFP'] == ntdas.CO_FIPS]

    # Now, setup a graph

    graph = GranularityGraph('STEvalGraph', Path('./logs/STEvalGraph.log'))

    # Try and load it first
    if loadGraph:
        msg = "Loading graph..."
        print(msg)
        logger.info(msg)
        graph.LoadGraph(graphsDir)
    else:
        msg = "Constructing new graph..."
        print(msg)
        logger.info(msg)

        msg = "Adding school district-ZCTA layer..."
        print(msg)
        logger.info(msg)
        graph = AddLevel(graph, sdGdf, zctaGdf,
                         n1Type=GEID.SD, n2Type=GEID.ZCTA)
        
        # Save it out
        graph.SaveGraph(graphsDir)
    
    # Check if we have an existing result file first
    if loadResults and resFile.exists():
        resDf = pd.read_csv(resFile)

        # Make the interval column timestamps
        resDf[ntdas.INTERVAL_COL] = pd.to_datetime(resDf[ntdas.INTERVAL_COL])

        # Reform the multiindex
        resDf = resDf.set_index(['GISJOIN', ntdas.INTERVAL_COL])
    
    # Otherwise, do the work
    else:

        # Get a gator object
        gator = Gator(graph, Path('./logs/STEvalGator.log'))

        # Before aggregation, we need to do a join
        # to assign ZCTAs to each vehicle reading
        joinedDf = pd.merge(vehicleDf, roadDf, on='tmc', how='inner')

        # Drop NANs
        joinedDf = joinedDf.dropna(subset=[ntdas.SPEED_RATIO_COL])

        # Do the scaling
        msg = "Starting scaling operation..."
        print(msg)
        logger.info(msg)
        st = time.time()
        resDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                             TID.HOUR, GEID.ZCTA, GEID.SD,
                                             'GISJOIN', 'GISJOIN', ntdas.INTERVAL_COL,
                                             None, ntdas.SPEED_RATIO_COL, None, None,
                                             AggMethod.MEAN, AggMethod.MEAN, EdgeType.AREA,
                                             True, True)
        et = time.time()
        msg = f"Finished scaling operation, runtime was {et - st} seconds."
        print(msg)
        logger.info(msg)

        # Fix the ordering of the multiindex
        resDf = resDf.swaplevel().sort_index(level=0, inplace=False)

        # Save it for speed ups
        resDf.to_csv(resFile)

    quit()

    # Make graphs for each school district
    groupedDfs = resDf.groupby(level=0)
    count = 0
    for sd, df in groupedDfs:
        
        # Make a new figure
        fig, ax = plt.subplots(figsize=FIG_SIZE)

        # Set labels and font sizes
        plt.xlabel('Hour', fontsize=FIG_LABEL_FONT_SIZE)
        plt.ylabel('Ratio of Mean to Reference Speed', fontsize=FIG_LABEL_FONT_SIZE)
        plt.title(f'Speed Ratio per Hour for School District {sd}', fontsize=FIG_TITLE_FONT_SIZE)

        # Fix font sizes for axis ticks
        ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
        ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

        # Drop the first level of the multiindex
        df = df.droplevel(level=0)

        # We know that this is in Denver, so fix the timestamps for better plots
        # (Doesn't account for DST, but this is data from one day in Oct.)
        df.index = df.index.tz_localize('MST')

        # Plot the results
        df.plot(use_index=True, y='a_speed_ratio_col_', ax=ax, xlabel='Timestamp')
        count += 1
        if count > 4:
            break
    
    plt.show()

def ExtractCols(df: pd.DataFrame, colDict: dict) -> pd.DataFrame:

    # Use the ascii values to calculate appropriate column index
    colIndices = {ord(col) - 64 - 1 if len(col) == 1 else
                  ((ord(col[0]) - 64)*26 + ord(col[1]) - 64) - 1:
                  colDict[col]
                  for col in colDict}
    colNames = {df.columns[k]: colIndices[k] for k in colIndices}

    # Extract only those relevant columns
    resDf = df[list(colNames.keys())]

    # Rename those columns
    resDf = resDf.rename(columns=colNames)

    return resDf

def StateIntToFIPS(row: pd.Series, col: str):
    
    # Take a one or two digit FIPS ID int and return it
    # as a two digit str (including leading zeros)
    try:
        val = str(row[col])
        if len(val) == 1:
            return f'0{val}'
        elif len(val) == 2:
            return val
        else:
            raise RuntimeError(f'FIPS ID of {val} is not exactly 1 or 2 digits.')
    except RuntimeError as e:
        print(row)
        raise e


def CountyFIPSConverter(row: pd.Series, countyDict: dict, col: str):
    
    # Extract the ID as a string, accounting for
    # an empty cell
    try:
        idStr = str(row[col])
    except:
        return ""
    
    # Make sure we're checking a valid county GEOID
    if len(idStr) != 4 and len(idStr) != 5:
        raise RuntimeError(f"GEOID of {idStr} is not length 4 or 5.")

    # Add a leading 0 if necessary
    if len(idStr) == 4:
        idStr = f"0{idStr}"
    
    # Check the dict for the matching GISJOIN ID
    if idStr in countyDict:
        return countyDict[idStr]
    
    else:
        return ""
    

def LoadEVRegistration(dataDir: Path, stateAc: str) -> tuple[pd.DataFrame, GEID, str, str]:

    # Data from https://www.atlasevhub.com/market-data/state-ev-registration-data/
    # except for CT


    # Each state has a unique file to be loaded
    resDf = None
    match stateAc:

        case 'CO' | 'ME' | 'MN' | 'NJ' | 'NM' | 'NY' | 'NC' | 'OR' | 'TX' | 'VT':

            # Load the CSV
            resDf = pd.read_csv(dataDir / Path(f'emissions/evRegistrations/{stateAc}.csv'), low_memory=False)

            # Drop unnecessary columns
            resDf = resDf[['State', 'ZIP Code', 'Registration Date', 'Vehicle Count']]

            # For the zip codes, we need to trim out any vehicles with an out-of-state ZIP
            stateRange = STATE_AC_ZIP_RANGE[stateAc]
            resDf['ZIP_INT'] = pd.to_numeric(resDf['ZIP Code'], errors='coerce')

            if stateAc == 'TX':
                # We also need to account for TX El Paso's range
                epRange = STATE_AC_TO_FIPS['TXEP']
                resDf = resDf[((resDf['ZIP_INT'] >= stateRange[0]) & (resDf['ZIP_INT'] <= stateRange[1])) | 
                              (resDf['ZIP_INT'].isin(stateRange[2:])) | 
                              ((resDf['ZIP_INT'] >= epRange[0]) & (resDf['ZIP_INT'] <= epRange[1]))]
            
            else:
                resDf = resDf[((resDf['ZIP_INT'] >= stateRange[0]) & (resDf['ZIP_INT'] <= stateRange[1])) | 
                              (resDf['ZIP_INT'].isin(stateRange[2:]))]

            # We can drop the ZIP as int column
            resDf = resDf.drop(columns=['ZIP_INT'])

            return resDf, GEID.ZIP, 'ZIP Code', 'Vehicle Count'

        case 'MT' | 'TN' | 'VA':

            # Load the CSV
            resDf = pd.read_csv(dataDir / Path(f'emissions/evRegistrations/{stateAc}.csv'), low_memory=False)

            # These are keyed by County, so pull that out instead of ZIP
            resDf = resDf[['State', 'County', 'Registration Date', 'Vehicle Count']]

            return resDf, GEID.COUNTY, 'County', 'Vehicle Count'


        case 'CT':

            # Use the existing file we have
            resDf = pd.read_csv(dataDir / Path('spatial/ev_registration.csv'))

            # Drop unnecessary columns
            resDf = resDf[['Primary Customer City', 'Primary Customer State', 'Vehicle Year']]

            # Rename for standardization
            resDf = resDf.rename(columns={'Primary Customer City': 'City',
                                          'Primary Customer State': 'State', 
                                          'Vehicle Year': 'Vehicle Count'})
            
            # Filter to only CT
            resDf = resDf[resDf['State'] == stateAc]
            
            return resDf, GEID.CITY, 'City', 'Vehicle Count'
        
        case _:
            # Unrecognized acronym
            raise ValueError(f"Invalid state acronym of {stateAc}")



def FixFIPS(row: pd.Series, fipsCol: str, correctLen: int):

    # Extract the FIPS code
    fips = row[fipsCol]

    # If no value is provided, return a default -1 (string)
    if pd.isna(fips):
        return "-1"

    # Ensure that the decimal is cutoff
    fips = int(fips)

    # Return as a string
    fips = str(fips)
    if len(fips) == correctLen:
        return fips
    
    elif len(fips) == correctLen - 1:
        # Add the missing leading zero
        fips = f"0{fips}"

    elif len(fips) == correctLen - 2:
        # Add two missing leading zeros
        fips = f"00{fips}"
    
    else:
        print(row['BLOCKID'])
        raise RuntimeError(f"Invalid length {len(fips)} for FIPS code {fips}, assuming len {correctLen}.")
    
    return fips

def LoadBlockAssignments(stateAc: str, dataDir: Path = Path("./data")) -> pd.DataFrame:

    # Block assignment files (2010)
    url = "https://www.census.gov/geographies/reference-files/time-series/geo/block-assignment-files.2010.html#list-tab-361828852"

    # Construct the full filename
    stateFips = STATE_AC_TO_FIPS[stateAc]
    filename = dataDir / Path(f"blockAssignments/{stateAc}/BlockAssign_ST{stateFips}_{stateAc}_INCPLACE_CDP.txt")

    # Check that it exists
    if not filename.exists():
        msg = f"Block assignment file for {stateAc} not found, please visit {url}"
        raise RuntimeError(msg)

    # Load it as a CSV
    resDf = pd.read_csv(filename)

    # Recast the block and place FIPS as strings
    blockCol = "BLOCKID"
    placeCol = "PLACEFP"
    resDf[blockCol] = resDf.apply(FixFIPS, args=(blockCol, 15), axis=1)
    resDf[placeCol] = resDf.apply(FixFIPS, args=(placeCol, 5), axis=1)

    # Extract the county FIPS from the full block FIPS
    resDf['COUNTYFP'] = resDf.apply(lambda r: r[blockCol][0:5], axis=1)


    return resDf

def LoadBlockZCTAAssignments(stateAc: str, dataDir: Path = Path("./data")) -> pd.DataFrame:

    # Block to ZCTA assignment files:
    url = "https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html#zcta"

    # Construct the full filename
    filename = dataDir / Path(f"blockAssignments/block-to-zcta.txt")

    # Check that it exists
    if not filename.exists():
        msg = f"Block to ZCTA file {filename} not found, please visit {url}"
        raise RuntimeError(msg)
    
    # Load it as a CSV
    resDf = pd.read_csv(filename, delimiter="|", low_memory=False)

    # Only select the necessary columns
    resDf = resDf[['GEOID_TABBLOCK_20', 'GEOID_ZCTA5_20']]
    resDf = resDf.rename(columns={'GEOID_TABBLOCK_20': 'BLOCKFP', 'GEOID_ZCTA5_20': 'ZCTAFP'})

    # We can drop the rows without a ZCTA assignment
    #resDf = resDf.dropna(subset=['ZCTAFP'])

    # Recast them as strings, fixing leading 0s if needed
    resDf['BLOCKFP'] = resDf.apply(FixFIPS, args=('BLOCKFP', 15), axis=1)
    resDf['ZCTAFP'] = resDf.apply(FixFIPS, args=('ZCTAFP', 5), axis=1)

    # Only get blocks for this state
    stateFIPS = STATE_AC_TO_FIPS[stateAc]
    resDf = resDf[resDf['BLOCKFP'].str.contains(rf'^{stateFIPS}', regex=True)].reset_index(drop=True)

    return resDf




def LoadBlockPopulation(stateAc: str, dataDir: Path = Path("./data")) -> pd.DataFrame:

    # Construct the full filename
    filename = dataDir / Path(f"blockPopulation/{stateAc}/data.csv")

    # Check that it exists
    if not filename.exists():
        msg = f"Block population file for {stateAc} not found, please download the P1|RACE table for all blocks from data.census.gov"
    
    # Read in the csv
    resDf = pd.read_csv(filename)

    # We only need the first three columns
    resDf = resDf[resDf.columns[0:3]]

    # Drop the first row, as it is an extra header
    resDf = resDf.iloc[1:]

    # Rename the total population column to something more readable
    resDf = resDf.rename(columns={resDf.columns[-1]: 'POPULATION'})

    # Extract the actual FIPS code from the GEOID
    resDf['BLOCKFP'] = resDf.apply(lambda r: r['GEO_ID'].split('US')[1], axis=1)

    # Drop the other two columns; they are not needed
    resDf = resDf[['BLOCKFP', 'POPULATION']]

    # Cut out weird edge cases with poor data quality
    resDf = resDf[~resDf['POPULATION'].str.contains('r', regex=False, na=False)]

    # Ensure the population column is an int
    resDf['POPULATION'] = resDf['POPULATION'].astype(int)


    return resDf
    
def PlaceFIPSConverter(row: pd.Series, placeDict: dict, col: str):

    # Extract the ID as a string, account for an empty cell
    try:
        idStr = str(row[col])
    except:
        return ""
    
    # Check for the default -1 string
    if idStr == "-1":
        return ""
    
    # Make sure we're checking a valid place FIPS code
    if len(idStr) != 4 and len(idStr) != 5:
        raise RuntimeError(f"Place FIPS code of {idStr} is not length 4 or 5.")

    # Add a leading 0 if necessary
    if len(idStr) == 4:
        idStr = f"0{idStr}"

    # Check the dict for the matching GISJOIN ID
    if idStr in placeDict:
        return placeDict[idStr]
    else:
        return ""




def EmissionsPC(dataDir: Path, sfDir: Path, loadGraph: bool = True,
                graphsDir: Path = Path("./graphs"), stateAc: str = "VA"):


    ''' Outline
    Scenario: Proof that EVs reduce overall, macro-level emissions, for a given state.
    This is useful when determining what states benefit most from EVs as each state
    has a different energy production profile (some are greener than others).

    Want: Average emissions per vehicle mile traveled compared against
    number of registered EVs, for each county.

    Have: Total emissions and total vehicle miles traveled by city,
    and registered EVs per city.
    
    Need:
        1.) Calculate emissions/vehicle mile traveled for all cities (manual)
        2.) Estimate county level emissions/vehicle (via graph)
        3.) Calculate total county EV registrations (via graph, simple sum)
        4.) Join them and plot.

    NOTE: We can use the county data that is provided as a comparison of accuracy
    between kriging and areal overlap for avg emissions/vehicle.

    Emissions data from: https://catalog.data.gov/dataset/city-and-county-energy-profiles-60fbd

    EV Data from: www.atlasevhub.com/market-data/state-ev-registration-data/
    and https://catalog.data.gov/dataset/electric-vehicle-registration-data

    Citation for block -> ZCTA population validity: https://www.census.gov/data/data-tools/survey-explorer/geo.html

    '''

    # Generate a logger for this test case
    logger = logging.getLogger('EmissionsPC')
    logging.basicConfig(filename=f"./logs/emissionsPC{stateAc}.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Read in the emissions data
    # We only need the 'City' and 'County' sheets
    allEmissions = pd.read_excel(dataDir / 'cityAndCountyEmissions.xlsb',
                                 sheet_name=['City', 'County'])#, nrows=5000)
    cityEmissions = allEmissions['City']
    countyEmissions = allEmissions['County']

    # List of Excel column names of interest
    cityCols = {
        'A': 'StateId',
        'B': 'StateAbbr',
        'C': 'CityStateName',
        'D': 'CityId',
        'E': 'CityName',
        'AT': 'VehicleMilesTraveled',
        'AU': 'VehicleMilesTraveledPerCapita',
        'FA': 'ResidentialElectricityEmissions',
        'FB': 'ResidentialNaturalGasEmissions',
        'FC': 'CommericalElectricityEmissions',
        'FD': 'CommercialNaturalGasEmissions',
        'FE': 'IndustryElectricityEmissions',
        'FF': 'IndustryNaturalGasEmissions',
        'FG': 'OnRoadTransportationGasEmissions',
        'FH': 'OnRoadTransportationDieselEmissions'
        }
    
    cityEmissions = ExtractCols(cityEmissions, cityCols)

    # Do the same thing for the counties
    countyCols = {
        'A': 'StateId',
        'B': 'StateAbbr',
        'C': 'CountyStateName',
        'D': 'CountyId',
        'E': 'CountyName',
        'AT': 'VehicleMilesTraveled',
        'AU': 'VehicleMilesTraveledPerCapita',
        'FA': 'ResidentialElectricityEmissions',
        'FB': 'ResidentialNaturalGasEmissions',
        'FC': 'CommericalElectricityEmissions',
        'FD': 'CommercialNaturalGasEmissions',
        'FE': 'IndustryElectricityEmissions',
        'FF': 'IndustryNaturalGasEmissions',
        'FG': 'OnRoadTransportationGasEmissions',
        'FH': 'OnRoadTransportationDieselEmissions'
        }
    
    countyEmissions = ExtractCols(countyEmissions, countyCols)

    # We can drop the first four rows since they
    # are all headers
    cityEmissions = cityEmissions.iloc[4:].reset_index(drop=True)
    countyEmissions = countyEmissions.iloc[4:].reset_index(drop=True)

    # Get rid of invalid rows
    cityEmissions = cityEmissions.dropna()
    countyEmissions = countyEmissions.dropna()

    # For the cities, we need to get rid of the types
    # and the state abbr in the names.
    # All types (city, village, borough, etc.) start with lowercase
    # letters, so use that for a regex
    cityEmissions['CityName'] = cityEmissions['CityName'].str.replace(r'(\s[a-z]+)+', '', regex=True)
    cityEmissions['CityName'] = cityEmissions['CityName'].str.replace(' CDP', '')
    cityEmissions['CityName'] = cityEmissions['CityName'].str.replace(' county', '')
    cityEmissions['CityName'] = cityEmissions['CityName'].str.replace(' (balance)', '')

    # For the counties, the types don't start with a lowercase,
    # so add them in as unique cases
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' County', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' Borough', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' Census Area', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' City and Borough', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' Municipality', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' Parish', '')
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.replace(' city', '')

    # Additionally, make them all lowercase for consistency
    cityEmissions['CityName'] = cityEmissions['CityName'].str.lower()
    countyEmissions['CountyName'] = countyEmissions['CountyName'].str.lower()

    # We also need to extract the fips code WITH leading zeros
    cityEmissions['STATEFP'] = cityEmissions.apply(StateIntToFIPS, args=('StateId',), axis=1)
    countyEmissions['STATEFP'] = countyEmissions.apply(StateIntToFIPS, args=('StateId',), axis=1)

    # Now, load in info for cities and counties

    ### Cities, towns, etc. ###
    placeGdf = LoadShapefile(sfDir, 'place')

    # Make the city names lower case for consistency
    placeGdf['NAME'] = placeGdf['NAME'].str.lower()

    # TODO: For testing, pick 1 state
    placeGdf = placeGdf[placeGdf['STATEFP'] == STATE_AC_TO_FIPS[stateAc]]

    # Make a city name: GISJOIN dict
    cityDict = pd.Series(placeGdf['GISJOIN'].values, index=[placeGdf['NAME'], placeGdf['STATEFP']]).to_dict()

    # Convert city name, state to GISJOIN ID
    cityEmissions['GISJOIN'] = cityEmissions.apply(CityTupleIdConverter, args=(cityDict, 'CityName', 'STATEFP'), axis=1)

    # Remove cities we don't have an ID for
    cityEmissions = cityEmissions[cityEmissions['GISJOIN'] != ""]

    # TODO: For testing, pick 1 state
    cityEmissions = cityEmissions[cityEmissions['StateAbbr'] == stateAc]

    ### Counties ###

    # Use an older copy of the shapefile to match the data
    countyGdf = LoadShapefile(sfDir, 'county2020')

    # Lowercase names for consistency
    countyGdf['NAME'] = countyGdf['NAME'].str.lower()

    # TODO: For testing, only use one state
    countyGdf = countyGdf[countyGdf['STATEFP'] == STATE_AC_TO_FIPS[stateAc]]
    

    # Make a county FIPS code: GISJOIN dict
    countyDict = pd.Series(countyGdf['GISJOIN'].values, index=countyGdf['GEOID']).to_dict()

    # Convert county FIPS to GISJOIN
    countyEmissions['GISJOIN'] = countyEmissions.apply(CountyFIPSConverter, args=(countyDict, 'CountyId'), axis=1)

    # Drop rows we didn't have a match for
    countyEmissions = countyEmissions[countyEmissions['GISJOIN'] != ""]

    # TODO: For testing, pick 1 state
    countyEmissions = countyEmissions[countyEmissions['StateAbbr'] == stateAc]

    ### States ###

    # Doesn't require any work since we are using this for a layer
    stateGdf = LoadShapefile(sfDir, 'state')

    ### Population ###

    # Read in the block -> place assignment file
    blockAssignments = LoadBlockAssignments(stateAc)

    # Read in the block -> ZCTA assignment file
    blockZCTAAssignments = LoadBlockZCTAAssignments(stateAc)

    # Put it all together
    blockAssignments = pd.merge(blockAssignments, blockZCTAAssignments,
                                left_on='BLOCKID', right_on='BLOCKFP')
    

    # Read in the population data by block
    blockPopulation = LoadBlockPopulation(stateAc)

    # Now, we have block -> county, block -> place, block -> ZCTA, and per block population
    # We need to aggregate singularly and pairwise (block, county, ZCTA, block/county, etc.)

    # First, join everything into one dataframe
    blockDf = pd.merge(blockAssignments, blockPopulation, left_on='BLOCKID', right_on='BLOCKFP')

    # We need GISJOIN IDS for both places, counties, and ZCTAs
    # For places, we can use the placeGdf to make a map from FIPS to GISJOIN
    placeDict = pd.Series(placeGdf['GISJOIN'].values, index=placeGdf['PLACEFP']).to_dict()
    blockDf['PLACEGISJOIN'] = blockDf.apply(PlaceFIPSConverter, args=(placeDict, 'PLACEFP'), axis=1)

    # Drop rows we didn't have a match for (this will include the default -1 value rows)
    blockDf = blockDf[blockDf['PLACEGISJOIN'] != ""]

    # We can reuse the county dict from before
    blockDf['COUNTYGISJOIN'] = blockDf.apply(CountyFIPSConverter, args=(countyDict, 'COUNTYFP'), axis=1)

    # Drop rows we didn't have a match for
    blockDf = blockDf[blockDf['COUNTYGISJOIN'] != ""]

    # For ZCTAs, we need to load in the ZCTA shapefile
    zctaGdf = LoadShapefile(sfDir, 'zcta')
    
    # Convert from ZCTA to GISJOIN
    zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()
    blockDf['ZCTAGISJOIN'] = blockDf.apply(ZctaIdConverter, args=(zctaDict, 'ZCTAFP'), axis=1)

    # Drop rows with ZCTAs we didn't have
    blockDf = blockDf[blockDf['ZCTAGISJOIN'] != ""]

    # Get place, county, and ZCTA populations separately
    placePopulation = blockDf.groupby('PLACEGISJOIN')['POPULATION'].sum().reset_index()
    countyPopulation = blockDf.groupby('COUNTYGISJOIN')['POPULATION'].sum().reset_index()
    zctaPopulation = blockDf.groupby('ZCTAGISJOIN')['POPULATION'].sum().reset_index()

    # Now, do pairwise groupby
    placeAndCountyPop = blockDf.groupby(['PLACEGISJOIN', 'COUNTYGISJOIN'])['POPULATION'].sum().reset_index()
    placeAndZctaPop = blockDf.groupby(['PLACEGISJOIN', 'ZCTAGISJOIN'])['POPULATION'].sum().reset_index()
    zctaAndCountyPop = blockDf.groupby(['ZCTAGISJOIN', 'COUNTYGISJOIN'])['POPULATION'].sum().reset_index()

    # NOTE: We reset the indices to make the GISJOIN ids actual columns, accessible inside pd.Dataframe.apply

    # Setup dataframes for comparison later
    countyGdfComparison = countyGdf[['GISJOIN', 'ALAND', 'AWATER', 'Shape_Area']]
    countyGdfComparison = pd.merge(countyGdfComparison, countyPopulation, left_on="GISJOIN", right_on="COUNTYGISJOIN")

    # Population density: Pop / km2
    countyGdfComparison['POPDENSITY'] = countyGdfComparison['POPULATION'] / (countyGdfComparison['Shape_Area'] / 10.**6)
    countyGdfComparison['POPLANDDENSITY'] = countyGdfComparison['POPULATION'] / (countyGdfComparison['ALAND'] / 10.**6)
    countyGdfComparison['LOGPOP'] = np.log(countyGdfComparison['POPULATION'])

    # Land to water ratio
    countyGdfComparison['LANDWATERRATIO'] = countyGdfComparison['ALAND'] / countyGdfComparison['AWATER']


    ### Graph Setup ###
    graph = GranularityGraph(f'emissionsPCGraph{stateAc}',
                             Path(f'./logs/emissionsPCGraph{stateAc}.log'))

    # If specified, try loading a graph from disk first
    loadGraphStatus = Status.NOTEXISTS
    if loadGraph:
        loadGraphStatus = graph.LoadGraph(Path("./graphs"))

    # If needed, create a fresh graph
    if loadGraphStatus != Status.SUCCESS:

        # Construct the graph, layer by layer

        msg = "Adding City (place)-County layer..."
        print(msg)
        logger.info(msg)
        graph = AddLevel(graph, placeGdf, countyGdf,
                         n1Type=GEID.CITY, n2Type=GEID.COUNTY)
        
        msg = "Adding County-State layer..."
        print(msg)
        logger.info(msg)
        graph = AddLevel(graph, countyGdf, stateGdf,
                         n1Type=GEID.COUNTY, n2Type=GEID.STATE)
        
        msg = "Adding City (place)-State layer..."
        print(msg)
        logger.info(msg)
        graph = AddLevel(graph, placeGdf, stateGdf,
                         n1Type=GEID.CITY, n2Type=GEID.STATE)
        
        msg = "Adding ZCTA-county layer..."
        print(msg)
        logger.info(msg)
        graph = AddLevel(graph, zctaGdf, countyGdf,
                        n1Type=GEID.ZCTA, n2Type=GEID.COUNTY)
        
        # Now, we will also need the city-county graph based on population

        # First, update all the place, county, and ZCTA nodes
        msg = "Updating City (place) nodes..."
        print(msg)
        logger.info(msg)
        placePopulation.apply(UpdateNodePop, args=(graph, 'PLACEGISJOIN', 'POPULATION', EdgeType.POPULATION, GEID.CITY), axis=1)

        msg = "Updating County nodes..."
        print(msg)
        logger.info(msg)
        countyPopulation.apply(UpdateNodePop, args=(graph, 'COUNTYGISJOIN', 'POPULATION', EdgeType.POPULATION, GEID.COUNTY), axis=1)  

        msg = "Updating ZCTA nodes..."
        print(msg)
        logger.info(msg)
        zctaPopulation.apply(UpdateNodePop, args=(graph, 'ZCTAGISJOIN', 'POPULATION', EdgeType.POPULATION, GEID.ZCTA), axis=1)  


        # Now, add the weights to the edges for the population as well
        msg = "Adding City (place) - County population layer..."
        print(msg)
        logger.info(msg)
        placeAndCountyPop.apply(AddPopEdge, args=(graph, 'PLACEGISJOIN', 'COUNTYGISJOIN', 'POPULATION', GEID.CITY, GEID.COUNTY), axis=1)

        msg = "Adding City (place) - ZCTA population layer..."
        print(msg)
        logger.info(msg)
        placeAndZctaPop.apply(AddPopEdge, args=(graph, 'PLACEGISJOIN', 'ZCTAGISJOIN', 'POPULATION', GEID.CITY, GEID.ZCTA), axis=1)

        msg = "Adding ZCTA - County population layer..."
        print(msg)
        logger.info(msg)
        zctaAndCountyPop.apply(AddPopEdge, args=(graph, 'ZCTAGISJOIN', 'COUNTYGISJOIN', 'POPULATION', GEID.ZCTA, GEID.COUNTY), axis=1)


        # Save the graph
        msg = "Saving the graph..."
        print(msg)
        logger.info(msg)
        graph.SaveGraph(graphsDir)

        # Load it again to make sure we have the correct objects
        graph.LoadGraph(graphsDir)

    else:
        # Log that we loaded the graph
        msg = "Graph loaded successfully."
        print(msg)
        logger.info(msg)

    # Now, we can do the work
    
    # Get a gator object
    gator = Gator(graph, Path(f'./logs/EmissionsPCGator{stateAc}.log'))

    # Sum the total emissions for each row
    eCols = [c for c in cityEmissions.columns if 'Emissions' in c]
    cityEmissions['TotalEmissions'] = cityEmissions[eCols].sum(axis=1)
    countyEmissions['TotalEmissions'] = countyEmissions[eCols].sum(axis=1)

    # Calculate avg per vehicle mile traveled
    cityEmissions['EmissionsPerVM'] = cityEmissions['TotalEmissions'] / cityEmissions['VehicleMilesTraveled']
    countyEmissions['EmissionsPerVM'] = countyEmissions['TotalEmissions'] / countyEmissions['VehicleMilesTraveled']

    # Normalize it
    normFactor = max(cityEmissions['EmissionsPerVM'].max(), countyEmissions['EmissionsPerVM'].max())
    cityEmissions['EmissionsPerVM'] /= normFactor
    countyEmissions['EmissionsPerVM'] /= normFactor

    '''
    import sys
    sys.path.append("/home/srpaulis/granularity-tree")
    from tests.util import ManualBlockKriging

    # Testing rows
    controlCounty = countyEmissions[countyEmissions['GISJOIN'] == "G0900010"]
    problemCounty = countyEmissions[countyEmissions['GISJOIN'] == "G0900030"]

    controlCountyCityIds = ['G09004790',
                      'G09008000',
                      'G09009050',
                      'G09018430',
                      'G09018936',
                      'G09019480',
                      'G09026698',
                      'G09033690',
                      'G09047515',
                      'G09050576',
                      'G09052910',
                      'G09055990',
                      'G09063620',
                      'G09063900',
                      'G09068100',
                      'G09068240',
                      'G09073000',
                      'G09074303',
                      'G09077278',
                      'G09083360',
                      'G09083586',
                      'G09071215']
    
    problemCountyCityIds = ['G09008420',
                        'G09012370',
                        'G09022420',
                        'G09022700',
                        'G09031270',
                        'G09054660',
                        'G09022420',
                        'G09037000',
                        'G09044690',
                        'G09046450',
                        'G09047290',
                        'G09050370',
                        'G09052210',
                        'G09069010',
                        'G09074655',
                        'G09075940',
                        'G09082660',
                        'G09084970',
                        'G09087140',
                        ]
    
    controlCountyCities = cityEmissions[cityEmissions['GISJOIN'].isin(controlCountyCityIds)]
    problemCountyCities = cityEmissions[cityEmissions['GISJOIN'].isin(problemCountyCityIds)]

    controlCountyNode = graph.GetNode("G0900010", GEID.COUNTY)
    problemCountyNode = graph.GetNode("G0900030", GEID.COUNTY)

    controlRows = []
    for id in controlCountyCityIds:
        n = graph.GetNode(id, GEID.CITY)
        controlRows.append({'GISJOIN': id, 'geometry': n.geometry})
    
    problemRows = []
    for id in problemCountyCityIds:
        n = graph.GetNode(id, GEID.CITY)
        problemRows.append({'GISJOIN': id, 'geometry': n.geometry})

    # Add the geometries to the dataframes
    controlGeoDf = pd.DataFrame(data=controlRows)
    problemGeoDf = pd.DataFrame(data=problemRows)

    controlCountyCities = pd.merge(controlCountyCities, controlGeoDf, on='GISJOIN')
    problemCountyCities = pd.merge(problemCountyCities, problemGeoDf, on='GISJOIN')

    #problemCountyCities = problemCountyCities.tail(n=4).reset_index()

    problemCountyCities = problemCountyCities.drop_duplicates(subset=['GISJOIN']).reset_index()


    #controlCountyGt,Cgt, Dgt, Wgt  = ManualBlockKriging(controlCountyCities, 'GISJOIN',
    #                                              'EmissionsPerVM', 'geometry', controlCountyNode.geometry,
    #                                              VariogramModel.EXPONENTIAL)


    #problemCountyGt, Cprob, Dprob, Wprob = ManualBlockKriging(problemCountyCities, 'GISJOIN',
    #                                                          'EmissionsPerVM', 'geometry', problemCountyNode.geometry,
    #                                                          VariogramModel.EXPONENTIAL)

    '''

    # Do an averaging using both areal overlap and kriging from cities to counties
    msg = "Areal overlap equalization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    arealResDf = gator.SpatialEqualize(cityEmissions, countyEmissions,
                                       GEID.CITY, GEID.COUNTY, 'GISJOIN', 'GISJOIN',
                                       'EmissionsPerVM', None, None, AggMethod.MEAN,
                                       EdgeType.AREA, ignoreMissing=True, ignoreIncomplete=True)
    arealRuntime = time.time() - st
    msg = "Kriging equalization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    krigingResDf = gator.SpatialEqualize(cityEmissions, countyEmissions,
                                       GEID.CITY, GEID.COUNTY, 'GISJOIN', 'GISJOIN',
                                       'EmissionsPerVM', None, None, AggMethod.KRIGING,
                                       EdgeType.AREA, ignoreMissing=True, ignoreIncomplete=True,
                                       distFunction=distFunc, model=VariogramModel.LINEAR,
                                       binSize=50.)
    krigingRuntime = time.time() - st

    # Do an averaging via population as well
    msg = "Population overlap equalization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    populationResDf = gator.SpatialEqualize(cityEmissions, countyEmissions,
                                       GEID.CITY, GEID.COUNTY, 'GISJOIN', 'GISJOIN',
                                       'EmissionsPerVM', None, None, AggMethod.MEAN,
                                       EdgeType.POPULATION, ignoreMissing=True, ignoreIncomplete=True)
    populationRuntime = time.time() - st

    # Do a rename for clarity when joining later
    populationResDf = populationResDf.rename(columns={'EmissionsPerVM': 'EmissionsPerVM_Pop'})

    #print(arealResDf)
    #print(krigingResDf)

    # Get the groundtruth values
    countyGt = countyEmissions[['GISJOIN', 'EmissionsPerVM']]
    countyGt = countyGt.rename(columns={'EmissionsPerVM': 'EmissionsPerVM_GT'})

    # Generated a combined dataset that averages all estimates together
    avgResDf = pd.merge(arealResDf, krigingResDf, left_index=True, right_on="GISJOIN")
    avgResDf = pd.merge(avgResDf, populationResDf, left_on='GISJOIN', right_index=True)

    # Calculate the combined estimate
    avgResDf['AvgEstEmissions'] = (avgResDf['EmissionsPerVM'] + 
                                   avgResDf['EmissionsPerVM_est'] +
                                   avgResDf['EmissionsPerVM_Pop']) / 3.

    #print(countyEmissions)

    # Add the 'true' value via joining
    arealResDf = pd.merge(arealResDf, countyGt, left_index=True, right_on='GISJOIN')
    krigingResDf = pd.merge(krigingResDf, countyGt, on='GISJOIN')
    populationResDf = pd.merge(populationResDf, countyGt, left_index=True, right_on='GISJOIN')
    avgResDf = pd.merge(avgResDf, countyGt, on='GISJOIN')

    # Calculate error
    errorCol = 'RelError'
    arealResDf[errorCol+'_a'] = np.abs(arealResDf['EmissionsPerVM'] - arealResDf['EmissionsPerVM_GT']) / arealResDf['EmissionsPerVM_GT']
    krigingResDf[errorCol+'_k'] = np.abs(krigingResDf['EmissionsPerVM_est'] - krigingResDf['EmissionsPerVM_GT']) / krigingResDf['EmissionsPerVM_GT']
    populationResDf[errorCol + '_p'] = np.abs(populationResDf['EmissionsPerVM_Pop'] - populationResDf['EmissionsPerVM_GT']) / populationResDf['EmissionsPerVM_GT']
    avgResDf[errorCol + '_avg'] = np.abs(avgResDf['AvgEstEmissions'] - avgResDf['EmissionsPerVM_GT']) / avgResDf['EmissionsPerVM_GT']

    # Calculate variance of error
    arealVar = arealResDf[errorCol+'_a'].var()
    krigingVar = krigingResDf[errorCol+'_k'].var()
    populationVar = populationResDf[errorCol + '_p'].var()
    avgVar = avgResDf[errorCol + '_avg'].var()

    # Join the results to compare directly
    errorDf = pd.merge(arealResDf[['GISJOIN', errorCol + '_a']], krigingResDf[['GISJOIN', errorCol +'_k']], on='GISJOIN')
    errorDf = pd.merge(errorDf, populationResDf[['GISJOIN', errorCol + '_p']], on='GISJOIN')
    errorDf = pd.merge(errorDf, avgResDf[['GISJOIN', errorCol + '_avg']], on='GISJOIN')

    # Get pairwise average error differences
    errorDf['Error Difference: A-K'] = errorDf[errorCol + '_a'] - errorDf[errorCol + '_k']
    avgErrorDiffAK = errorDf['Error Difference: A-K'].mean()
    medErrorDiffAK = errorDf['Error Difference: A-K'].median()

    errorDf['Error Difference: A-P'] = errorDf[errorCol + '_a'] - errorDf[errorCol + '_p']
    avgErrorDiffAP = errorDf['Error Difference: A-P'].mean()
    medErrorDiffAP = errorDf['Error Difference: A-P'].median()

    errorDf['Error Difference: P-K'] = errorDf[errorCol + '_p'] - errorDf[errorCol + '_k']
    avgErrorDiffPK = errorDf['Error Difference: P-K'].mean()
    medErrorDiffPK = errorDf['Error Difference: P-K'].median()

    # Redo it for the avg (yes, this could have been a loop and a function)
    errorDf['Error Difference: Avg-A'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_a']
    avgErrorDiffAvgA = errorDf['Error Difference: Avg-A'].mean()
    medErrorDiffAvgA = errorDf['Error Difference: Avg-A'].median()

    errorDf['Error Difference: Avg-K'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_k']
    avgErrorDiffAvgK = errorDf['Error Difference: Avg-K'].mean()
    medErrorDiffAvgK = errorDf['Error Difference: Avg-K'].median()

    errorDf['Error Difference: Avg-P'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_p']
    avgErrorDiffAvgP = errorDf['Error Difference: Avg-P'].mean()
    medErrorDiffAvgP = errorDf['Error Difference: Avg-P'].median()

    # Caclulate singular error averages
    avgErrorAreal = errorDf[errorCol + '_a'].mean()
    medErrorAreal = errorDf[errorCol + '_a'].median()

    avgErrorKriging = errorDf[errorCol + '_k'].mean()
    medErrorKriging = errorDf[errorCol + '_k'].median()

    avgErrorPopulation = errorDf[errorCol + '_p'].mean()
    medErrorPopulation = errorDf[errorCol + '_p'].median()

    avgErrorAvg = errorDf[errorCol + '_avg'].mean()
    medErrorAvg = errorDf[errorCol + '_avg'].median()


    # Print out average and median error difference for each pair of methods
    print(f"\nAreal - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffAK*100.}")
    print(f"Median error difference (in %): {medErrorDiffAK*100.}")
    print(f"\nAreal - Population")
    print(f"Average error difference (in %): {avgErrorDiffAP*100.}")
    print(f"Median error difference (in %): {medErrorDiffAP*100.}")
    print(f"\nPopulation - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffPK*100.}")
    print(f"Median error difference (in %): {medErrorDiffPK*100.}")

    print(f"\n\nAveraged - Areal")
    print(f"Average error difference (in %): {avgErrorDiffAvgA*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgA*100.}")
    print(f"\nAveraged - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffAvgK*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgK*100.}")
    print(f"\nAveraged - Population")
    print(f"Average error difference (in %): {avgErrorDiffAvgP*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgP*100.}")

    # Print average errors by method
    print(f"\n\n\nAreal Mean Error (in %): {avgErrorAreal*100.}")
    print(f"Areal Median Error (in %): {medErrorAreal*100.}")
    print(f"\nKriging Mean Error (in %): {avgErrorKriging*100.}")
    print(f"Kriging Median Error (in %): {medErrorKriging*100.}")
    print(f"\nPopulation Mean Error (in %): {avgErrorPopulation*100.}")
    print(f"Population Median Error (in %): {medErrorPopulation*100.}")
    print(f"\nAveraged Estimate Mean Error (in %): {avgErrorAvg*100.}")
    print(f"Averaged Estimate Median Error (in %): {medErrorAvg*100.}")

    # Print error variance by method
    print(f"\n\n\nAreal Error Variance: {arealVar}")
    print(f"Kriging Error Variance: {krigingVar}")
    print(f"Population Error Variance: {populationVar}")
    print(f"Averaged Estimate Error Variance: {avgVar}")

    # Print runtime by method
    print(f"\n\n\nAreal runtime: {arealRuntime}")
    print(f"Kriging runtime: {krigingRuntime}")
    print(f"Population runtime: {populationRuntime}")

    # Try to do some investigation into charactersitcs of oddly performing counties
    # Join the results with the comparison GDF
    errorComparisonGdf = pd.merge(errorDf, countyGdfComparison, on='GISJOIN')

    #print(errorComparisonGdf)

    # Plot the error rate against each characterstic
    errorCols = {errorCol+'_a': 'red', errorCol+'_k': 'blue', errorCol+'_p': 'green'}
    charCols = ['POPULATION', 'POPDENSITY', 'POPLANDDENSITY', 'LANDWATERRATIO', 'LOGPOP']

    for characteristic in charCols:

        #TODO: Remove to plot everything
        break

        # Make a new figure
        fig, ax = plt.subplots(figsize=FIG_SIZE)

        # Set labels and font sizes
        plt.xlabel(characteristic, fontsize=FIG_LABEL_FONT_SIZE)
        plt.ylabel('Relative Error', fontsize=FIG_LABEL_FONT_SIZE)
        plt.title(f'Error rate vs. {characteristic} for {stateAc}', fontsize=FIG_TITLE_FONT_SIZE)

        # Fix font sizes for axis ticks
        ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
        ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

        # Plot each error rate
        for ec in errorCols:
            errorComparisonGdf.plot(x=characteristic, y=ec, kind='line', ax=ax, color=errorCols[ec])

    # Do the same thing, but with the error differences
    errorCols = {'Error Difference: A-K': 'red',
                 'Error Difference: A-P': 'blue',
                 'Error Difference: P-K': 'green'
                 }
    

    for characteristic in charCols:

        #TODO: Remove to plot everything
        break

        # Make a new figure
        fig, ax = plt.subplots(figsize=FIG_SIZE)

        # Set labels and font sizes
        plt.xlabel(characteristic, fontsize=FIG_LABEL_FONT_SIZE)
        plt.ylabel('Relative Error Difference', fontsize=FIG_LABEL_FONT_SIZE)
        plt.title(f'Error difference vs. {characteristic} for {stateAc}', fontsize=FIG_TITLE_FONT_SIZE)

        # Fix font sizes for axis ticks
        ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
        ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

        # Plot each error rate
        for ec in errorCols:
            errorComparisonGdf.plot(x=characteristic, y=ec, kind='line', ax=ax, color=errorCols[ec])

    # Now, we want the EVs at the county level
    regsDf, keyType, keyCol, dataCol = LoadEVRegistration(Path('./evaluation'), stateAc)

    # We need the regs states as FIPS codes
    regsDf['STATEFIPS'] = regsDf.apply(StateAcToFips, args=(STATE_AC_TO_FIPS, 'State'), axis=1)

    # Drop rows with an invalid state
    regsDf = regsDf[regsDf['STATEFIPS'] != '']

    if keyType == GEID.CITY:

        # We need to convert from city name to GISJOIN
        regsDf['GISJOIN'] = regsDf.apply(CityTupleIdConverter, args=(cityDict, keyCol, 'STATEFIPS'), axis=1)

        # Remove cities that we didn't recognize
        regsDf = regsDf[regsDf['GISJOIN'] != '']
    
    if keyType == GEID.COUNTY:

        # Convert county name to GISJOIN

        # We're only looking at one state at a time, so no need to account
        # for duplicate county names

        # First, format the county names to match the countyEmissions DF
        regsDf['County'] = regsDf['County'].str.replace(' County', '')
        regsDf['County'] = regsDf['County'].str.replace(' Borough', '')
        regsDf['County'] = regsDf['County'].str.replace(' Census Area', '')
        regsDf['County'] = regsDf['County'].str.replace(' City and Borough', '')
        regsDf['County'] = regsDf['County'].str.replace(' Municipality', '')
        regsDf['County'] = regsDf['County'].str.replace(' Parish', '')
        regsDf['County'] = regsDf['County'].str.replace(' city', '')

        regsDf['County'] = regsDf['County'].str.lower()

        # Do a join on the county name to get GISJOIN ids
        regsDf = pd.merge(regsDf, countyEmissions[['CountyName', 'GISJOIN']],
                          left_on='County', right_on='CountyName')

    if keyType == GEID.ZIP:

        # We need to convert from ZIP to ZCTA first
        zctaGdf = LoadShapefile(sfDir, 'zcta')
        ztzGdf = gpd.read_file("./data/zipToZcta.csv")

        # Make a map from ZIP to ZCTA
        ztzDict = pd.Series(ztzGdf['zcta'].values, index=ztzGdf['ZIP_CODE']).to_dict()

        # Do the actual conversion
        regsDf[ntdas.ZCTA_COL] = regsDf.apply(ZipZctaConverter, args=(ztzDict, keyCol), axis=1)

        # Then, convert from ZCTA to GISJOIN
        zctaDict = pd.Series(zctaGdf['GISJOIN'].values, index=zctaGdf['ZCTA5CE20']).to_dict()
        regsDf['GISJOIN'] = regsDf.apply(ZctaIdConverter, args=(zctaDict,), axis=1)

        # Drop rows with ZIPS we didn't have
        #print(regsDf)
        regsDf = regsDf[regsDf['GISJOIN'] != ""]

        #fig, ax = plt.subplots()
        #zctaGdf.plot(ax=ax, color='red')
        #countyGdf.plot(ax=ax)
        #zctaGdf.plot(ax=ax, color='red')
        #plt.show()
        
        # Make sure the key type is updated
        keyType = GEID.ZCTA

        #quit()


    # We already have city-county information in the graph,
    # so go ahead and do the aggregation

    # Make sure the data column is a float for mathmatical operations
    regsDf[dataCol] = regsDf[dataCol].astype(np.float64)

    if keyType == GEID.COUNTY:

        # We don't need to use the gator, we can just do a groupby
        regsResDf = regsDf.groupby('GISJOIN').sum()

        # We only need one column
        regsResDf = regsResDf[[dataCol]]

        # Can't aggregate via population for comparison
        regsResPopDf = None

    else:

        regsResDf =  gator.SpatialEqualize(regsDf, countyEmissions, keyType, GEID.COUNTY,
                                        'GISJOIN', 'GISJOIN', dataCol, None, None,
                                        AggMethod.SUM, EdgeType.AREA, ignoreMissing=True,
                                        ignoreIncomplete=True)
        
        # Also do the aggregation by population for comparison
        regsResPopDf = gator.SpatialEqualize(regsDf, countyEmissions, keyType, GEID.COUNTY,
                                                'GISJOIN', 'GISJOIN', dataCol, None, None,
                                                AggMethod.SUM, EdgeType.POPULATION, ignoreMissing=True,
                                                ignoreIncomplete=True)
            

    # For clarity, rename the 'Vehicle Year' column
    regsResDf = regsResDf.rename(columns={dataCol: 'EV_Count'})
    if not regsResPopDf is None:
        regsResPopDf = regsResPopDf.rename(columns={dataCol: 'EV_Count_Pop'})

    # Do some renames for looping purposes
    krigingResDf = krigingResDf.rename(columns={'EmissionsPerVM_est': 'EmissionsPerVM'})
    populationResDf = populationResDf.rename(columns={'EmissionsPerVM_Pop': 'EmissionsPerVM'})

    # Put everything in a dictionary for organization
    resDfs = {'Areal': arealResDf,
               'Kriging': krigingResDf,
               'Population': populationResDf,
               'Averaged': avgResDf}
    
    # Join the emissions results with the EV registration
    joinedFinalDfs = {}
    for k in resDfs:
        joinedFinalDfs[k] = pd.merge(resDfs[k], regsResDf, left_on='GISJOIN', right_index=True)

        # Do the same with the population-based EV registration data, if applicable
        if not regsResPopDf is None:
            joinedFinalDfs[k + ' (Pop-based EVs)'] = pd.merge(resDfs[k], regsResPopDf, left_on='GISJOIN', right_index=True)

    if not regsResPopDf is None:
        # Join with the regular regsResDf for comparison of EV registration counts
        regsComparisonDf = pd.merge(regsResDf, regsResPopDf, left_index=True, right_index=True)

        # Calculate relative difference, using the areal version as "ground truth"
        regsComparisonDf['Percent Difference'] = ((regsComparisonDf['EV_Count_Pop'] - regsComparisonDf['EV_Count']) / regsComparisonDf['EV_Count'])

        # Get statistics for the difference
        regsMeanDiff = regsComparisonDf['Percent Difference'].mean()*100.
        regsMedDiff = regsComparisonDf['Percent Difference'].median()*100.
        regsDiffVar = regsComparisonDf['Percent Difference'].var()

        print(regsComparisonDf)
        print('\nStatistics for difference between areal and population-based methods for EV registrations')
        print(f'Mean percent difference: {regsMeanDiff}')
        print(f'Median percent difference: {regsMedDiff}')
        print(f'Error difference variance: {regsDiffVar}')

    else:
        regsComparisonDf = None


    # Sort for better plotting
    for k in joinedFinalDfs:

        if 'Pop-based' in k:
            # Do a rename for looping first
            joinedFinalDfs[k] = joinedFinalDfs[k].rename(columns={'EV_Count_Pop': 'EV_Count'})
        
        joinedFinalDfs[k] = joinedFinalDfs[k].sort_values('EV_Count')

    # Setup the figure(s)
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    allAxes = {'Areal': ax}

    # Set labels and font sizes
    plt.xlabel('EV Count', fontsize=FIG_LABEL_FONT_SIZE)
    plt.ylabel('Emissions per Vehicle Mile (MT of CO2e/mi)', fontsize=FIG_LABEL_FONT_SIZE)
    plt.title(f'Total Emissions per Vehicle Mile Traveled by EV Count for {stateAc}', fontsize=FIG_TITLE_FONT_SIZE)

    # Fix font sizes for axis ticks
    ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
    ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

    allAxes = {'Areal': ax}

    # Do the same for the pop-based EV registrations, if applicable
    if not regsResPopDf is None:
        fig, axp = plt.subplots(figsize=FIG_SIZE)

        # Set labels and font sizes
        plt.xlabel('EV Count (Pop-based)', fontsize=FIG_LABEL_FONT_SIZE)
        plt.ylabel('Emissions per Vehicle Mile (MT of CO2e/mi)', fontsize=FIG_LABEL_FONT_SIZE)
        plt.title(f'Total Emissions per Vehicle Mile Traveled by Pop-based EV Count for {stateAc}', fontsize=FIG_TITLE_FONT_SIZE)

        # Fix font sizes for axis ticks
        axp.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
        axp.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)
        
        allAxes['Population'] = axp

    # Plot the results
    colors = {}
    for k in joinedFinalDfs:
        if 'Areal' in k:
            colors[k] = 'red'
        elif 'Kriging' in k:
            colors[k] = 'blue'
        elif 'Population' in k:
            colors[k] = 'black'
        elif 'Averaged' in k:
            colors[k] = 'orange'
    

    names = []
    popNames = []
    for k in joinedFinalDfs:
        curDf = joinedFinalDfs[k]
        if 'Pop-based' in k:
            curDf.plot(x='EV_Count', y='EmissionsPerVM', kind='line', ax=allAxes['Population'], color=colors[k])
            popNames.append(k)
        else:
            curDf.plot(x='EV_Count', y='EmissionsPerVM', kind='line', ax=allAxes['Areal'], color=colors[k])
            names.append(k)

    # Plot the ground truth as well
    joinedFinalDfs['Areal'].plot(x='EV_Count', y='EmissionsPerVM_GT', kind='line', ax=allAxes['Areal'], color='green')
    names.append('Ground Truth')
    allAxes['Areal'].legend(names)

    if not regsResPopDf is None:
        joinedFinalDfs['Population'].plot(x='EV_Count', y='EmissionsPerVM_GT', kind='line', ax=allAxes['Population'], color='green')
        popNames.append('Ground Truth')
        allAxes['Population'].legend(popNames)
    
    print(f'\nFinished {stateAc} analysis.\n')

    return errorDf, errorCol


def ExtractFIPSFromGEOID(row: pd.Series, geoIdCol: str) -> str:


    # Grab the geoId
    geoId = row[geoIdCol]

    # Find the 'US' splitter
    usIndex = geoId.index('US')

    # Grab all the numbers that come after the splitter
    fips = geoId[usIndex+2:]

    return fips

def StateFIPSConverter(row: pd.Series, stateDict: dict, col: str):

        # Extract the ID as a string, accounting for
    # an empty cell
    try:
        idStr = str(row[col])
    except:
        return ""
    
    # Make sure we're checking a valid state GEOID
    if len(idStr) != 1 and len(idStr) != 2:
        raise RuntimeError(f"GEOID of {idStr} is not length 1 or 2.")

    # Add a leading 0 if necessary
    if len(idStr) == 1:
        idStr = f"0{idStr}"
    
    # Check the dict for the matching GISJOIN ID
    if idStr in stateDict:
        return stateDict[idStr]
    
    else:
        return ""
    


def LoadCountyPopulation(dataDir: Path = Path("./data")) -> pd.DataFrame:


    # Construct the full filename
    filename = dataDir / Path("county-pop-2020.csv")

    # Check that it exists
    if not filename.exists():
        msg = f"County population file not found, please download the P1|Race table for all counties from data.census.gov"
    
    # Read it in
    resDf = pd.read_csv(filename)

    # We only need the first three columns
    resDf = resDf[resDf.columns[0:3]]

    # Drop the first row, as it is an extra header
    resDf = resDf.iloc[1:]

    # Rename the population column for readability
    resDf = resDf.rename(columns={resDf.columns[-1]: 'POPULATION'})

    # Extract the actual FIPS code from the provided GEOID
    resDf['COUNTYFP'] = resDf.apply(lambda r: r['GEO_ID'].split('US')[1], axis=1)

    # Only keep the needed columns
    resDf = resDf[['COUNTYFP', 'POPULATION']]

    # Ensure the population column in an int
    resDf['POPULATION'] = resDf['POPULATION'].astype(int)

    return resDf

def LoadStatePopulation(dataDir: Path = Path("./data")) -> pd.DataFrame:

    # Construct the full filename
    filename = dataDir / Path("state-pop-2020.csv")

    # Check that it exists
    if not filename.exists():
        msg = f"State population file not found, please download the P1|Total Population table for all states from data.census.gov"
    
    # Read it in
    resDf = pd.read_csv(filename)

    # We can drop the first column
    resDf = resDf[resDf.columns[1:]]

    # Each remaining column is a state
    # We need to translate to integers

    for c in resDf.columns:
        # Strip out commas before casting as an int
        resDf[c] = resDf[c].str.replace(',', '', regex=False).astype(int)

    # We also need to assign the correct FIPS codes
    # While they are in alphabetical order, FIPS codes are not contiguous,
    # so we need a map
    colRenames = {}
    for c in resDf.columns:
        colRenames[c] = STATE_AC_TO_FIPS[STATE_TO_ACRO[c]]
    
    resDf = resDf.rename(columns=colRenames)

    # For joining, we need to make each state a row instead
    # The index is now the state FIPS code
    resDf = resDf.transpose().reset_index()

    # Sanity check
    assert len(resDf.columns) == 2

    # Rename the columns for clarity
    resDf = resDf.rename(columns={resDf.columns[0]: 'STATEFP', 
                                  resDf.columns[1]: 'POPULATION'})

    return resDf






def IncomeVsPolicy(dataDir: Path, sfDir: Path, loadGraph: bool = True,
                   graphsDir: Path = Path("./graphs")):
    
    ''' Outline

    Goal: See if there is a correlation between affluence (median income) and the number
    of "green" policies enacted in a state.

    Want: Policy data at a state level, median income at a state level
    Have: Policy data at a state level, median income at a county level.

    Need: Aggregate median income from county to state

    NOTE: We actually HAVE median income at the state level, so we can use that
    for accuracy comparison betwen kriging and areal overlap.

    NOTE: The median income data are 1-year estimates from ACS, downloaded from 
    the Census database.

    NOTE: The policy data is from https://www.climatepolicydashboard.org/

    '''


    # Generate a logger for this test case
    logger = logging.getLogger('IncomeVsPolicy')
    logging.basicConfig(filename=f"./logs/incomeVsPolicy.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Read in the policy data
    rawPolicyDfs = pd.read_excel(dataDir / 'statePolicies.xlsx',
                             sheet_name=['Climate Governance and Equity',
                                         'Cross Sector',
                                         'Electricity',
                                         'Buildings and Efficiency',
                                         'Transportation',
                                         'Natural and Working Lands',
                                         'Industry, Materials, and Waste '])

    # List of column names of interest
    policyCols = ['State',
                  'State Abbreviation',
                  'Policy Area',
                  'Policy Category',
                  'Policy Status']
    
    # Extract only the columns of interest
    allPolicydfs = {}
    for sheet in rawPolicyDfs:
        
        allPolicydfs[sheet] = rawPolicyDfs[sheet][policyCols]

    # For each sheet, get a per-state sum of enacted or partially-enacted policies
    policyCountDfs = {}
    for sheet in allPolicydfs:

        # Grab the df
        curDf = allPolicydfs[sheet]

        # Filter out not-enacted policies
        curDf = curDf[curDf['Policy Status'] != 'not-enacted'].reset_index()

        # Group by state and count
        policyCountDf = curDf.groupby('State Abbreviation').count()

        # We only need one column to get the count
        policyCountDf = policyCountDf[['State']]

        # Save it
        policyCountDfs[sheet] = policyCountDf

    # Now, sum up across all sheets

    # First, join on the state abbreviations
    resPolicyDf = None
    lastSheet = None
    for sheet in policyCountDfs:
        curDf = policyCountDfs[sheet]


        # If it's the first one, just reassign
        if resPolicyDf is None:
            resPolicyDf = curDf
        
        # Otherwise, merge it
        else:
            resPolicyDf = pd.merge(resPolicyDf, curDf, how='inner',
                                   left_index=True, right_index=True,
                                   suffixes=(lastSheet, sheet))
        
        # Save the sheet name for unique suffixes
        lastSheet = sheet
            

    finalPolicyCountDf = resPolicyDf.sum(axis=1).to_frame().reset_index()

    # Rename the count column
    finalPolicyCountDf = finalPolicyCountDf.rename(columns={0: 'Num Policies'})

    # We also need to assign GISJOIN IDs to each column
    
    # Use the state shapefile to get GISJOIN IDs
    stateGdf = LoadShapefile(sfDir, 'state')

    stateIds = stateGdf[['GISJOIN', 'STUSPS']]

    finalPolicyCountDf = pd.merge(finalPolicyCountDf, stateIds,
                                  left_on = "State Abbreviation", right_on="STUSPS")
    
    #print(finalPolicyCountDf)

    # Now, load in the per-county income data
    incomeByCountyDf = pd.read_csv(dataDir / 'medianIncomeByCounty2024.csv')

    # Extract only columns of interest
    incomeCols = {
        'A': 'GEOID',
        'B': 'Name',
        'FG': "MedianHouseholdIncome",
        'FH': "IncomeMOE"
    }

    incomeByCountyDf = ExtractCols(incomeByCountyDf, incomeCols)

    # Do the same for the per-state income data
    incomeByStateDf = pd.read_csv(dataDir / 'medianIncomeByState2024.csv')

    # We need the same columns
    incomeByStateDf = ExtractCols(incomeByStateDf, incomeCols)

    # Drop the extra header row included
    incomeByCountyDf = incomeByCountyDf.iloc[1:]
    incomeByStateDf = incomeByStateDf.iloc[1:]

    # Convert from GEOID to FIPS
    incomeByCountyDf['FIPS'] = incomeByCountyDf.apply(ExtractFIPSFromGEOID, args=('GEOID',), axis=1)
    incomeByStateDf['FIPS'] = incomeByStateDf.apply(ExtractFIPSFromGEOID, args=('GEOID',), axis=1)

    # We now need to convert from FIPS to GISJOIN, via the shapefile
    countyGdf = LoadShapefile(sfDir, 'county')
    countyDict = pd.Series(countyGdf['GISJOIN'].values, index=countyGdf['GEOID']).to_dict()
    incomeByCountyDf['GISJOIN'] = incomeByCountyDf.apply(
        CountyFIPSConverter, args=(countyDict, 'FIPS'), axis=1)

    # Drop rows we didn't have a match for
    incomeByCountyDf = incomeByCountyDf[incomeByCountyDf['GISJOIN'] != ""]

    # Do the same thing for state income for easy comparison
    stateDict = pd.Series(stateGdf['GISJOIN'].values, index=stateGdf['GEOID']).to_dict()
    incomeByStateDf['GISJOIN'] = incomeByStateDf.apply(
        StateFIPSConverter, args=(stateDict, 'FIPS'), axis=1)
    

    # Load in the population data by county and by state
    countyPopDf = LoadCountyPopulation()
    statePopDf = LoadStatePopulation()

    # Get the correct GISJOIN IDs to match with the nodes
    countyPopDf = pd.merge(countyPopDf, countyGdf[['GISJOIN', 'GEOID']],
                           left_on='COUNTYFP', right_on='GEOID')
    statePopDf = pd.merge(statePopDf, stateGdf[['GISJOIN', 'GEOID']],
                          left_on='STATEFP', right_on='GEOID')
    
    # Rename to avoid naming conflicts
    countyPopDf = countyPopDf.rename(columns={'GISJOIN': 'COUNTYGISJOIN'})

    # We need to match the counties to their state.  We can
    # use the FIPS code for this
    countyPopDf['STATEFP'] = countyPopDf['COUNTYFP'].str[0:2]
    countyPopDf = pd.merge(countyPopDf, stateGdf[['GISJOIN', 'GEOID']],
                           left_on="STATEFP", right_on='GEOID')
    countyPopDf = countyPopDf.rename(columns={'GISJOIN': 'STATEGISJOIN'})

    # Try and load the graph
    graph = GranularityGraph('incomeVsPolicy', Path('./logs/incomeVsPolicy.log'))
    status = Status.NOTEXISTS
    if loadGraph:
        status = graph.LoadGraph(graphsDir)

    # If needed, create a fresh graph
    if status != Status.SUCCESS:

        # Construct the graph
        msg = "Adding County-State layer..."
        print(msg)
        logger.info(msg)

        graph = AddLevel(graph, countyGdf, stateGdf,
                         n1Type=GEID.COUNTY, n2Type=GEID.STATE)
        
        # Update the county and state nodes with their population
        msg = "Updating County nodes..."
        print(msg)
        logger.info(msg)
        countyPopDf.apply(UpdateNodePop, args=(graph, 'COUNTYGISJOIN', 'POPULATION', EdgeType.POPULATION, GEID.COUNTY), axis=1)

        msg = "Updating State nodes..."
        print(msg)
        logger.info(msg)
        statePopDf.apply(UpdateNodePop, args=(graph, 'GISJOIN', 'POPULATION', EdgeType.POPULATION, GEID.STATE), axis=1)

        # Add the population layer
        # We assume that counties are fully contained within one state each
        msg = "Adding County-State population layer..."
        print(msg)
        logger.info(msg)
        countyPopDf.apply(AddPopEdge, args=(graph, 'COUNTYGISJOIN', 'STATEGISJOIN', 'POPULATION', GEID.COUNTY, GEID.STATE), axis=1)


        # Save the graph
        msg = "Saving the graph..."
        print(msg)
        logger.info(msg)
        graph.SaveGraph(graphsDir)
        msg = "Saved the graph."
        print(msg)
        logger.info(msg)

        # Reload it to make sure data types are correct
        graph.LoadGraph(graphsDir)
        msg = "Graph re-loaded successfully."
        print(msg)
        logger.info(msg)

    else:
        # Log that we loaded the graph
        msg = "Graph loaded successfully."
        print(msg)
        logger.info(msg)

    # Get a gator object
    gator = Gator(graph, Path('./logs/incomeVsPolicyGator.log'))

    # We need to account for poor data quality (mainly missing values)
    # The Census uses "N" to denote this
    incomeByCountyDf = incomeByCountyDf[incomeByCountyDf['MedianHouseholdIncome'] != "N"]
    incomeByCountyDf['MedianHouseholdIncome'] = \
        incomeByCountyDf['MedianHouseholdIncome'].astype(np.float64)

    # Use the gator to get the median income from county to state
    msg = "Areal overlap equalization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    arealResDf = gator.SpatialEqualize(incomeByCountyDf, incomeByStateDf,
                                       GEID.COUNTY, GEID.STATE, 'GISJOIN', 'GISJOIN',
                                       'MedianHouseholdIncome', None, None,
                                       AggMethod.MEDIAN, edgeType=EdgeType.AREA,
                                       ignoreMissing=True, ignoreIncomplete=True)
    arealRuntime = time.time() - st

    # Do the same thing but with kriging
    msg = "Kriging equalization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    krigingResDf = gator.SpatialEqualize(incomeByCountyDf, incomeByStateDf,
                                         GEID.COUNTY, GEID.STATE, 'GISJOIN', 'GISJOIN',
                                         'MedianHouseholdIncome', None, None,
                                         AggMethod.KRIGING, edgeType=EdgeType.AREA,
                                         ignoreMissing=True, ignoreIncomplete=True,
                                         distFunction=distFunc, model=VariogramModel.EXPONENTIAL,
                                         binSize=50.)
    krigingRuntime = time.time() - st

    # Now, do it via population overlap
    msg = "Population overlap equlization starting..."
    print(msg)
    logger.info(msg)
    st = time.time()
    popResDf = gator.SpatialEqualize(incomeByCountyDf, incomeByStateDf,
                                       GEID.COUNTY, GEID.STATE, 'GISJOIN', 'GISJOIN',
                                       'MedianHouseholdIncome', None, None,
                                       AggMethod.MEDIAN, edgeType=EdgeType.POPULATION,
                                       ignoreMissing=True, ignoreIncomplete=True)
    popRuntime = time.time() - st

    # Rename for clarity
    popResDf = popResDf.rename(columns={"MedianHouseholdIncome": "MedianHouseholdIncome_Pop"})
    
    # Rename the ground truth column for clarity
    incomeByStateDf = incomeByStateDf.rename(
        columns={'MedianHouseholdIncome': 'MedianHouseholdIncome_GT'})
    
    # Fix the typing too
    incomeByStateDf['MedianHouseholdIncome_GT'] = incomeByStateDf['MedianHouseholdIncome_GT'].astype(float)

    # Generate a combined dataset that averages all estimates together
    print(arealResDf)
    print(krigingResDf)
    print(popResDf)
    avgResDf = pd.merge(arealResDf, krigingResDf, left_index=True, right_on='GISJOIN')
    print(avgResDf)
    avgResDf = pd.merge(avgResDf, popResDf, left_on='GISJOIN', right_index=True)

    avgResDf['AvgEstIncome'] = (avgResDf['MedianHouseholdIncome'] +
                                avgResDf['MedianHouseholdIncome_est'] +
                                avgResDf['MedianHouseholdIncome_Pop']) / 3.

    # Join with the "ground truth" for a comparison
    arealResDf = pd.merge(arealResDf, incomeByStateDf, left_index=True, right_on='GISJOIN')
    krigingResDf = pd.merge(krigingResDf, incomeByStateDf, on='GISJOIN')
    popResDf = pd.merge(popResDf, incomeByStateDf, left_index=True, right_on='GISJOIN')
    avgResDf = pd.merge(avgResDf, incomeByStateDf, on='GISJOIN')

    # Calculate error
    errorCol = 'RelError'
    arealResDf[errorCol+'_a'] = np.abs(arealResDf['MedianHouseholdIncome'] - arealResDf['MedianHouseholdIncome_GT']) / arealResDf['MedianHouseholdIncome_GT']
    krigingResDf[errorCol+'_k'] = np.abs(krigingResDf['MedianHouseholdIncome_est'] - krigingResDf['MedianHouseholdIncome_GT']) / krigingResDf['MedianHouseholdIncome_GT']
    popResDf[errorCol+'_p'] = np.abs(popResDf['MedianHouseholdIncome_Pop'] - popResDf['MedianHouseholdIncome_GT']) / popResDf['MedianHouseholdIncome_GT']
    avgResDf[errorCol+'_avg'] = np.abs(avgResDf['AvgEstIncome'] - avgResDf['MedianHouseholdIncome_GT']) / avgResDf['MedianHouseholdIncome_GT']

    # Calculate variance of error
    arealVar = arealResDf[errorCol+'_a'].var()
    krigingVar = krigingResDf[errorCol+'_k'].var()
    popVar = popResDf[errorCol+'_p'].var()
    avgVar = avgResDf[errorCol+'_avg'].var()

    # Join the results to compare errors directly
    errorDf = pd.merge(arealResDf[['GISJOIN', errorCol+'_a']],
                       krigingResDf[['GISJOIN', errorCol+'_k']],
                       on='GISJOIN')
    errorDf = pd.merge(errorDf,
                       popResDf[['GISJOIN', errorCol+'_p']],
                       on='GISJOIN')
    errorDf = pd.merge(errorDf,
                       avgResDf[['GISJOIN', errorCol+'_avg']],
                       on='GISJOIN')
    
    # Get pairwise average error differences
    errorDf['Error Difference: A-K'] = errorDf[errorCol+'_a'] - errorDf[errorCol+'_k']
    avgErrorDiffAK = errorDf['Error Difference: A-K'].mean()
    medErrorDiffAK = errorDf['Error Difference: A-K'].median()
        
    errorDf['Error Difference: A-P'] = errorDf[errorCol+'_a'] - errorDf[errorCol+'_p']
    avgErrorDiffAP = errorDf['Error Difference: A-P'].mean()
    medErrorDiffAP = errorDf['Error Difference: A-P'].median()

    errorDf['Error Difference: P-K'] = errorDf[errorCol+'_p'] - errorDf[errorCol+'_k']
    avgErrorDiffPK = errorDf['Error Difference: P-K'].mean()
    medErrorDiffPK = errorDf['Error Difference: P-K'].median()

    # Redo it for the avg (yes, this could have been a loop and a function)
    errorDf['Error Difference: Avg-A'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_a']
    avgErrorDiffAvgA = errorDf['Error Difference: Avg-A'].mean()
    medErrorDiffAvgA = errorDf['Error Difference: Avg-A'].median()

    errorDf['Error Difference: Avg-K'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_k']
    avgErrorDiffAvgK = errorDf['Error Difference: Avg-K'].mean()
    medErrorDiffAvgK = errorDf['Error Difference: Avg-K'].median()

    errorDf['Error Difference: Avg-P'] = errorDf[errorCol+'_avg'] - errorDf[errorCol+'_p']
    avgErrorDiffAvgP = errorDf['Error Difference: Avg-P'].mean()
    medErrorDiffAvgP = errorDf['Error Difference: Avg-P'].median()

    
    # Calculate singular error averages
    avgErrorAreal = errorDf[errorCol + '_a'].mean()
    medErrorAreal = errorDf[errorCol + '_a'].median()

    avgErrorKriging = errorDf[errorCol + '_k'].mean()
    medErrorKriging = errorDf[errorCol + '_k'].median()

    avgErrorPop = errorDf[errorCol + '_p'].mean()
    medErrorPop = errorDf[errorCol + '_p'].median()

    avgErrorAvg = errorDf[errorCol + '_avg'].mean()
    medErrorAvg = errorDf[errorCol + '_avg'].median()

    # Print out average and median error difference for each pair of methods
    print(f"\nAreal - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffAK*100.}")
    print(f"Median error difference (in %): {medErrorDiffAK*100.}")
    print(f"\nAreal - Population")
    print(f"Average error difference (in %): {avgErrorDiffAP*100.}")
    print(f"Median error difference (in %): {medErrorDiffAP*100.}")
    print(f"\nPopulation - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffPK*100.}")
    print(f"Median error difference (in %): {medErrorDiffPK*100.}")

    print(f"\n\nAveraged - Areal")
    print(f"Average error difference (in %): {avgErrorDiffAvgA*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgA*100.}")
    print(f"\nAveraged - Kriging")
    print(f"Average error difference (in %): {avgErrorDiffAvgK*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgK*100.}")
    print(f"\nAveraged - Population")
    print(f"Average error difference (in %): {avgErrorDiffAvgP*100.}")
    print(f"Median error difference (in %): {medErrorDiffAvgP*100.}")

    # Print average errors by method
    print(f"\n\n\nAreal Mean Error (in %): {avgErrorAreal*100.}")
    print(f"Areal Median Error (in %): {medErrorAreal*100.}")
    print(f"\nKriging Mean Error (in %): {avgErrorKriging*100.}")
    print(f"Kriging Median Error (in %): {medErrorKriging*100.}")
    print(f"\nPopulation Mean Error (in %): {avgErrorPop*100.}")
    print(f"Population Median Error (in %): {medErrorPop*100.}")
    print(f"\nAveraged Estimate Mean Error (in %): {avgErrorAvg*100.}")
    print(f"Averaged Estimate Median Error (in %): {medErrorAvg*100.}")

    # Print error variance by method
    print(f"\n\n\nAreal Error Variance: {arealVar}")
    print(f"Kriging Error Variance: {krigingVar}")
    print(f"Population Error Variance: {popVar}")
    print(f"Averaged Estimate Error Variance: {avgVar}")

    # Print runtime by method
    print(f"\n\n\nAreal runtime: {arealRuntime}")
    print(f"Kriging runtime: {krigingRuntime}")
    print(f"Population runtime: {popRuntime}")

    # Now, combine it with the state policy data for our results
    arealFinalDf = pd.merge(finalPolicyCountDf, arealResDf, on='GISJOIN')
    krigingFinalDf = pd.merge(finalPolicyCountDf, krigingResDf, on='GISJOIN')
    popFinalDf = pd.merge(finalPolicyCountDf, popResDf, on='GISJOIN')
    avgFinalDf = pd.merge(finalPolicyCountDf, avgResDf, on='GISJOIN')
    gtFinalDf = pd.merge(finalPolicyCountDf, incomeByStateDf, on='GISJOIN')

    # Sort for better plotting
    #arealFinalDf.sort_values('MedianHouseholdIncome', inplace=True)
    #krigingFinalDf.sort_values('MedianHouseholdIncome_est', inplace=True)
    #gtFinalDf.sort_values('MedianHouseholdIncome_GT', inplace=True)

    arealFinalDf.sort_values('Num Policies', inplace=True)
    krigingFinalDf.sort_values('Num Policies', inplace=True)
    popFinalDf.sort_values('Num Policies', inplace=True)
    avgFinalDf.sort_values('Num Policies', inplace=True)
    gtFinalDf.sort_values('Num Policies', inplace=True)

    fig, ax = plt.subplots(figsize=FIG_SIZE)

    arealFinalDf.plot(y='MedianHouseholdIncome', x='Num Policies', ax=ax, color='red', label='Areal Overlap', lw=2)
    arealFinalDf.plot(y='MedianHouseholdIncome', x='Num Policies', ax=ax, kind='scatter', color='red', s=50)

    krigingFinalDf.plot(y='MedianHouseholdIncome_est', x='Num Policies', ax=ax, color='blue', label='Kriging', lw=2)
    krigingFinalDf.plot(y='MedianHouseholdIncome_est', x='Num Policies', ax=ax, kind='scatter', color='blue', s=50)

    popFinalDf.plot(y='MedianHouseholdIncome_Pop', x='Num Policies', ax=ax, kind='line', color='black', label='Pop. Overlap', lw=2)
    popFinalDf.plot(y='MedianHouseholdIncome_Pop', x='Num Policies', ax=ax, kind='scatter', color='black', s=50)

    avgFinalDf.plot(y='AvgEstIncome', x='Num Policies', ax=ax, kind='line', color='orange', label='Averaged Est.', lw=2)
    avgFinalDf.plot(y='AvgEstIncome', x='Num Policies', ax=ax, kind='scatter', color='orange', s=50)

    gtFinalDf.plot(y='MedianHouseholdIncome_GT', x='Num Policies', ax=ax, kind='line', color='green', label='Ground Truth', lw=2)
    gtFinalDf.plot(y='MedianHouseholdIncome_GT', x='Num Policies', ax=ax, kind='scatter', color='green', s=50)



    # Fix the legend size and location
    ax.legend(loc='upper left', fontsize=FIG_LABEL_FONT_SIZE)

    # Set labels and font sizes

    plt.xlabel('Number of Green Policies', fontsize=FIG_LABEL_FONT_SIZE)
    plt.ylabel('Median Household Income (USD)', fontsize=FIG_LABEL_FONT_SIZE)
    plt.title('Number of Green Policies vs. Household Income', fontsize=FIG_TITLE_FONT_SIZE)

    # Fix font sizes for axis ticks
    ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
    ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

    ax.legend(fontsize=FIG_MINOR_AXIS_TICK_SIZE)

    # Save the figure out
    figDir = dataDir / Path("figures/")
    if not figDir.exists():
        figDir.mkdir()

    plt.savefig(figDir / Path("policies-vs-income.png"))

    # We also want to get a boxplot for the errors
    
    # First, rename the columns for a better plot
    colMapper = {
            errorCol+'_a': 'Areal',
            errorCol+'_k': 'Kriging',
            errorCol+'_p': 'Population',
            errorCol+'_avg': 'Averaged'
    }
    errorDf = errorDf.rename(columns=colMapper)

    # Multiply each error by 100 for the percentage
    for c in list(colMapper.values()):
        errorDf[c] = errorDf[c]*100.

    # Generate a new figure
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    # Plot all 4 error columns for this state
    props = dict(linewidth=3)
    dotProps = dict(marker='o', markersize=12, markeredgewidth=3)
    errorDf.boxplot(column=['Areal', 'Kriging', 'Population', 'Averaged'],
                    ax=ax, grid=False, boxprops=props, whiskerprops=props,
                    capprops=props, medianprops=props, flierprops=dotProps)
    
    # Fix plot labels and sizes
    plt.xlabel('Change of Support Method', fontsize=FIG_LABEL_FONT_SIZE)
    plt.ylabel('Relative Error (%)', fontsize=FIG_LABEL_FONT_SIZE)
    plt.title(f'Relative Error of Estimation of Median Income', fontsize=FIG_TITLE_FONT_SIZE)

    ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
    ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)

    #ax.legend(fontsize=FIG_MINOR_AXIS_TICK_SIZE)

    plt.savefig(figDir / Path("income-est-boxplot.png"))


    plt.show()



def RainVsChargingUsage(dataDir: Path, loadGraph: bool = True,
                        graphsDir: Path = Path("./graphs")):
    
    ''' Outline
    
    Goal: Check for a correlation between precipitation and charger usage (a negative
    correlation is expected)

    Want: Daily precipitation for the city of Palo Alto, daily charger use (kWh) for Palo Alto
    Have: Hourly precipitation for Palo Alto, charging sessions for Palo Alto

    Need: Aggregate hourly to daily

    NOTE: We have the daily precipitation already, so we can use that as ground truth for
    accuracy comparison.

    NOTE: For this comparison, make sure to note that the hourly and daily weather data
    ARE ALL FROM THE SAME SOURCE.  Who knows how they aggregate their data.

    NOTE: The weather data is from https://open-meteo.com/

    
    '''

    # Generate a logger for this test case
    logger = logging.getLogger('RainVsChargingUsage')
    logging.basicConfig(filename=f"./logs/rainVsChargingUsage.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Column names
    startTsCol = 'StartDate'
    startTzCol = 'StartTimeZone'
    endTsCol = 'EndDate'
    endTzCol = 'EndTimeZone'
    intervalCol = "TIME_INTERVAL"

    # Check for a cached file first
    cachedChargingFile = Path(dataDir / Path('chargingStations2018.csv'))
    if cachedChargingFile.exists():
        chargingDf = pd.read_csv(cachedChargingFile)

        # We still have to convert to timestamps and intervals
        chargingDf[startTsCol] = chargingDf.apply(ConvertToDt, args=(startTsCol, startTzCol), axis=1)
        chargingDf[endTsCol] = chargingDf.apply(ConvertToDt, args=(endTsCol, endTzCol), axis=1)

        # Invalid rows should already have been removed

        # Form the interval objects too
        chargingDf[intervalCol] = chargingDf.apply(FormInterval, args=(startTsCol, endTsCol), axis=1)

    else:

        msg = "No cached charging data found..."
        logger.info(msg)
        print(msg)

        # Load the original charging data
        chargingDf = pd.read_csv(Path("./evaluation/temporal/EVChargingStationUsage.csv"),
                                low_memory=False)

        # Rename the columns to remove all special characters
        # so itertuples works
        fixedCols = {c: c.replace(' ', '').replace('(','').replace(')','').replace(':','') 
                    for c in chargingDf.columns}
        
        chargingDf = chargingDf.rename(columns=fixedCols)
        
        # First, convert to actual timestamps
        chargingDf[startTsCol] = chargingDf.apply(ConvertToDt, args=(startTsCol, startTzCol), axis=1)
        chargingDf[endTsCol] = chargingDf.apply(ConvertToDt, args=(endTsCol, endTzCol), axis=1)

        # Remove invalid rows
        chargingDf = chargingDf[(chargingDf[startTsCol] != 0) & (chargingDf[endTsCol] != 0)]

        # We only have weather for the year of 2018, so just select that year's data
        chargingDf = chargingDf[chargingDf[startTsCol].dt.year == 2018]

        chargingDf.to_csv(cachedChargingFile, index=False)

        msg = "Charging data cached, please rerun for analysis."
        logger.info(msg)
        print(msg)

        return


    # Load in the weather data
    allWeather = pd.read_excel(dataDir / 'palo-alto-2018-weather.xlsx',
                               sheet_name=['Hourly', 'Daily'])
    
    # Drop the first three rows for each sheet
    for dfk in allWeather:
        allWeather[dfk] = allWeather[dfk].iloc[3:].reset_index(drop=True)

    # Separate hourly and daily aggregations
    hourlyWeatherDf = allWeather['Hourly']
    dailyWeatherDf = allWeather['Daily']

    # Fix the column names
    hourlyCols = {
        'A': 'Timestamp',
        'B': 'Temperature',
        'C': 'Precipitation',
        'D': 'Rain',
        'E': 'Snowfall_cm'
    }

    hourlyWeatherDf = ExtractCols(hourlyWeatherDf, hourlyCols)

    dailyCols = {
        'A': 'Timestamp',
        'B': 'Daily Precipitation',
        'C': 'Precipitation Hours'
    }

    dailyWeatherDf = ExtractCols(dailyWeatherDf, dailyCols)

    # For the weather aggregation, we actually need an interval column
    hourlyWeatherDf[endTsCol] = hourlyWeatherDf['Timestamp'] + pd.Timedelta(minutes=59, seconds=59)

    # Make sure they are both timestamp objects (not datetime) -
    # Yes, the function is named poorly for this
    hourlyWeatherDf['Timestamp'] = pd.to_datetime(hourlyWeatherDf['Timestamp'])
    hourlyWeatherDf[endTsCol] = pd.to_datetime(hourlyWeatherDf[endTsCol])

    # Same goes for the daily weather's timestamp column
    dailyWeatherDf['Timestamp'] = pd.to_datetime(dailyWeatherDf['Timestamp'])

    hourlyWeatherDf[intervalCol] = hourlyWeatherDf.apply(FormInterval, args=('Timestamp', endTsCol), axis=1)

    # We are only looking at temporal aggregation, so no need for the shapefiles

    # Get a gator object
    gator = Gator(None, Path('./logs/rainVsChargingUsage.log'))

    # Aggregate weather from hour to day
    hourlyDataCol = 'Precipitation'

    msg = "Beginning weather aggregation from hourly to daily..."
    hourlyResDf = gator.TemporalEqualize(hourlyWeatherDf, TID.DAY, intervalCol,
                                         hourlyDataCol, AggMethod.SUM)
    
    # Extract the date for joining
    dailyWeatherDf['Date'] = pd.to_datetime(dailyWeatherDf['Timestamp'].dt.date)

    # Do the join
    weatherResDf = pd.merge(hourlyResDf, dailyWeatherDf, left_index=True, right_on='Date')

    # Get an error comparison
    # Can't use percentage because precipitation can be 0
    weatherResDf['Actual Error'] = np.abs(weatherResDf['Precipitation'] - weatherResDf['Daily Precipitation'])

    print(f"Average actual error for precipitation: {weatherResDf['Actual Error'].mean()}")

    print(chargingDf)

    # Now, aggregate charging usage to the day
    chargingResDf = gator.TemporalEqualize(chargingDf, TID.DAY, intervalCol,
                                           'EnergykWh', AggMethod.SUM)
    
    print(chargingResDf)


    
  

if __name__ == "__main__":
    
    #SpatialEval(Path('./evaluation/spatial'), loadGraph=True)

    #TemporalEval(Path('./evaluation/temporal'))

    #STEval(Path('./data/ntdas'), loadGraph=True, loadResults=True)
    
    errorDfs = {}
    for stateAc in ['TN', 'CT', 'OR']:#['OR']:#['CT']:#, 'OR', 'TN']:
        break
        errorDfs[stateAc] = EmissionsPC(Path('./evaluation/emissions'), Path('./data/tiger'), stateAc=stateAc,
                                        loadGraph=True)
    

    # Plot a boxplot of all the errors
    #fig, ax = plt.subplots(figsize=FIG_SIZE)
    finalDf = None
    for stateAc in errorDfs:

        # New figure for each state since the scales are mismatched
        fig, ax = plt.subplots(figsize=FIG_SIZE)

        curDf, errorCol = errorDfs[stateAc]

        # All columns except the first should be floats
        for c in curDf.columns[1:]:
            curDf[c] = curDf[c].astype(float)

        # Add the state in for groupby later
        curDf['STATE'] = stateAc

        # Rename the columns for a better plot
        curDf = curDf.rename(columns={
            errorCol+'_a': 'Areal',
            errorCol+'_k': 'Kriging',
            errorCol+'_p': 'Population',
            errorCol+'_avg': 'Averaged'
        })

        # Plot all 4 error columns for this state
        curDf.boxplot(column=['Areal', 'Kriging', 'Population', 'Averaged'],
                      ax=ax, grid=False)
        
        # Fix plot labels and sizes
        plt.xlabel('Method', fontsize=FIG_LABEL_FONT_SIZE)
        plt.ylabel('Relative Error', fontsize=FIG_LABEL_FONT_SIZE)
        plt.title(f'Relative Error for{ACRO_TO_STATE[stateAc]}, by Method', fontsize=FIG_TITLE_FONT_SIZE)

        ax.tick_params(axis='both', which='major', labelsize=FIG_MAJOR_AXIS_TICK_SIZE)
        ax.tick_params(axis='both', which='minor', labelsize=FIG_MINOR_AXIS_TICK_SIZE)
        
        ax.legend(fontsize=FIG_MINOR_AXIS_TICK_SIZE)


        # Concatenate with the other results
        if finalDf is None:
            finalDf = curDf
        else:
            finalDf = pd.concat([finalDf, curDf])
        

        

    # Plot all boxplots together
    #finalDf.boxplot(column=[errorCol+'_a', errorCol+'_k', errorCol+'_p', errorCol+'_avg'],
    #                ax=ax, grid=False, by='STATE')


    
    #plt.show()

    IncomeVsPolicy(Path('./evaluation/incomeVsPolicy'), Path('./data/tiger'), loadGraph=True)

    #RainVsChargingUsage(Path('./evaluation/weather'))
