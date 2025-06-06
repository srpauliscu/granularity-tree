

import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path


def NationRegion():
    pass

def RegionState(regionGdf: gpd.GeoDataFrame, stateGdf: gpd.GeoDataFrame):

    pass

def StateCounty():
    pass

def CountyCity():
    pass

def CountyZip():
    pass

def CountyZCTA():
    pass

def CountyBlockGroup():
    pass

def BlockGroupBlock():
    pass

def BlockTract():
    pass


def main():

    # Folder information
    parentDir = Path("./data/tiger")

    '''
    # Load in from the top down, starting with nation
    nationGdf = gpd.read_file(parentDir / Path("./nation/US_nation_2023.shp"))

    print(nationGdf.head())
    nationGdf.plot()

    stateGdf = gpd.read_file(parentDir / Path("./state/US_state_2023.shp"))
    print(stateGdf.head(n=5))

    countyGdf = gpd.read_file(parentDir / Path("./county/US_county_2023.shp"))
    print(countyGdf.head(n=5))
    countyGdf.plot()
    '''

    zctaGdf = gpd.read_file(parentDir / Path("./zcta/US_zcta_2023.shp"))
    print(zctaGdf.head(n=5))

    tractGdf = gpd.read_file(parentDir / Path("./tract/US_tract_2023.shp"))
    print(tractGdf.head(n=5))

    return
    

    #ov = gpd.overlay(nationGdf, countyGdf.head(n=1), how="intersection")
    ov = gpd.overlay(stateGdf.head(n=1), countyGdf.head(n=70), how="intersection")
    

    print(ov.head())
    print(ov.geometry.area)


if __name__ == "__main__":
    main()