# sm-analyze-stats

Scripts to analyze a given Stepmania Stats.xml file for stats (most played songs, leaderboards, etc.)

You can run this code but I don't really expect people to run it for themselves, it's more for people to look at and steal/reuse for their own analysis needs :) 

## How to use

Standard Python business:
  * Dependencies are in `requirements.txt`. Install with `pip install -r requirements.txt`.
    * Optionally create a virtual environment before installing if you don't want to clutter your main Python installation. `python -m venv venv`

The analysis uses your Stepmania `Stats.xml` file as well as a scan of your Stepmania songs folder (not required, but it greatly improves the quality of the output data.)

To scan your Stepmania folder use the `getavailablesongs.py` script (usage: `getavailablesongs.py (path to your songs folder)`). After iterating through your song folder for a while, it will generate a CSV file which the data analysis knows to look for and read.

The data analysis is done in a Jupyter notebook (after installing Jupyter, run `jupyter notebook`). There's a preamble to load in required data, then the code to generate each data table appears in its own section. Run the preamble then run each tables' section one-by-one. Each section is structured to write the data to your clipboard, which you can then paste into Excel or Google Sheets or wherever you want.

## Available statistics

 * General info
   * List of packs on cab
   * Number of songs + charts in each pack 
     * Number of songs + charts for singles/doubles
   * Difficulty histogram of each pack
 * Most played charts
   * all songs
   * doubles only
 * Most played songs + breakdown of playcount per song difficulty
   * all songs
   * doubles only
 * Most played packs + top n played songs per pack
 * Recently played packs
 * Pack completion - percentage of pack played
   * Percentage of songs played
   * Percentage of charts played
   * Score breakdown of all charts in the pack (quads, tristars, etc.)
 * Highest passes
   * singles
   * doubles
 * Highest scores
   * singles
   * doubles
 * Leaderboard analysis
   * Number of 1st places, 2nd places, etc. of each player