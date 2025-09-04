
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import math
import random

from connecticutGraph import LoadShapefile

# Use a state/county as example
ST_FIPS = '08' # Colorado


def main():

    # Directory info
    parentDir = Path("./data/tiger")

    # Load the county and ZCTA shapefiles
    countyGdf = LoadShapefile(parentDir, 'county')
    schoolGdf = LoadShapefile(parentDir, 'school')

    # Only get one state's data
    countyGdf = countyGdf[countyGdf['STATEFP'] == ST_FIPS]

    #print(zctaGdf.head())
    #quit()

    #print(countyGdf.head())
    #quit()

    # ZCTAs aren't bound to one state, so use overlapping instead
    ov = gpd.overlay(countyGdf, schoolGdf, how="intersection", keep_geom_type=False)

    # Add the area as an extra column
    ov['Area'] = ov.geometry.area

    # Remove false positives
    ov = ov[ov['Area'] > 0]

    # Use the overlaps to filter the original GDF
    schoolGdf = schoolGdf[schoolGdf['GISJOIN'].isin(ov['GISJOIN_2'].to_list())]

    # Use random colors to distinguish adjacent areas
    random.seed(43)
    colors = [f"#{random.randint(0, 0xFFFFFF):06x}" for _ in range(len(schoolGdf))]
    #print(colors[:5])
    #quit()
    schoolGdf['color'] = colors

    #print(ov.head())
    #quit()
    base = schoolGdf.plot(color=schoolGdf['color'])
    #schoolGdf.boundary.plot(ax=base, color='black', linewidth=2, linestyle="dashed")
    countyGdf.boundary.plot(ax=base, color='black')

    plt.show()





if __name__ == "__main__":
    main()