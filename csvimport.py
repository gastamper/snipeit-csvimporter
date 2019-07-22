import csv, requests, json, logging, configparser
from sys import exit, exc_info, argv
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False, help="set verbosity level")
(options, args) = parser.parse_args()
print(f"{options} {args}")
#exit(0)
config = configparser.ConfigParser()
config['DEFAULT'] = { 'SNIPE_URL': "https://your_snipe_url/",
                      'API_TOKEN': "YOUR_SNIPE_API_TOKEN_HERE" }
config.read('config.ini')
SNIPE_URL = config['DEFAULT']['SNIPE_URL']
API_TOKEN = config['DEFAULT']['API_TOKEN']

header = {'Authorization': "Bearer " + API_TOKEN, 'Accept': "application/json", 'Content-type':"application/json" }
def patch(snipeid, item, data):
     payload = "{\"%s\":\"%s\"}" % (str(item), str(data))
     patch = requests.request("PATCH", SNIPE_URL + "/api/v1/hardware/" + str(snipeid), headers=header, data=payload)
     newjs = json.loads(patch.text)
     if newjs['status'] != 'error':
         logger.info(f"Updated Snipe asset number {snipeid}, field {str(item)} with {str(data)}")
#         logger.debug(f"{newjs}")
         return newjs
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

# Logger setup
logformatter = logging.Formatter(fmt='[%(asctime)-15s %(levelname)6s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logformatter)
logger.addHandler(streamhandler)
logger.setLevel(logging.DEBUG)

if len(argv) is 1:
    logger.error(f"Usage: {argv[0]} [CSV file]")
    exit(1)

try:
  with open(argv[1]) as csv_file:
    csv_reader = csv.DictReader(csv_file)
    if 'Item Name' not in csv_reader.fieldnames:
        logger.error("CSV file must include 'Item Names' column for lookup in Snipe-IT.")
        exit(1)
# Build dictionary of Snipe internal fields
    js = sniperequest(SNIPE_URL + "/api/v1/fieldsets", {"search":""})
    snipefields = {}
# Catch API error 429 (API overload)
    if not 'rows' in js:
        if 'status' in js and 'error' in js['status']:
            logger.error("Received error {js['messages']}")
            exit(2)
        else:
            logger.error("Undefined error")
            exit(2)
# Continue processing
    for count in js['rows']:
        for field in count['fields']['rows']:
            snipefields[field['name']] = field['db_column_name']
    logger.debug("Snipe fields built: %s" % snipefields)

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
            logger.info("Got error 429 (API overload), waiting.")
            from time import sleep
            sleep(10)
            js  = sniperequest(SNIPE_URL + "/api/v1/hardware", querystring)
            if 'error' in js and js['error'] is 429:
                logger.error("Got 429 again, failing out")
                continue
        elif js['total'] > 1:
            buf = ','.join(item['name'] + " (" + item['asset_tag'] + ")" for item in js['rows'])
            logger.error(f"Got multiple entries for {row['Item Name']}: {buf}")
            continue
        else:    
            snipeid = "Unknown"
            logger.error(f"Couldn't find {row['Item Name']} in Snipe")
            continue
# Actual update logic
        fields = (x for x in csv_reader.fieldnames if "Item Name" not in x)
        for entry in fields:
# Blank CSV entries should be set to None as that's what Snipe returns for empty fields
            if row[entry] is '': row[entry] = None
# Check each field in Snipe-IT against CSV
            if entry in snipefields:
                logger.debug(f"{row['Item Name']}: Found {entry} in Snipe-IT fields {snipefields[entry]}")
                #TODO: check if entry in Snipe matches CSV, if so ignore else patch
                if entry in js['rows'][0]['custom_fields']:
                        if js['rows'][0]['custom_fields'][entry]['value'] != row[entry]:
                            logger.info(f"{row['Item Name']}: Snipe and CSV don't match: CSV has {row[entry]}, Snipe has {js['rows'][0]['custom_fields'][entry]['value']}")
                            result = patch(snipeid, js['rows'][0]['custom_fields'][entry]['field'], row[entry])
                            if result != 1:
                                logger.info(f"{row['Item Name']} updated.")
                        else: logger.info(f"{row['Item Name']}: Snipe and CSV match for {entry}: {row[entry]}")
                elif entry in js['rows'][0]:
                        logger.info("Fix this")
                else:
                    logger.error(f"{row['Item Name']}: Couldn't find field {entry} in asset fields")
            else:
                logger.error(f"Couldn't find {entry} in Snipe-IT fields")
except IOError as e:
    logger.error(f"{e}")
