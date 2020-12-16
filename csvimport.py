#!/bin/env python36
import csv, requests, json, logging, configparser, pprint, copy
from sys import exit, exc_info
from optparse import OptionParser,OptionGroup
from os import access,R_OK
global snipemodels

def patch(snipeid, item, data, header):
     if options.dryrun is True:
         logger.info(f"Dry run: Would have tried to update Snipe asset number {snipeid}, field {str(item)} with {str(data)}")
         return 0
     payload = "{\"%s\":\"%s\"}" % (str(item), str(data))
     patch = requests.request("PATCH", SNIPE_URL + "/api/v1/hardware/" + str(snipeid), headers=header, data=payload)
     newjs = json.loads(patch.text)
     if newjs['status'] != 'error':
         logger.info(f"Updated Snipe asset number {snipeid}, field {str(item)} with {str(data)}")
         return newjs
     else:
         if newjs['messages'] is 429:
             logger.error("Received error 429: API rate limited, exiting")
             exit(4)
         else:
             logger.error(f"Failed to update Snipe asset number {snipeid}: {newjs['messages']}")
         return 1

def sniperequest(URL, QUERYSTRING, header):
   try: id = requests.request("GET", URL, headers=header, params=QUERYSTRING) 
   except requests.exceptions.RequestException as e:
       logger.error("Error connecting to Snipe: %s" % e)
       exit(1)
   js = json.loads(id.text)
   if 'error' in js:
       if js['error'] == 'Unauthorized.':
           logger.error("Error from Snipe: Unauthorized (check API key)")
       else: logger.error("Error from Snipe: %s" % js['error'])
       exit(1)
   return(js)

def update(row, js, fields, snipeid, header):
    builtins = {'Name':'name','Asset Tag':'asset_tag','Serial':'serial','Warranty Months':'warranty_months','Order Number':'order_number','Purchase Cost':'purchase cost','Purchase Date':'purchase_date','Notes':'notes'}
    for entry in fields:
# Blank CSV entries should be set to None as that's what Snipe returns for empty fields
        if row[entry] is '': row[entry] = 'None'
# Check each field in Snipe-IT against CSV
        if entry in snipefields:
            logger.debug(f"{row['Item Name']}: Found {entry} in Snipe-IT fields {snipefields[entry]}")
            #TODO: check if entry in Snipe matches CSV, if so ignore else patch
            for x in js['rows']:
                if x['id'] == snipeid:
