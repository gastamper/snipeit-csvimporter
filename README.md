# snipeit-csvimporter
This project allows for updating assets in Snipe-IT from a CSV file using Item Name rather than asset tag as the key value, as is required for GUI-based CSV imports from within Snipe-IT.  Custom fields are well-supported, as are most built-in fields (name, asset tag, warranty months, purchase date, purchase cost, order number, notes).

## Current state:
1. Updates to existing items work as expected.
2. Updates to nonexistent items should fail gracefully.
3. Creation of new items from CSV is *not* planned.

## Requirements:
1. A Snipe-IT server accessible from wherever the importer is running.
2. A properly formatted CSV file which includes the 'Item Name' column.
3. Python 3.

## Basic usage:
Your CSV must include an 'Item Name' column.  Any columns which don't exist in Snipe-IT should be ignored by the importer.
```
Usage: csvimport.py [options] -f FILE

Options:
  -h, --help            show this help message and exit
  -v, --verbose         set verbosity level
  -d, --dry-run         run without executing changes
  -o, --overwrite       overwrite in case of multiple entries
  -i INIFILE, --inifile=INIFILE
                        File containing configuration data (default:
                        config.ini)

  Required Options:
    -f FILE, --file=FILE
                        CSV file to read data from
```


## Configuration
1. Edit config.ini:
    1. Include the proper Snipe-IT server as SNIPE_URL
    2. [Generate and include an API key as API_TOKEN for Snipe-IT access.](https://snipe-it.readme.io/reference#generating-api-tokens)
