
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


STATE_AC_TO_FIPS = {

    'AL': '01',
    'AK': '02',
    'AZ': '04',
    'CA': '06',
    'CO': '08',
    'CT': '09',
    'DE': '10',
    'FL': '12',
    'GA': '13',
    'HI': '15',
    'ID': '16',
    'IL': '17',
    'IN': '18',
    'IA': '19',
    'KS': '20',
    'LA': '22',
    'ME': '23',
    'MD': '24',
    'MA': '25',
    'MI': '26',
    'MN': '27',
    'MS': '28',
    'MT': '30',
    'NE': '31',
    'NV': '32',
    'NH': '33',
    'NJ': '34',
    'NM': '35',
    'NY': '36',
    'NC': '37',
    'ND': '38',
    'OK': '40',
    'OR': '41',
    'RI': '44',
    'SC': '45',
    'SD': '46',
    'TN': '47',
    'TX': '48',
    'UT': '49',
    'VT': '50',
    'VA': '51',
    'WA': '53',
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
    regsDf = regsDf[regsDf['Primary Customer State'] == 'CT'].head(n=1000)
    iouRatesDf = iouRatesDf[iouRatesDf['state'] == 'CT'].head(n=1000)

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
    joinedGdf.plot(x='Number of EVs', y='res_rate', kind='scatter')
    joinedGdf.plot(x='Number of EVs', y='comm_rate', kind='scatter')
    plt.show()


def ConvertToDt(row, tsCol: str, tzCol: str):

    # Grab the timezone
    tz = row[tzCol]

    # Get the corresponding name and DST flag
    tzName, dst = US_TIMEZONE_DICT[tz]

    # Use to_datetime and tz_localize
    try:
        return pd.to_datetime(row[tsCol]).tz_localize(tzName, ambiguous=dst, nonexistent='shift_forward').tz_convert('UTC')
    except:
        return 0
    #return pd.to_datetime(row[tsCol]).tz_localize('UTC').tz_convert(tz)

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
    dataDf = pd.read_csv(dirPath / 'EVChargingStationUsage.csv')

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

    dataDf[intervalCol] = dataDf.apply(FormInterval, args=(startTsCol, endTsCol), axis=1)

    # Get a gator object
    gator = Gator(None, Path('./logs/temporalEvalGator.log'))

    # Aggregate to the hour level
    dataCol = 'EnergykWh'
    resDf = gator.TemporalEqualize(dataDf, TID.DAY, intervalCol,
                                   dataCol, AggMethod.SUM)

    resDf.plot(y=dataCol)
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
    dateCutoff = pd.Timestamp(year=2020, month=10, day=7, hour=0, minute=0, second=0)
    vehicleDf = vehicleDf[vehicleDf[ntdas.TIMESTAMP_COL] < dateCutoff]

    # We only want Denver ZIP codes for the roads
    roadDf = roadDf[roadDf['zip'].isin(ntdas.DENVER_ZIPS)]

    # Take out rows with a travel time of 0 minutes
    vehicleDf = vehicleDf[vehicleDf[ntdas.TRAVEL_TIME_COL] > 0]

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
        st = time.time()
        resDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                             TID.HOUR, GEID.ZCTA, GEID.SD,
                                             'GISJOIN', 'GISJOIN', ntdas.INTERVAL_COL,
                                             None, ntdas.SPEED_RATIO_COL, None, None,
                                             AggMethod.MEAN, AggMethod.MEAN, EdgeType.AREA,
                                             True, True)
        
        print(f"Runtime: {time.time() - st}")

        # Fix the ordering of the multiindex
        resDf = resDf.swaplevel().sort_index(level=0, inplace=False)

        # Save it for speed ups
        resDf.to_csv(resFile)


    print(resDf)

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
    #print(arealResDf)
    #print(krigingResDf)

    # Get the groundtruth values
    countyGt = countyEmissions[['GISJOIN', 'EmissionsPerVM']]
    countyGt = countyGt.rename(columns={'EmissionsPerVM': 'EmissionsPerVM_GT'})

    #print(countyEmissions)

    # Add the 'true' value via joining
    arealResDf = pd.merge(arealResDf, countyGt, left_index=True, right_on='GISJOIN')
    krigingResDf = pd.merge(krigingResDf, countyGt, on='GISJOIN')

    # Calculate error
    errorCol = 'RelError'
    arealResDf[errorCol+'_a'] = np.abs(arealResDf['EmissionsPerVM'] - arealResDf['EmissionsPerVM_GT']) / arealResDf['EmissionsPerVM_GT']
    krigingResDf[errorCol+'_k'] = np.abs(krigingResDf['EmissionsPerVM_est'] - krigingResDf['EmissionsPerVM_GT']) / krigingResDf['EmissionsPerVM_GT']

    # Calculate variance of error
    arealVar = arealResDf[errorCol+'_a'].var()
    krigingVar = krigingResDf[errorCol+'_k'].var()

    # Join the two results to compare errors directly
    errorDf = pd.merge(arealResDf[['GISJOIN', errorCol + '_a']], krigingResDf[['GISJOIN', errorCol +'_k']], on='GISJOIN')

    # Get an average error difference
    errorDf['Error Difference'] = errorDf[errorCol + '_a'] - errorDf[errorCol + '_k']
    avgErrorDiff = errorDf['Error Difference'].mean()
    medErrorDiff = errorDf['Error Difference'].median()


    print(arealResDf)
    print(krigingResDf)



    #pd.set_option('display.max_rows', None)
    print(errorDf)
    print(f"Average error difference (in %): {avgErrorDiff*100}")
    print(f"Median error difference (in %): {medErrorDiff*100}")

    print(f"Areal Error Variance: {arealVar}")
    print(f"Kriging Error Variance: {krigingVar}")

    print(f"Areal runtime: {arealRuntime}")
    print(f"Kriging runtime: {krigingRuntime}")

    #print(countyEmissions[countyEmissions['GISJOIN'] == "G0100790"])

    # Now, we want the EVs at the county level
    regsDf = pd.read_csv(Path("./evaluation/spatial/ev_registration.csv"))

    #regsDf = regsDf.drop_duplicates('Primary Customer State')
    #print(regsDf)
    #quit()

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

        # If we didn't load the graph, we also need to add
        print(zctaGdf)
        print(zctaGdf[zctaGdf['GISJOIN'] == 'G85014'])
        # a ZCTA-county layer
        if loadGraphStatus != Status.SUCCESS:
            msg = "Adding ZCTA-county layer..."
            print(msg)
            logger.info(msg)
            graph = AddLevel(graph, zctaGdf, countyGdf,
                            n1Type=GEID.ZCTA, n2Type=GEID.COUNTY)
            
            # Re-save the graph
            graph.SaveGraph(graphsDir)
        
        # Make sure the key type is updated
        keyType = GEID.ZCTA


    # We already have city-county information in the graph,
    # so go ahead and do the aggregation

    # Make sure the data column is a float for mathmatical operations
    regsDf[dataCol] = regsDf[dataCol].astype(np.float64)

    if keyType == GEID.COUNTY:

        # We don't need to use the gator, we can just do a groupby
        regsResDf = regsDf.groupby('GISJOIN').sum()

        # We only need one column
        regsResDf = regsResDf[[dataCol]]

    else:

        regsResDf =  gator.SpatialEqualize(regsDf, countyEmissions, keyType, GEID.COUNTY,
                                        'GISJOIN', 'GISJOIN', dataCol, None, None,
                                        AggMethod.SUM, EdgeType.AREA, ignoreMissing=True,
                                        ignoreIncomplete=True)

    # For clarity, rename the 'Vehicle Year' column
    regsResDf = regsResDf.rename(columns={dataCol: 'EV_Count'})

    # Now, join the results
    regsArealDf = pd.merge(arealResDf, regsResDf, left_on='GISJOIN', right_index=True)
    regsKrigingDf = pd.merge(krigingResDf, regsResDf, left_on='GISJOIN', right_index=True)

    # Sort for better plotting
    regsArealDf = regsArealDf.sort_values('EV_Count')
    regsKrigingDf = regsKrigingDf.sort_values('EV_Count')

    # Plot the results
    fig, ax = plt.subplots()
    regsArealDf.plot(x='EV_Count', y='EmissionsPerVM', kind='line', ax=ax, color='red')
    regsKrigingDf.plot(x='EV_Count', y='EmissionsPerVM_est', kind='line', ax=ax, color='blue')
    regsArealDf.plot(x='EV_Count', y='EmissionsPerVM_GT', kind='line', ax=ax, color='green')

    # Add labels, titles, etc.
    plt.title(f'EVs Vs. Emissions per Vehicle Mile Traveled, {stateAc}')


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
        
        # Save the graph
        msg = "Saving the graph..."
        print(msg)
        logger.info(msg)
        graph.SaveGraph(graphsDir)

        # Reload it to make sure data types are correct
        graph.LoadGraph(graphsDir)

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
    
    # Rename the ground truth column for clarity
    incomeByStateDf = incomeByStateDf.rename(
        columns={'MedianHouseholdIncome': 'MedianHouseholdIncome_GT'})
    
    # Fix the typing too
    incomeByStateDf['MedianHouseholdIncome_GT'] = incomeByStateDf['MedianHouseholdIncome_GT'].astype(float)

    # Join with the "ground truth" for a comparison
    arealResDf = pd.merge(arealResDf, incomeByStateDf, left_index=True, right_on='GISJOIN')
    krigingResDf = pd.merge(krigingResDf, incomeByStateDf, on='GISJOIN')

    # Calculate error
    errorCol = 'RelError'
    arealResDf[errorCol+'_a'] = np.abs(arealResDf['MedianHouseholdIncome'] - arealResDf['MedianHouseholdIncome_GT']) / arealResDf['MedianHouseholdIncome_GT']
    krigingResDf[errorCol+'_k'] = np.abs(krigingResDf['MedianHouseholdIncome_est'] - krigingResDf['MedianHouseholdIncome_GT']) / krigingResDf['MedianHouseholdIncome_GT']

    # Calculate variance of error
    arealVar = arealResDf[errorCol+'_a'].var()
    krigingVar = krigingResDf[errorCol+'_k'].var()

    # Join the two results to compare errors directly
    errorDf = pd.merge(arealResDf[['GISJOIN', errorCol+'_a']],
                       krigingResDf[['GISJOIN', errorCol+'_k']],
                       on='GISJOIN')
    
    # Get an average error difference
    errorDf['Error Difference'] = errorDf[errorCol+'_a'] - errorDf[errorCol+'_k']
    avgErrorDiff = errorDf['Error Difference'].mean()
    medErrorDiff = errorDf['Error Difference'].median()

    print(errorDf)
    print(f"Average error difference (in %): {avgErrorDiff*100}")
    print(f"Median error difference (in %): {medErrorDiff*100}")

    print(f"Areal Error Variance: {arealVar}")
    print(f"Kriging Error Variance: {krigingVar}")

    print(f"Areal runtime: {arealRuntime}")
    print(f"Kriging runtime: {krigingRuntime}")

    # Now, combine it with the state policy data for our results
    arealFinalDf = pd.merge(finalPolicyCountDf, arealResDf, on='GISJOIN')
    krigingFinalDf = pd.merge(finalPolicyCountDf, krigingResDf, on='GISJOIN')
    gtFinalDf = pd.merge(finalPolicyCountDf, incomeByStateDf, on='GISJOIN')

    # Sort for better plotting
    #arealFinalDf.sort_values('MedianHouseholdIncome', inplace=True)
    #krigingFinalDf.sort_values('MedianHouseholdIncome_est', inplace=True)
    #gtFinalDf.sort_values('MedianHouseholdIncome_GT', inplace=True)

    arealFinalDf.sort_values('Num Policies', inplace=True)
    krigingFinalDf.sort_values('Num Policies', inplace=True)
    gtFinalDf.sort_values('Num Policies', inplace=True)

    fig, ax = plt.subplots()

    arealFinalDf.plot(y='MedianHouseholdIncome', x='Num Policies', ax=ax, color='red', label='Areal Overlap')
    arealFinalDf.plot(y='MedianHouseholdIncome', x='Num Policies', ax=ax, kind='scatter', color='red', s=50)

    krigingFinalDf.plot(y='MedianHouseholdIncome_est', x='Num Policies', ax=ax, color='blue', label='Kriging')
    krigingFinalDf.plot(y='MedianHouseholdIncome_est', x='Num Policies', ax=ax, kind='scatter', color='blue', s=50)

    gtFinalDf.plot(y='MedianHouseholdIncome_GT', x='Num Policies', ax=ax, kind='line', color='green', label='Ground Truth')
    gtFinalDf.plot(y='MedianHouseholdIncome_GT', x='Num Policies', ax=ax, kind='scatter', color='green', s=50)

    # Fix the legend size and location
    ax.legend(loc='upper left', fontsize=18)

    # Set labels and font sizes
    labelFontSize = 24
    titleFontSize = 32

    plt.xlabel('Number of Green Policies', fontsize=labelFontSize)
    plt.ylabel('Median Household Income (USD)', fontsize=labelFontSize)
    plt.title('Number of Green Policies vs. Household Income', fontsize=titleFontSize)

    # Fix font sizes for axis ticks
    ax.tick_params(axis='both', which='major', labelsize=16)
    ax.tick_params(axis='both', which='minor', labelsize=14)


    plt.show()



    
    
  

if __name__ == "__main__":
    
    #SpatialEval(Path('./evaluation/spatial'), loadGraph=True)

    #TemporalEval(Path('./evaluation/temporal'))

    #STEval(Path('./data/ntdas'), loadGraph=True, loadResults=True)

    for stateAc in ['CO']:#, 'OR', 'TN']:
        EmissionsPC(Path('./evaluation/emissions'), Path('./data/tiger'), stateAc=stateAc,
                    loadGraph=True)
    
    plt.show()

    #IncomeVsPolicy(Path('./evaluation/incomeVsPolicy'), Path('./data/tiger'), loadGraph=True)
