# snipeit-csvimporter
This project allows for updating assets in Snipe-IT from a CSV file using Item Name rather than asset tag as the key value, as is required for GUI-based CSV imports from within Snipe-IT.  Custom fields are well-supported; only serial number has been tested extensively from the available built-in fields (asset tag, serial, warranty_expires, warranty_months, name) 

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
Run csvimporter.py with your CSV file as the sole argument and things should just work.

## Configuration
1. Edit config.ini:
    1. Include the proper Snipe-IT server as SNIPE_URL
    2. [Generate and include an API key as API_TOKEN for Snipe-IT access.](https://snipe-it.readme.io/reference#generating-api-tokens)
