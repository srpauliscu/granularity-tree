# Granularity Tree
Codebase for a knowledge graph-based approach for spatio-temporal data fusion.

## Current Version: 1.0.0

# Data

The four case studies, with the exception of Case Study 2, relied exclusively on publically available data.  Below are links to individual datasets used in all case studies.

## Graph Building

There were several datasets used during for graph construction in one or more case studies.

**Geometries**: The geometries for the spatial entities were obtained from [NHGIS](https://www.nhgis.org/) as TIGER/Line shapefiles, using the files from the year 2023.  These files also contained GISJOIN ID assignments used throughout.

**Entity Matching**:  We obtained files that map one entity to another from two locations provided by the U.S. Census.  For block assignment files, we used the 2010 files from [here](https://www.census.gov/geographies/reference-files/time-series/geo/block-assignment-files.2010.html#list-tab-361828852).  For all other entity relationships, we used the 2020 files from [here](https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html#list-tab-1709067297).

**Population**: For the population data used in constructing the population-based weights, we obtained Census data for each state individually, from the following sources:
- [Connecticut](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US09$1000000)
- [Vermont](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US50$1000000)
- [Oregon](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US41$1000000)
- [Tennessee](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US47$1000000)
- [New York](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US36$1000000)
- [Minnesota](https://data.census.gov/table/DECENNIALPL2020.P1?q=population&g=040XX00US27$1000000)


## Case Study 1: Vehicle Charging

For the EV charging data, we used data for the city of [Palo Alto](https://www.kaggle.com/datasets/venkatsairo4899/ev-charging-station-usage-of-california-city).

## Case Study 2: Traffic Patterns

The data used for this case study was provided by [NTDAS](https://ntdas.ieee.org/).  This is the only commercial dataset used in this manuscript.  In lieu of providing the raw data, which is against licensing terms, we have provided a sample dataset with dummy data that can be used to run the example.

## Case Study 3: Income vs. Green Policies


# License

This codebase is licensed under GNU AGPLv3.  Please see LICENSE for more information.
