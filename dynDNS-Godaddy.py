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
-fill in your API and secret keys given to you by GoDaddy.com
-fill in all relevant information about your external domain
   (the one being hosted by GoDaddy.com)
-fill in your email address so you can get notified if there's a failure

'''

import os
import requests
import json
import psutil
import socket
import time


#
# User-entered variables
#

# DNS and user info (please enter your info here)
api_key = 'API_KEY_HERE'
api_secret = 'API_SECRET_HERE'

dns_domain = 'example-domain.com'
dns_type = 'A'
dns_name = 'subdomain-here'
dns_ttl = 3600

notify_email = 'NOTIFY_EMAIL_HERE'


#
# Derived variables, and constants
#

headers = {'Authorization' : 'sso-key ' + api_key + ':' + api_secret, 'Content-Type' : 'application/json'}
base_checkip_url = 'https://icanhazip.com'
base_godaddy_url = 'https://api.godaddy.com'

#
# Function definitions
#

def get_current_ip():
    '''
    This function will return the current external IP.
    '''
    response = requests.get(base_checkip_url)
    if response.status_code == 200:
        return response.text.strip('\n')
    else:
        return None


def get_dns_ip():
    '''
    This function will return the current IP set in the 'subdomain-here' record.
    '''
    dns_ip_cur = socket.gethostbyname(dns_name + '.' + dns_domain)
    return dns_ip_cur


def update_dns_ip(current_ip, dns_ip):
    '''
    This function will update the DNS 'subdomain-here' record with the current
       external IP.
    '''
    url = base_godaddy_url + '/v1/domains/' + dns_domain + '/records/' \
        + dns_type + '/' + dns_name
    dns_json = [{'data':current_ip, 'name':dns_name, 'ttl':dns_ttl}]
    response = requests.put(url, data = json.dumps(dns_json), headers = headers)


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

    c = 0
    if dns_ttl > 29:
        if dns_ttl > 3600:
            retries = 360
        else:
            retries = dns_ttl // 10
    else:
        retries = 2
    for n in range(retries):
        if get_dns_ip() != current_ip:
            time.sleep(10)
        else:
            quit()

    msg = '''echo "An IP address appears to have changed, but there was an issue with updating it. The new IP address appears to be {c}. Thank you." | mail -s "DDNS Error" {n}'''.format(c = current_ip, n = notify_email)
    os.system(msg)


#
# Main
#

if __name__ == "__main__":
    main()
