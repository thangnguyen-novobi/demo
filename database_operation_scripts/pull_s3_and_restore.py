"""
Instructions:
1) Set the Odoo server parameters
2) Set the AWS S3 connection parameters
3) Finesse!
Note: Sensitive data such as password and AWS credentials can be populated via environment variables.
"""
import os
import pip
import io

try:
    import boto
    import odoorpc
    # import boto.s3
except ImportError:
    print('- Attempting to install the necessary python package -')
    print('Installing...')
    pip.main(['install', 'boto'])
    pip.main(['install', 'OdooRPC'])
    print('* Done *')

import boto
import odoorpc


##########################
# Odoo server parameters #
##########################
PORT = 80
HOST_NAME = "<Odoo server's host>"
MASTER_PASSWD = os.environ.get('MASTER_PASSWD', "<Odoo server's master password>")
NEW_DATABASE_NAME = "<The database's name to be restored>"


#####################
# AWS S3 parameters #
#####################
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', "<AWS Access Key ID in Security Credentials>")
AWS_ACCESS_KEY_SECRET = os.environ.get('AWS_ACCESS_KEY_SECRET', "<AWS Access Key Secret in Security Credentials>")
BUCKET_NAME = "<Bucket's name to download the backup file>"
BACKUP_FILE_BUCKET_KEY = "<The backup file's key to download>"


def connect_odoorpc():
    """
    Establish connection to odoo database server
    :return: connection object or None
    """
    odoo = None
    try:
        head = 'https://' if PORT == 443 else 'http://'
        odoo = odoorpc.ODOO(host=HOST_NAME, protocol='jsonrpc+ssl' if PORT == 443 else 'jsonrpc', port=PORT)
        print(f'Connected to Odoo server {head}{HOST_NAME}:{PORT}')
    except Exception as e:
        head = 'https://' if PORT == 443 else 'http://'
        print(f"Couldn't connect to Odoo server {head}{HOST_NAME}:{PORT} due to {e}")
        exit(1)
    return odoo


if any(not x for x in [PORT, HOST_NAME, MASTER_PASSWD, NEW_DATABASE_NAME, AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET, BUCKET_NAME, BACKUP_FILE_BUCKET_KEY]):
    print("Missing one or more required parameter settings")
    exit(1)

# Connect to the Odoo server
odoo = connect_odoorpc()
odoo_db = odoo.db

if NEW_DATABASE_NAME in odoo_db.list():
    print(f"There has already been a database with the same name {NEW_DATABASE_NAME}")
    exit(1)

try:
    connection = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET)
    bucket = connection.get_bucket(BUCKET_NAME)
    print(f"Downloading from {BUCKET_NAME}")
    key_obj = bucket.get_key(BACKUP_FILE_BUCKET_KEY)
    if key_obj is not None:
        key_obj.get_contents_to_filename(BACKUP_FILE_BUCKET_KEY)
        print(f"Successfully downloaded {BACKUP_FILE_BUCKET_KEY}")
    else:
        print(f"Couldn't download the backup file with key '{BACKUP_FILE_BUCKET_KEY}'\nERROR: No such key in the bucket {BUCKET_NAME}")
        exit(1)
except Exception as e:
    print(f"Couldn't download the backup file with key '{BACKUP_FILE_BUCKET_KEY}' in bucket {BUCKET_NAME}")
    exit(1)

# Read file
backup_file = None
with open(BACKUP_FILE_BUCKET_KEY, 'rb') as bk:
    backup_file = io.BytesIO(bk.read())
if backup_file is None:
    print(f"Couldn't read the file {BACKUP_FILE_BUCKET_KEY}")
    exit(1)

# Perform restore
backup_timeout = odoo.config.get('timeout', 600)
odoo.config['timeout'] = 1800
print(f"Creating a database named {NEW_DATABASE_NAME} using the AWS S3 object with key {BACKUP_FILE_BUCKET_KEY}...")
odoo_db.restore(MASTER_PASSWD, NEW_DATABASE_NAME, backup_file, True)
print(f"* Done *")
odoo.config['timeout'] = backup_timeout

# Clean up the backup file
# Comment out the block below if the backup file needs a copy on the local machine
if os.path.isfile(BACKUP_FILE_BUCKET_KEY):
    os.remove(BACKUP_FILE_BUCKET_KEY)
    print(f"Successfully cleaned up the backup file")
else:
    print(f"ERROR: {BACKUP_FILE_BUCKET_KEY} file not found")
