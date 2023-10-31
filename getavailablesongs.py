# Survey a Stepmania Songs folder and output song information to a csv
# to be loaded by data analysis for better output.

import argparse
import csv
import time
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import simfile
from simfile.dir import SimfileDirectory


def loadfromcsv(path: Path) -> List[List[str]]:
    """Load data from CSV as array"""
    with open(path, newline="", encoding="utf8") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        return [row for row in reader]


def writetocsv(path: Path, data: List[List]) -> None:
    """Write array to CSV"""
    with open(path, "w", newline="", encoding="utf8") as csvfile:
        writer = csv.writer(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for item in data:
            writer.writerow(item)


def translit(normal: Optional[str], transliterated: Optional[str]) -> Tuple[str, str]:
    """
    Behaviour to compute real normal/translit values from those stored in the simfile.
    If one entry is empty, fills it with the other.

    >>> translit("normal", "translit")
    ("normal", "translit")
    >>> translit("normal", "")
    ("normal", "normal")
    """
    if not transliterated:
        transliterated = normal
    return (normal or "", transliterated or "")


def directories(path: Path) -> Iterator[Path]:
    """Iterate over subdirectories of a folder"""
    return (p for p in path.iterdir() if p.is_dir())


def pack_iterator(song_folder: Path) -> List[Path]:
    """Return paths to each pack in a song folder"""
    return sorted(directories(song_folder), key=lambda p: p.stem.lower())


def song_iterator(pack_folder: Path, secrets: bool = False) -> Iterator[Tuple[Path, Path]]:
    """Return paths to each song in a pack folder"""
    if secrets:
        raise NotImplementedError("secrets flag not implemented yet")

    for songpath in sorted(directories(pack_folder), key=lambda p: p.stem.lower()):
        d = SimfileDirectory(songpath)
        smpath = d.simfile_path
        if smpath is None:
            # this song folder didn't contain a simfile, it's not a song
            # (eg. some packs have a folder to hold graphics)
            # skip scanning this folder
            print(f"{songpath} detected as not a song folder, skipping")
            continue

        yield songpath, Path(smpath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="getavailablesongs.py",
        description="Scan Stepmania song folder and generate/update CSV of information.",
    )

    parser.add_argument("path", help="Path to song folder.")
    parser.add_argument(
        "-p",
        "--pack",
        action="append",
        help="If any number of these are specified, scan only these packs from the song folder.",
    )
    parser.add_argument(
        "--skip", help="If this script breaks, you can use this value to resume the search from a given pack name."
    )
    parser.add_argument("--output", default="song_listing.csv", help="Output path.")

    args = parser.parse_args()

    SONGS_PATH = Path(args.path)
    OUTPUT_PATH = Path(args.output)
    FLUSH_OUTPUT_EVERY_SECONDS = 30

    # load previous data if it exists
    if OUTPUT_PATH.exists():
        availablesongs = loadfromcsv(OUTPUT_PATH)
        existing_keys = set(i[0] for i in availablesongs)
    else:
        availablesongs = []
        existing_keys = set()

    start = lastwrite = time.monotonic()

    def pack_listing(songs_folder: Path, pack_filter: List[str], skip_to_pack: Optional[str]) -> Iterator[Path]:
        """Iterate over packs to scan based on command-line options."""
        if pack_filter is None:
            allpacks = pack_iterator(songs_folder)
        else:
            allpacks = [songs_folder / i for i in pack_filter]

        skipping = skip_to_pack is not None
        for packpath in allpacks:
            packname = packpath.name

            # skip entries until (skip_to_pack) is found
            if packname == skip_to_pack:
                skipping = False
            if skipping:
                continue

            yield packpath

    try:
        allpacks = list(pack_listing(SONGS_PATH, args.pack, args.skip))
        for i, packpath in enumerate(allpacks):
            # show which pack we're currently on cause the scan takes a while
            now = time.monotonic()
            print(f"{now-start} | ({i+1}/{len(allpacks)}) {packpath}")

            for songpath, smpath in song_iterator(packpath):
                key = songpath.relative_to(SONGS_PATH).as_posix() + "/"

                # skip adding entries for this song if it already exists
                if key in existing_keys:
                    continue

                # flush the output file every once in a while
                now = time.monotonic()
                if now - lastwrite > FLUSH_OUTPUT_EVERY_SECONDS:
                    writetocsv(OUTPUT_PATH, availablesongs)
                    lastwrite = now

                with open(smpath, encoding="utf8", errors="ignore") as f:
                    # strict=False required to parse simfiles with text between msd tags (e.g. comments)
                    # eg. #TITLE:a;     text here
                    #     #SUBTITLE:b;
                    sm = simfile.load(f, strict=False)

                # add data to file
                # use the transliterated song title
                songtitle = translit(sm.title, sm.titletranslit)[1]
                for c in sm.charts:
                    availablesongs.append((key, songtitle, c.stepstype, c.difficulty, int(float(c.meter))))
    finally:
        writetocsv(OUTPUT_PATH, availablesongs)
