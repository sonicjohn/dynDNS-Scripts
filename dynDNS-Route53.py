#! /usr/bin/env /bin/python3.14
# boto3 requires a recent version of python 3
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
import shutil
from datetime import datetime
import requests
import subprocess
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
            configs_dict['notify_email'] = os.environ['NOTIFY_EMAIL']

def get_current_ip():
    '''
    This function will return the current external IP.
    '''
    try:
        response = requests.get(configs_dict['check_url'], timeout=15)
    except requests.RequestException:
        return None
    if response.status_code == 200:
        return response.text.strip('\n')
    return None

def get_dns_ip():
    '''
    This function will return the current IP set in the 'home' record.
    '''
    try:
        return socket.gethostbyname(configs_dict['domain'])
    except socket.gaierror:
        return None

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
            if len(procs) > 2: # 2 if running via cron, 1 otherwise
                return True

    return False

def find_sendmail():
    '''Return the path to a sendmail binary, or None if not found.'''
    found = shutil.which('sendmail')
    if found:
        return found
    for path in ('/usr/sbin/sendmail', '/usr/lib/sendmail'):
        if os.access(path, os.X_OK):
            return path
    return None

def notify_by_mail(subject, body):
    '''Send a notification email if a sendmail binary exists. Returns True if handed off.'''
    sendmail = find_sendmail()
    if sendmail is None:
        return False

    recipient = configs_dict['notify_email']
    message = 'To: {r}\nSubject: {s}\n\n{b}\n'.format(r=recipient, s=subject, b=body)

    try:
        subprocess.run(
            [sendmail, '-t'],
            input=message.encode(),
            check=True,
            timeout=30
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False

def main():
    load_config()
    
    current_ip = get_current_ip()
    #print("current ip is", current_ip) # debug
    
    if current_ip is None:
        print('{t}: Could not determine external IP; skipping this run.'.format(
            t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        quit()
    
    dns_ip = get_dns_ip()
    #print("DNS ip is", dns_ip) # debug

    current_process_name = os.path.basename(__file__)
    #print("current process name is", current_process_name) # debug

    if current_ip == dns_ip:
        # Stdout is designed to be redirected to a log file here.
        print('{t}: No change detected; IP is still {c}.'.format(
            t=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), c=current_ip))
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
    updated = False
    for n in range(retries):
        if get_dns_ip() != current_ip:
            time.sleep(10)
        else:
            updated = True
            break
    if updated:
        body = ('The external IP address changed from {o} to {c}, and the '
                'DNS record was updated successfully.'.format(o=dns_ip, c=current_ip))
        if not notify_by_mail('DDNS Updated: {d}'.format(d=configs_dict['domain']), body):
            print('IP changed to', current_ip, 'and DNS was updated; no mail client available to notify.')
    else:
        body = ('An IP address appears to have changed, but there was an issue '
                'with updating it. The old address was {o}, and the new IP '
                'address appears to be {c}. Thank you.'.format(o=dns_ip, c=current_ip))
        if not notify_by_mail('DDNS Error: {d}'.format(d=configs_dict['domain']), body):
            print('DDNS update failed and no mail client available; new IP is', current_ip)

#
# Run
#

if __name__ == "__main__":
    main()