# Custom field update
                    if entry in x['custom_fields']:
                            if js['rows'][0]['custom_fields'][entry]['value'] is '': val = 'None'
                            else: val =  js['rows'][0]['custom_fields'][entry]['value']
                            if x['custom_fields'][entry]['value'] != row[entry]:
                                logger.info(f"{row['Item Name']}: Snipe and CSV don't match for {entry}: CSV has {row[entry]}, Snipe has {val}")
                                result = patch(snipeid, js['rows'][0]['custom_fields'][entry]['field'], row[entry], header)
                                if result != 1:
                                    logger.info(f"{row['Item Name']} updated {snipefields[entry]} with {row[entry]}.")
                            else: logger.debug(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
# Built-in field update
                    elif entry in builtins:
# Snipe API returns 'x months' for warranty_months, but only accepts an integer; workaround this
                        if entry == 'Warranty Months' and x['warranty_months'] is not None: 
                            x['warranty_months'] = x['warranty_months'][:-7]
# Compare fields and update if they differ
                        if x[builtins[entry]] != row[entry]:
# Penguin Computing doesn't update BIOS to include serial, so their SN and assume you kept Snipe up to date yourself
                            if entry in ["Serial"] and row[entry] == '01234567890123456789AB':
                                logger.info("Skipping invalid serial 01234567890123456789AB")
                                continue
                            if js['rows'][0][builtins[entry]] is '': val = 'None'
                            else: val = js['rows'][0][builtins[entry]]
                            logger.info(f"{row['Item Name']}: Snipe and CSV don't match: CSV has {row[entry]}, Snipe has {val}")
                            result = patch(snipeid, builtins[entry], row[entry], header)
                            if result != 1:
                                logger.info(f"{row['Item Name']} updated {snipefields[entry]} with {row[entry]}.")
                        else: logger.debug(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
                    elif entry in ["Model"]:
                        if x['model']['name'] != row[entry]:
                            if row[entry] in snipemodels:
                                logger.info(f"{row['Item Name']}: Snipe and CSV don't match: CSV has {row[entry]}, Snipe has {x['model']['name']}")
                                result = patch(snipeid, "model_id", snipemodels[row[entry]], header)
                                logger.info(f"{row['Item Name']} updated model with {row[entry]} (model {snipemodels[row[entry]]}).")
                            else: logger.error(f"Model {row[entry]} not found in Snipe models list; skipping.")
                        else: logger.debug(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
                    else:
                        logger.error(f"{row['Item Name']}: Couldn't find field {entry} in asset fields")
# Manufacturer is auto-derived by Snipe-IT from model unless creating a new model.
        elif entry == 'Manufacturer':
            pass
        else:
            logger.error(f"Couldn't find {entry} in Snipe-IT fields")

if __name__ == "__main__":
# Logger setup
    logformatter = logging.Formatter(fmt='[%(asctime)-15s %(levelname)6s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger()
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logformatter)
    logger.addHandler(streamhandler)

    parser = OptionParser(usage = "usage: %prog [options] -f FILE")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False, help="set verbosity level")
    parser.add_option("-d", "--dry-run", dest="dryrun", action="store_true", default=False, help="run without executing changes")
    parser.add_option("-o", "--overwrite", dest="overwrite", action="store_true", default=False, help="overwrite in case of multiple entries")
    parser.add_option("-i", "--inifile", dest="inifile", help="File containing configuration data (default: config.ini)")
    group = OptionGroup(parser, "Required Options")
    group.add_option("-f", "--file", dest="file", help="CSV file to read data from", metavar="FILE")
    parser.add_option_group(group)
    (options, args) = parser.parse_args()

    config = configparser.ConfigParser()
    config['DEFAULT'] = { 'SNIPE_URL': "https://your_snipe_url/",
                      'API_TOKEN': "YOUR_SNIPE_API_TOKEN_HERE" }
    if options.file is None:
        parser.print_help()
        print("\r\nERROR: No CSV file supplied")
        exit(1)
    if options.inifile is not None:
        if access(options.inifile, R_OK) is not False:
            config.read(options.inifile)
        else: 
            print(f"ERROR: cannot read INI file: {options.inifile}")
            exit(1)
    else: config.read("config.ini")
    SNIPE_URL = config['DEFAULT']['SNIPE_URL']
    API_TOKEN = config['DEFAULT']['API_TOKEN']

    if options.verbose is True:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    header = {'Authorization': "Bearer " + API_TOKEN, 'Accept': "application/json", 'Content-type':"application/json" }
# Build dictionary of Snipe internal fields
    js = sniperequest(SNIPE_URL + "/api/v1/fieldsets", {"search":""}, header)
    snipefields = {}
# Catch API error 429 (API overload)
    if not 'rows' in js:
        if 'status' in js and 'error' in js['status']:
            if js['messages'] is 429:
                logger.error("Received error 429: API rate limited, exiting")
            else:
                logger.error(f"Received error {js['messages']}")
            exit(2)
        else:
            logger.error(f"Undefined error: {js}")
            exit(2)
# Continue processing
    for count in js['rows']:
        for field in count['fields']['rows']:
            snipefields[field['name']] = field['db_column_name']
# Add easily importable built-in fields; note Model is functionally different
    snipefields.update({"Serial":"serial","Asset Tag":"asset_tag","Name":"name","Warranty Months":"warranty_months",'Order Number':'order_number','Purchase Cost':'purchase cost','Purchase Date':'purchase_date','Notes':'notes','Model':'model'})
    pp = pprint.PrettyPrinter(indent=4)
    logger.debug("Snipe fields built: \r\n%s" % pp.pformat(snipefields))
    logger.debug("Snipe update:")

# Build list of asset models 
    modeljs = sniperequest(SNIPE_URL + "/api/v1/models", {"search":""}, header)
    snipemodels = {}
    for item in modeljs['rows']:
        logger.debug(f"Adding {item['name']} with id {item['id']} to model list")
        snipemodels.update({item['name']:item['id']})

    try:
        with open(options.file) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            if 'Item Name' not in csv_reader.fieldnames:
                logger.error("CSV file must include 'Item Name' column for lookup in Snipe-IT.")
                logger.error(f"Fields are: {csv_reader.fieldnames}")
                exit(1)

# Build dictionary of Snipe internal fields
            for row in csv_reader:
                querystring = {"offset":"0","search":row['Item Name']}
                header = {'Authorization': "Bearer " + API_TOKEN, 'Accept': "application/json", 'Content-type':"application/json" }
                logger.debug(f"Searching with query {querystring}")
                js  = sniperequest(SNIPE_URL + "/api/v1/hardware", querystring, header)
                if 'total' in js and js['total'] == 1:
                    snipeid = js['rows'][0]['id']
                    logger.debug(f"Snipe-IT ID for {row['Item Name']} is {snipeid}")
                elif 'status' in js and 'error' in js['status'] and js['messages'] == 429:
                    logger.info("Got error 429 (API rate limited), exiting.")
                    exit(2)
# Multiple entries in Snipe for same item
                elif js['total'] > 1:
                    buf = ','.join(item['name'] + " (" + item['asset_tag'] + ")" for item in js['rows'])
                    if options.overwrite is False:
                        logger.error(f"Skipping due to multiple entries for {row['Item Name']}: {buf}")
                        continue
                    else:
                        logger.info(f"Got multiple entries for {row['Item Name']}: {buf}")
                        logger.info("Option overwrite enabled, overwriting data for entries.")
                        for x in range(len(js['rows'])):
                            snipeid = js['rows'][x]['id']
                            fields = (x for x in csv_reader.fieldnames if "Item Name" not in x)
                            update(row, js, fields, snipeid, header)
                        continue
                else:    
                    snipeid = "Unknown"
                    logger.error(f"Couldn't find {row['Item Name']} in Snipe")
                    continue
# Actual update logic
                fields = (x for x in csv_reader.fieldnames if "Item Name" not in x)
                update(row, js, fields, snipeid, header)
    except IOError as e:
        logger.error(e)
        exit(1)
    except TypeError as e:
        logger.error(e)
        exit(1)
