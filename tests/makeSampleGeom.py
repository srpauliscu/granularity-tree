

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
    for shape in stateShapes:
        assert shape.area == 1000

    # Append new column
    states['shape'] = stateShapes

    
    ### Counties ###
    countyShapes = [Polygon() for i in range(counties.shape[0])]
    for ind, row in counties.iterrows():
        # Grab the listed area of the county
        ea = row['Area']
        curCounty = int(row['ID'][-1])

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
        assert countyShapes[curCounty] == ea



if __name__ == "__main__":
    main()