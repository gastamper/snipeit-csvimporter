#!/usr/bin/env python36
import csv, requests, json, logging, configparser, pprint
from sys import exit, exc_info
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False, help="set verbosity level")
parser.add_option("-d", "--dry-run", dest="dryrun", action="store_true", default=False, help="run without executing changes")
parser.add_option("-o", "--overwrite", dest="overwrite", action="store_true", default=False, help="overwrite in case of multiple entries")
parser.add_option("-f", "--file", dest="file", help="CSV file to read data from", metavar="FILE")
(options, args) = parser.parse_args()

config = configparser.ConfigParser()
config['DEFAULT'] = { 'SNIPE_URL': "https://your_snipe_url/",
                      'API_TOKEN': "YOUR_SNIPE_API_TOKEN_HERE" }
config.read('config.ini')
SNIPE_URL = config['DEFAULT']['SNIPE_URL']
API_TOKEN = config['DEFAULT']['API_TOKEN']

header = {'Authorization': "Bearer " + API_TOKEN, 'Accept': "application/json", 'Content-type':"application/json" }
def patch(snipeid, item, data):
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

def sniperequest(URL, QUERYSTRING):
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

def update(row, js, fields, snipeid):
    builtins = {'Name':'name','Asset Tag':'asset_tag','Serial':'serial','Warranty Months':'warranty_months','Order Number':'order_number','Purchase Cost':'purchase cost','Purchase Date':'purchase_date','Notes':'notes'}
    for entry in fields:
# Blank CSV entries should be set to None as that's what Snipe returns for empty fields
        if row[entry] is '': row[entry] = None
# Check each field in Snipe-IT against CSV
        if entry in snipefields:
            logger.debug(f"{row['Item Name']}: Found {entry} in Snipe-IT fields {snipefields[entry]}")
            #TODO: check if entry in Snipe matches CSV, if so ignore else patch
            for x in js['rows']:
                if x['id'] == snipeid:
# Custom field update
                    if entry in x['custom_fields']:
                            if x['custom_fields'][entry]['value'] != row[entry]:
                                if js['rows'][0]['custom_fields'][entry]['value'] is '': val = 'None'
                                else: val =  js['rows'][0]['custom_fields'][entry]['value']
                                logger.info(f"{row['Item Name']}: Snipe and CSV don't match: CSV has {row[entry]}, Snipe has {val}")
                                result = patch(snipeid, js['rows'][0]['custom_fields'][entry]['field'], row[entry])
                                if result != 1:
                                    logger.info(f"{row['Item Name']} updated {snipefields[entry]} with {row[entry]}.")
                            else: logger.debug(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
# Built-in field update
                    elif entry in builtins:
                        if x[builtins[entry]] != row[entry]:
                            if js['rows'][0][builtins[entry]] is '': val = 'None'
                            else: val = js['rows'][0][builtins[entry]]
                            logger.info(f"{row['Item Name']}: Snipe and CSV don't match: CSV has {row[entry]}, Snipe has {val}")
                            result = patch(snipeid, builtins[entry], row[entry])
                            if result != 1:
                                logger.info(f"{row['Item Name']} updated {snipefields[entry]} with {row[entry]}.")
                            else: logger.debug(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
                    else:
                        logger.error(f"{row['Item Name']}: Couldn't find field {entry} in asset fields")
        else:
            logger.error(f"Couldn't find {entry} in Snipe-IT fields")

# Logger setup
logformatter = logging.Formatter(fmt='[%(asctime)-15s %(levelname)6s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logformatter)
logger.addHandler(streamhandler)
if options.verbose is True:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

try:
  with open(options.file) as csv_file:
    csv_reader = csv.DictReader(csv_file)
    if 'Item Name' not in csv_reader.fieldnames:
        logger.error("CSV file must include 'Item Name' column for lookup in Snipe-IT.")
        exit(1)
# Build dictionary of Snipe internal fields
    js = sniperequest(SNIPE_URL + "/api/v1/fieldsets", {"search":""})
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
            logger.error("Undefined error")
            exit(2)
# Continue processing
    for count in js['rows']:
        for field in count['fields']['rows']:
            snipefields[field['name']] = field['db_column_name']
# Add easily importable built-in fields
    snipefields.update({"Serial":"serial","Asset Tag":"asset_tag","Name":"name","Warranty Months":"warranty_months",'Order Number':'order_number','Purchase Cost':'purchase cost','Purchase Date':'purchase_date','Notes':'notes'})
    pp = pprint.PrettyPrinter(indent=4)
    logger.debug("Snipe fields built: \r\n%s" % pp.pformat(snipefields))
    logger.debug("Snipe update:")
    for row in csv_reader:
        querystring = {"offset":"0","search":row['Item Name']}
        header = {'Authorization': "Bearer " + API_TOKEN, 'Accept': "application/json", 'Content-type':"application/json" }
        logger.debug(f"Searching with query {querystring}")
        js  = sniperequest(SNIPE_URL + "/api/v1/hardware", querystring)
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
                    update(row, js, fields, snipeid)
                continue
        else:    
            snipeid = "Unknown"
            logger.error(f"Couldn't find {row['Item Name']} in Snipe")
            continue
# Actual update logic
        fields = (x for x in csv_reader.fieldnames if "Item Name" not in x)
        update(row, js, fields, snipeid)
except IOError as e:
    logger.error(f"{e}")
