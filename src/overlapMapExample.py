
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


    # ZCTAs aren't bound to one state, so use overlapping instead
    ov = gpd.overlay(countyGdf, schoolGdf, how="intersection", keep_geom_type=False)

    # Add the area as an extra column
    ov['Area'] = ov.geometry.area

    # Remove false positives
    ov = ov[ov['Area'] > 1]

    # Our example is Eagle County
    exampleCounty = ov[ov['NAME_1'] == "Eagle"]
    
    # Calculate overlap factor
    exampleCounty['overlap_factor'] = ov['Area'] / ov['Shape_Area_1']
    print(exampleCounty[['NAME_2', 'overlap_factor']])

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

    # Our example is Eagle County
    exampleCounty = ov[ov['NAME_1'] == "Eagle"]
    print(exampleCounty)

    # Set the zoom before saving
    
    base.set_xlim(-.96*(10**6), -0.85*(10**6))
    base.set_ylim(241000, 332000)
    plt.savefig("./data/overlapMapExampleZoomed.png", dpi=1600)
    #plt.show()







if __name__ == "__main__":
    main()