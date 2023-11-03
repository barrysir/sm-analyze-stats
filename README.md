# sm-analyze-stats

Script to analyze the saved statistics of a Stepmania instance (Stats.xml) and report statistics in an Excel spreadsheet. (This can then be imported into Google Sheets or wherever.)

The only user of this code currently is me so sorry if it's hard to use.


## How to use

### Installation

Standard Python business:
  * Python 3.9+
  * Optionally create a virtual environment before installing if you don't want to clutter your main Python installation. `python -m venv venv` to create the environment, then `venv/Scripts/activate` (or wherever you activation script is) to enter it.
  * Dependencies are in `pyproject.toml`. Install with `pip install .`
  * The `pyproject.toml` also has optional dependencies listed for development and notebook libraries. To install these, e.g. the `notebook` optional dependencies, run `pip install .[notebook]`.
    

### Prerequisite data files

The analysis uses your Stepmania `Stats.xml` file as well as a scan of your Stepmania songs folder. You can usually find this at `(your stepmania folder)/Save/MachineProfile/Stats.xml`.

To scan your Stepmania folder use the `getavailablesongs.py` script (usage: `getavailablesongs.py (path to your songs folder)`). After iterating through your song folder for a while, it will generate a CSV file which the data analysis knows to look for and read.

### Generating the report

The main script is `py main.py`. Provide the data files as command-line arguments. Please view its help page for information on how to use it. By default it will write the finished report to `output.xlsx` (configurable by a command line parameter).

### Optional: Jupyter notebook

A Jupyter notebook (after installing Jupyter, run `jupyter notebook`) is also provided with sections to generate each table individually. You can use this notebook to do your own analysis. More information is written in the notebook.

## Development notes

Using `ruff` for code linting. `ruff format .` -> `ruff check .`.

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