
from pathlib import Path

import numpy as np

from gator import *

# Import functions for graph creation from shapefiles
from connecticutGraph import *


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
    'IN': '18',
    'IA': '19',
    'KS': '20',
    'LA': '22',
    'ME': '23',
    'MA': '25',
    'MI': '26',
    'MN': '27',
    'MS': '28',
    'MT': '30',
    'NE': '31',
    'NV': '32',
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

def SetupGraph():
    pass



def SpatialEval(dirPath: Path, loadGraph: bool = True):

    # Generate a logger for this evaluation
    logger = logging.getLogger('SpatialEval')
    logging.basicConfig(filename="./logs/spatialEval.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")


    ''' Outline
    Want: EV registration vs. utility rates
    Have: EV registration by city, rates by ZIP
    Need: EV Registration by ZIP

    Procedure: Scale by areal overlap, city -> ZIP
    '''

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
    regsDf = regsDf[regsDf['Primary Customer State'] == 'CT']
    iouRatesDf = iouRatesDf[iouRatesDf['state'] == 'CT']

    # We are only doing American locations, so drop BC and ON from the list
    regsDf = regsDf[(regsDf['Primary Customer State'] != 'BC') & 
                  (regsDf['Primary Customer State'] != 'ON')]

    # We need information for ZIPS and cities

    ### Cities ###
    cityGdf = LoadShapefile(sfDir, 'city')

    # Make the city names lower case for consistency
    cityGdf['NAME'] = cityGdf.apply(lambda x: x['NAME'].lower(), axis=1)
    
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
        msg = "Adding City-ZCTA layers..."
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




if __name__ == "__main__":
    SpatialEval(Path('./evaluation/spatial'))