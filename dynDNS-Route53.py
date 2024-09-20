#! /usr/bin/env python3
'''
Description of this script:

-check whether the current external address matches the DNS address
   -if so, quit
   -if not, proceed
-check whether there is already one of these processes running
   -if so, quit
   -if not, proceed
-update the specified DNS record to match the current external address
-in timeframes relevant to the TTL, check to see if it's been updated
   -if so, quit
   -if not, check again until TTL has been reached, then notify via email

User Instructions:
-clone the repo locally
-copy the config-sample.ini file to a file named config.ini
-fill in the config.ini file with your info incl. AWS credentials
    -NOTE: "config.ini" is in the .gitignore so it won't be pushed with any repo changes,
        but "config-sample.ini" will
-you also have the option to create these as environment variables and skip using config.ini
'''

import os
import requests
import json
import psutil
import socket
import time
import configparser
import boto3


#
# Setup
#

configs_dict = {}
script_cwd = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_cwd)

#
# Function definitions
#

def load_config():
        if os.path.exists('config.ini'):
            config = configparser.ConfigParser()
            config.read('config.ini')
            configs_dict['domain'] = config['DEFAULT']['DOMAIN']
            configs_dict['aws_hosted_zone_id'] = config['DEFAULT']['AWS_HOSTED_ZONE_ID']
            configs_dict['aws_access_key_id'] = config['DEFAULT']['AWS_ACCESS_KEY_ID']
            configs_dict['aws_secret_access_key'] = config['DEFAULT']['AWS_ACCESS_SECRET_KEY']
            configs_dict['check_url'] = config['DEFAULT']['CHECK_URL']
            configs_dict['notify_email'] = config['DEFAULT']['NOTIFY_EMAIL']
        else:
            configs_dict['domain'] = os.environ['DOMAIN']
            configs_dict['aws_hosted_zone_id'] = os.environ['AWS_HOSTED_ZONE_ID']
            configs_dict['aws_access_key_id'] = os.environ['AWS_ACCESS_KEY_ID']
            configs_dict['aws_secret_access_key'] = os.environ['AWS_ACCESS_SECRET_KEY']
            configs_dict['check_url'] = os.environ['CHECK_URL']
            configs_dict['NOTIFY_EMAIL'] = os.environ['NOTIFY_EMAIL']


def get_current_ip():
    '''
    This function will return the current external IP.
    '''
    response = requests.get(configs_dict['check_url'])
    if response.status_code == 200:
        return response.text.strip('\n')
    else:
        return None


def get_dns_ip():
    '''
    This function will return the current IP set in the 'home' record.
    '''
    return socket.gethostbyname(configs_dict['domain'])


def update_dns_ip(current_ip, dns_ip):
    '''
    This function will update the DNS 'home' record with the current
       external IP.
    '''

    domain = configs_dict['domain']
    aws_hosted_zone_id = configs_dict['aws_hosted_zone_id']
    aws_access_key_id = configs_dict['aws_access_key_id']
    aws_access_secret_key = configs_dict['aws_secret_access_key']

    client = boto3.client('route53',
                            aws_access_key_id=aws_access_key_id,
                            aws_secret_access_key=aws_access_secret_key)

    client.change_resource_record_sets(
        HostedZoneId=aws_hosted_zone_id,
        ChangeBatch={
            'Comment': 'string',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': domain,
                        'Type': 'A',
                        'TTL': 60,
                        'ResourceRecords': [
                            {
                                'Value': current_ip
                            }
                        ]
                    }
                }
            ]
        }
    )

def is_proc_running(name):
    '''
    This function returns True if there is another update process
       already running, and false if there's not.
    '''

    procs = []
    for p in psutil.process_iter(attrs=['cmdline']):
        for subname in p.info['cmdline']:
            if name in subname:
                procs.append(p)
            if len(procs) > 1:
                return True

    return False

def main():
    load_config()
    
    current_ip = get_current_ip()
    #print("current ip is", current_ip) # debug
    
    dns_ip = get_dns_ip()
    #print("DNS ip is", dns_ip) # debug

    current_process_name = os.path.basename(__file__)
    #print("current process name is", current_process_name) # debug

    if current_ip == dns_ip:
        quit()

    if is_proc_running(current_process_name):
        quit()

    update_dns_ip(current_ip, dns_ip)

    dns_check_timeout = 3600 # may be adjusted

    if dns_check_timeout > 29:
        if dns_check_timeout > 3600:
            retries = 360
        else:
            retries = dns_check_timeout // 10
    else:
        retries = 2
    for n in range(retries):
        if get_dns_ip() != current_ip:
            time.sleep(10)
        else:
            quit()
    #print("at the end, and vars are", get_dns_ip(), current_ip) # debug
    msg = '''echo "An IP address appears to have changed, but there was an issue with updating it. The new IP address appears to be {c}. Thank you." | mail -s "DDNS Error" {n}'''.format(c = current_ip, n = configs_dict[notify_email])
    os.system(msg)


#
# Run
#

if __name__ == "__main__":
    main()
