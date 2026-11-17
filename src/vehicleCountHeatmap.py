

from allEval import *


def VehicleHeatmap(dataDir: Path = Path("./data/ntdas"), shapefileDir: Path = Path("./data/tiger"),
           loadGraph: bool = True, graphsDir: Path = Path("./graphs"),
           loadResults: bool = True, resDir: Path = Path("./evaluation/st")
           ):
    

    # Redo the spatio-temporal analysis twice:
    # 1: count all observations per location/time pair
    # 2: count unique vehicles per location/time pair

    logger = logging.getLogger('VehicleHeatmap')
    logging.basicConfig(filename="./logs/vehicleHeatmap.log", encoding='utf-8', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger.info("\n\n")

    # Grab the data
    # NOTE: Caching is difficult because data types would get messed up
    vehicleDf, roadDf = ntdas.LoadData(dataDir, numRows=-1)

    # Let's start with specific dates of data
    #dateCutoff = pd.Timestamp(year=2020, month=10, day=6, hour=0, minute=0, second=0)
    dateCutoff = pd.Timestamp(year=2020, month=10, day=7, hour=0, minute=0, second=0)
    #dateCutoff = pd.Timestamp(year=2020, month=10, day=10, hour=0, minute=0, second=0)
    
    vehicleDf = vehicleDf[vehicleDf[ntdas.TIMESTAMP_COL] < dateCutoff]


    # We only want Denver ZIP codes for the roads
    roadDf = roadDf[roadDf['zip'].isin(ntdas.DENVER_ZIPS)]

    # Take out rows with a travel time of 0 minutes
    vehicleDf = vehicleDf[vehicleDf[ntdas.TRAVEL_TIME_COL] > 0]

    COL_OF_I = 'speed'
    #COL_OF_I = ntdas.SPEED_RATIO_COL

    if not (loadResults and resDir.exists()):

        # We need to calculate an end timestamp for each measurement
        vehicleDf[ntdas.INTERVAL_COL] = vehicleDf.apply(ntdas.CalcInterval, axis=1)

        # Calculate ratio of speed to reference speed
        vehicleDf[ntdas.SPEED_RATIO_COL] = vehicleDf[ntdas.SPEED_COL] / vehicleDf[ntdas.REFERENCE_COL]

        graph = GranularityGraph('STEvalGraph', Path('./logs/VehicleHeatmapGraph.log'))

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

        # Try and load it first
        if loadGraph:
            msg = "Loading graph..."
            print(msg)
            logger.info(msg)
            graph.LoadGraph(graphsDir)
        else:

            # Now, setup the graph
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

        # Do the work

        # Get a gator object
        gator = Gator(graph, Path('./logs/STEvalGator.log'))

        # Drop unneeded columns before the join
        roadDf = roadDf[[ntdas.SEG_ID_COL, "GISJOIN"]]

        # Before aggregation, we need to do a join
        # to assign ZCTAs to each vehicle reading
        joinedDf = pd.merge(vehicleDf, roadDf, on='tmc', how='inner')

        # Drop NANs
        joinedDf = joinedDf.dropna(subset=[ntdas.SPEED_RATIO_COL])

        # Delete the dataframes to save memory
        del vehicleDf
        del roadDf

        # Do the scaling
        msg = "Starting scaling operation..."
        print(msg)
        logger.info(msg)
        st = time.time()
        obsResDf = gator.SpatioTemporalEqualize(joinedDf, sdGdf,
                                             TID.HOUR, GEID.ZCTA, GEID.SD,
                                             'GISJOIN', 'GISJOIN', ntdas.INTERVAL_COL,
                                             None, COL_OF_I, None, None,
                                             AggMethod.SUM, AggMethod.COUNT, EdgeType.AREA,
                                             True, True)
        et = time.time()
        msg = f"Finished scaling operation, runtime was {et - st} seconds."
        print(msg)
        logger.info(msg)

        # Fix the ordering of the multiindex
        obsResDf = obsResDf.swaplevel().sort_index(level=0, inplace=False)

        # Save it for speed ups
        obsResDf.to_csv(resDir / Path('hmVehicleObs.csv'))

        # Verify counts
        resCount = obsResDf[COL_OF_I].sum()
        print(resCount)
        print(len(joinedDf))

        
    # Load the results file
    else:

        msg = "Loading results file..."
        print(msg)
        logger.info(msg)

        obsResDf = pd.read_csv(resDir / Path('hmVehicleObs.csv'))

        # Make the interval column timestamps
        obsResDf[ntdas.INTERVAL_COL] = pd.to_datetime(obsResDf[ntdas.INTERVAL_COL])

        # Reform the multiindex
        obsResDf = obsResDf.set_index(['GISJOIN', ntdas.INTERVAL_COL])
    
    print(obsResDf.index.get_level_values(0))

    





if __name__ == "__main__":
    VehicleHeatmap()