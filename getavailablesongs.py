# Survey a Stepmania Songs folder and output song information to a csv
# to be loaded by data analysis for better output.

from typing import Iterator, List, Optional, Tuple
from simfile.dir import SimfileDirectory
import simfile
from pathlib import Path
import time
import csv
import argparse

parser = argparse.ArgumentParser(
    prog='getavailablesongs.py',
    description='Scan Stepmania song folder and generate CSV of information.',
)

parser.add_argument('path', help='Path to song folder.')
parser.add_argument('-p', '--pack', action='append', help='If any number of these are specified, scan only these packs from the song folder.')
parser.add_argument('--skip', help='If this script breaks, you can use this value to resume the search from a given pack name.')

args = parser.parse_args()

# ===== Configuration variables =====
PATH = Path(args.path)
OUTPUT_CSV = Path("available.csv")

# if this script breaks, you can use this value to resume the search from a given pack name.
# set this value to None to begin from the start.
skippack = args.skip

def loadfromcsv(path: Path) -> List[List[str]]:
    with open(path, newline='', encoding='utf8') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        return [row for row in reader]

def writetocsv(path: Path, data: List) -> None:
    with open(path, 'w', newline='', encoding='utf8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for item in data:
            writer.writerow(item)

def translit(normal: Optional[str], transliterated: Optional[str]) -> Tuple[str, str]:
    if not transliterated:
        transliterated = normal
    return (normal or "", transliterated or "")

# load previous data if it exists
if OUTPUT_CSV.exists():
    availablesongs = loadfromcsv(OUTPUT_CSV)
    existing_keys = set(i[0] for i in availablesongs)
else:
    availablesongs = []
    existing_keys = set()

skipping = (skippack is not None)
start = lastwrite = time.monotonic()

def directories(path: Path) -> Iterator[Path]:
    return (p for p in path.iterdir() if p.is_dir())

try:
    if args.pack is None:
        allpacks = list(directories(PATH))
    else:
        allpacks = [PATH / i for i in args.pack]
    
    for i,packpath in enumerate(allpacks):
        # show which pack we're currently on cause the scan takes a while
        now = time.monotonic()
        print(f"{now-start} | ({i+1}/{len(allpacks)}) {packpath}")

        packname = packpath.name
        if packname == skippack:
            skipping = False

        if skipping:
            continue

        for songpath in directories(packpath):
            key = songpath.relative_to(PATH).as_posix() + '/'

            # skip adding entries for this song if it already exists
            if key in existing_keys:
                continue
                
            # flush the output file every once in a while
            now = time.monotonic()
            if now - lastwrite > 30:
                writetocsv(OUTPUT_CSV, availablesongs)
                lastwrite = now
            
            d = SimfileDirectory(songpath)
            smpath = d.simfile_path
            if smpath is None:
                # this song folder didn't contain a simfile, it's not a song
                # (eg. some packs have a folder to hold graphics)
                # skip scanning this folder
                print(f"{songpath} detected as not a song folder, skipping")
                continue
        
            with open(smpath, 'r', encoding='utf8', errors='ignore') as f:
                # strict=False required to parse simfiles with text between msd tags
                # eg. #TITLE:a;     text here
                #     #SUBTITLE:b;
                sm = simfile.load(f, strict=False)
                
            # add data to file
            # use the transliterated song title
            songtitle = translit(sm.title, sm.titletranslit)[1]
            for c in sm.charts:
                availablesongs.append((key, songtitle, c.stepstype, c.difficulty, int(float(c.meter))))
finally:
    writetocsv(OUTPUT_CSV, availablesongs)