



import os
from pathlib import Path
import zipfile

STATES = {

    '010': 'Alabama',
    '020': 'Alaska',
    '040': 'Arizona',
    '050': 'Arkansas',
    '060': 'California',
    '080': 'Colorado',
    '090': 'Connecticut',
    '100': 'Delaware',
    '110': 'District of Columbia',
    '120': 'Florida',
    '130': 'Georgia',
    '150': 'Hawaii',
    '160': 'Idaho',
    '170': 'Illinois',
    '180': 'Indiana',
    '190': 'Iowa',
    '200': 'Kansas',
    '210': 'Kentucky',
    '220': 'Louisiana',
    '230': 'Maine',
    '240': 'Maryland',
    '250': 'Massachusetts',
    '260': 'Michigan',
    '270': 'Minnesota',
    '280': 'Mississippi',
    '290': 'Missouri',
    '300': 'Montana',
    '310': 'Nebraska',
    '320': 'Nevada',
    '330': 'New Hampshire',
    '340': 'New Jersey',
    '350': 'New Mexico',
    '360': 'New York',
    '370': 'North Carolina',
    '380': 'North Dakota',
    '390': 'Ohio',
    '400': 'Oklahoma',
    '410': 'Oregon',
    '420': 'Pennsylvania',
    '440': 'Rhode Island',
    '450': 'South Carolina',
    '460': 'South Dakota',
    '470': 'Tennessee',
    '480': 'Texas',
    '490': 'Utah',
    '500': 'Vermont',
    '510': 'Virginia',
    '530': 'Washington',
    '540': 'West Virginia',
    '550': 'Wisconsin',
    '560': 'Wyoming',
    '720': 'Puerto Rico'

}


def main():
    for k in STATES:
        # Form the file name
        fName = Path(f'./nhgis0005_shapefile_tl2020_{k}_block_2020.zip')

        # Skip files we already did
        if not fName.exists():
            continue

        # Make a new folder with the name of the state
        dirName = Path(f'./{STATES[k]}')
        dirName.mkdir()

        # Move the file to the new folder
        dest = dirName / fName
        fName.rename(dest)

        # Unzip the file inside the folder
        print(f"Unzipping {dest}")
        zipfile.ZipFile(dest).extractall(dirName)

        # Now move the ZIP to the bkp folder
        bkpDest = Path('../bkp/blocks/') / fName
        dest.rename(bkpDest)




if __name__ == "__main__":
    main()
