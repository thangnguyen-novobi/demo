"""
Instructions:
1) Set the Odoo server parameters
2) Set the AWS S3 connection parameters
3) Change the backup file naming convention @line82 (optional)
4) Finesse!
Note: Sensitive data such as password and AWS credentials can be populated via environment variables.
"""
import os
import pip
import time

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
DB_TO_BACKUP_AND_PUSH = "<The database to be backed up>"


#####################
# AWS S3 parameters #
#####################
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', "<AWS Access Key ID in Security Credentials>")
AWS_ACCESS_KEY_SECRET = os.environ.get('AWS_ACCESS_KEY_SECRET', "<AWS Access Key Secret in Security Credentials>")
BUCKET_NAME = "<Bucket's name to write the backup file into>"


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


if any(not x for x in [PORT, HOST_NAME, MASTER_PASSWD, DB_TO_BACKUP_AND_PUSH, AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET, BUCKET_NAME]):
    print("Missing one or more required parameter settings")
    exit(1)

# Connect to the Odoo server
odoo = connect_odoorpc()
odoo_db = odoo.db

# Perform backup
backup_timeout = odoo.config.get('timeout', 600)
odoo.config['timeout'] = 1500
dump = odoo_db.dump(MASTER_PASSWD, DB_TO_BACKUP_AND_PUSH)
odoo.config['timeout'] = backup_timeout
if not dump:
    print(f"- ERROR: Couldn't get the database {DB_TO_BACKUP_AND_PUSH}'s backup from {HOST_NAME}:{PORT}")
    exit(1)

# Write backup
filename = f'{DB_TO_BACKUP_AND_PUSH}_backup_{time.strftime("%Y%m%d-%H%M%S")}.zip'
with open(filename, 'wb') as zip_file:
    zip_file.write(dump.read())

try:
    connection = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET)
    bucket = connection.get_bucket(BUCKET_NAME)
    print(f"Writing to {BUCKET_NAME}")
    key_obj = boto.s3.key.Key(bucket)
    key_obj.key = filename
    key_obj.set_contents_from_filename(filename, num_cb=10)
    print(f"Successfully uploaded {filename} into bucket {BUCKET_NAME}")
except Exception as e:
    print(f"Couldn't upload the backup file to AWS S3 Bucket - {BUCKET_NAME}")
    exit(1)

# Clean up the backup file
# Comment out the block below if the backup file needs a copy on the local machine
if os.path.isfile(filename):
    os.remove(filename)
    print(f"Successfully cleaned up the backup file")
else:
    print(f"Error: {filename} file not found")
