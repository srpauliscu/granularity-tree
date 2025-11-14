

import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, mapping, shape
import math



# Script to generate the polygons for the sample entities

def main():

    # Read in the files
    states = pd.read_csv("./tests/states.csv")
    counties = pd.read_csv("./tests/counties.csv")
    zips = pd.read_csv("./tests/zips.csv")

    # Combination of manual and calculated coordinates

    ### States ###
    stateShapes = [Polygon() for i in range(states.shape[0])]
    stateArea = 1000
    SL = math.sqrt(stateArea)
    for ind, row in states.iterrows():
        if row['ID'] == "s0":
            stateShapes[0] = Polygon((
                (0, SL),
                (0, 2*SL),
                (SL, 2*SL),
                (SL, SL)
            ))

        elif row['ID'] == "s1":
            stateShapes[1] = Polygon((
                (SL, SL),
                (SL, 2*SL),
                (2*SL, 2*SL),
                (2*SL, SL)
            ))

        elif row['ID'] == "s2":
            stateShapes[2] = Polygon((
                (SL, 0),
                (SL, SL),
                (2*SL, SL),
                (2*SL, 0)
            ))

        elif row['ID'] == "s3":
            stateShapes[3] = Polygon((
                (0, 0),
                (0, SL),
                (SL, SL),
                (SL, 0)
            ))
    
    # Sanity check
    for s in stateShapes:
        assert s.area == 1000

    # Map to strings first
    mappedStateShapes = [mapping(s) for s in stateShapes]

    # Append new column
    states['shape'] = mappedStateShapes

    
    ### Counties ###
    countyShapes = [Polygon() for i in range(counties.shape[0])]
    for ind, row in counties.iterrows():
        # Grab the listed area of the county
        ea = row['Area']
        curCounty = int(row['ID'][1:])

        if curCounty == 0:
            countyShapes[curCounty] = Polygon((
                (0, 1.5*SL),
                (0, 2*SL),
                ((2.*ea) / SL, 2.*SL),
                ((2.*ea) / SL, 1.5*SL)
            ))
            
        if curCounty == 1:
            countyShapes[curCounty] = Polygon((
                (0, SL),
                (0, 1.5*SL),
                (.5*SL, 1.5*SL),
                (.5*SL, SL)
            ))

        if curCounty == 2:
            countyShapes[curCounty] = Polygon((
                (.5*SL, SL),
                (.5*SL, 2*SL),
                (SL, 2*SL),
                (SL, SL)
            ))

        if curCounty == 3:
            countyShapes[curCounty] = Polygon((
                ((.5*SL-(2.*ea/SL)), 1.5*SL),
                ((.5*SL-(2.*ea/SL)), 2*SL),
                (.5*SL, 2*SL),
                (.5*SL, 1.5*SL)
            ))

        if curCounty == 4:
            countyShapes[curCounty] = Polygon((
                (SL, 1.5*SL),
                (SL, 2*SL),
                (1.5*SL, 2*SL),
                (1.5*SL, 1.5*SL)
            ))

        if curCounty == 5:
            countyShapes[curCounty] = Polygon((
                (SL, SL),
                (SL, 1.5*SL),
                (1.5*SL, 1.5*SL),
                (1.5*SL, 2*SL),
                (2*SL, 2*SL),
                (2*SL, SL)
            ))

        if curCounty == 6:
            countyShapes[curCounty] = Polygon((
                (0, 0),
                (0, SL),
                (SL / 3., SL),
                (SL / 3., 0)
            ))

        if curCounty == 7:
            countyShapes[curCounty] = Polygon((
                (SL / 3., 0),
                (SL / 3., SL),
                ((2*SL) / 3., SL),
                ((2*SL) / 3., 0)
            ))

        if curCounty == 8:
            countyShapes[curCounty] = Polygon((
                ((2*SL) / 3., 0),
                ((2*SL) / 3., SL),
                (SL, SL),
                (SL, 0)
            ))

        if curCounty == 9:
            countyShapes[curCounty] = Polygon((
                (SL, 0),
                (SL, .5*SL),
                (1.5*SL, .5*SL),
                (1.5*SL, 0)
            ))

        if curCounty == 10:
            countyShapes[curCounty] = Polygon((
                (1.5*SL, 0),
                (1.5*SL, .5*SL),
                (2*SL, .5*SL),
                (2*SL, 0)
            ))

        if curCounty == 11:
            countyShapes[curCounty] = Polygon((
                (SL, .5*SL),
                (SL, SL),
                (2*SL, SL),
                (2*SL, .5*SL)
            ))

        # Sanity check each round
        if not math.isclose(countyShapes[curCounty].area, ea):
            # Edge cases for the thirds
            if ((curCounty == 6 and int(countyShapes[curCounty].area) == ea) or
                (curCounty == 7 and int(countyShapes[curCounty].area) == ea) or
                (curCounty == 8 and int(countyShapes[curCounty].area) + 1 == ea)):
                pass
            else:
                print(f"County {curCounty}")
                print(f"Calculated area: {countyShapes[curCounty].area}")
                print(f"Expected area: {ea}")
                raise RuntimeError

    # Map to strings first
    mappedCountyShapes = [mapping(s) for s in countyShapes]

    # Append new column
    counties['shape'] = mappedCountyShapes

    ### ZIP codes ###
    zipShapes = [Polygon() for i in range(zips.shape[0])]
    for ind, row in zips.iterrows():

        # Grab the listed area of the zip
        ea = row['Area']
        curZip = int(row['ID'][1:])

        if curZip == 0:
            zipShapes[curZip] = Polygon((
                (0, 1.5*SL),
                (0, 2*SL),
                (.5*SL, 2*SL),
                (.5*SL, 1.5*SL)
            ))

        if curZip == 1:
            zipShapes[curZip] = Polygon((
                (.5*SL, 1.5*SL),
                (.5*SL, 2*SL),
                (1.5*SL, 2*SL),
                (1.5*SL, 1.5*SL)
            ))

        if curZip == 2:
            zipShapes[curZip] = Polygon((
                (1.5*SL, 1.5*SL),
                (1.5*SL, 2*SL),
                (2*SL, 2*SL),
                (2*SL, 1.5*SL)
            ))

        if curZip == 3:
            zipShapes[curZip] = Polygon((
                (0, .5*SL),
                (0, 1.5*SL),
                (.5*SL, 1.5*SL),
                (.5*SL, SL),
                ((2*SL) / 3., SL),
                ((2*SL) / 3., .5*SL)
            ))

        if curZip == 4:
            zipShapes[curZip] = Polygon((
                ((2*SL) / 3., .5*SL),
                ((2*SL) / 3., SL),
                (.5*SL, SL),
                (.5*SL, 1.5*SL),
                (1.5*SL, 1.5*SL),
                (1.5*SL, .5*SL)
            ))

        if curZip == 5:
            zipShapes[curZip] = Polygon((
                (1.5*SL, .5*SL),
                (1.5*SL, 1.5*SL),
                (2*SL, 1.5*SL),
                (2*SL, .5*SL)
            ))

        if curZip == 6:
            zipShapes[curZip] = Polygon((
                (0, 0),
                (0, .5*SL),
                (1.5*SL, .5*SL),
                (1.5*SL, .0)
            ))

        if curZip == 7:
            zipShapes[curZip] = Polygon((
                (1.5*SL, 0),
                (1.5*SL, .5*SL),
                (2*SL, .5*SL),
                (2*SL, 0)
            ))
        
        # Sanity check each round
        if not math.isclose(zipShapes[curZip].area, ea):
            if ((curZip == 3 and int(zipShapes[curZip].area) == ea) or
                curZip == 4 and int(zipShapes[curZip].area) + 1 == ea):
                pass
            else:
                print(f"ZIP {curZip}")
                print(f"Calculated area: {zipShapes[curZip].area}")
                print(f"Expected area: {ea}")
                raise RuntimeError


    # Map to strings first
    mappedZipShapes = [mapping(s) for s in zipShapes]

    # Append new column
    zips['shape'] = mappedZipShapes


    # Save over the old csvs
    states.to_csv("./tests/states.csv", index=False)
    counties.to_csv("./tests/counties.csv", index=False)
    zips.to_csv("./tests/zips.csv", index=False)

    # Sanity check that the shapes can be loaded
    states = pd.read_csv("./tests/states.csv")
    counties = pd.read_csv("./tests/counties.csv")
    zips = pd.read_csv("./tests/zips.csv")

    states['shape'] = states['shape'].apply(lambda x: shape(eval(x)))
    counties['shape'] = counties['shape'].apply(lambda x: shape(eval(x)))
    zips['shape'] = zips['shape'].apply(lambda x: shape(eval(x)))

    assert isinstance(states['shape'].iloc[0], Polygon)
    assert isinstance(counties['shape'].iloc[0], Polygon)
    assert isinstance(zips['shape'].iloc[0], Polygon)






if __name__ == "__main__":
    main()