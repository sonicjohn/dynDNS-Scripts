# DynDNS Python Scripts

## Description
This is a simple script which detects a change in the WAN IP and updates a DNS record. The need for this arose when I was travelling and needed to access my services at home via a subdomain which always reflects my home IP address. It's not intended for use in enterprise production environments.

This is implemented using a single small script for simplicity. There is a version for GoDaddy and one for Route53. Since GoDaddy has disabled their DNS API for non-enterprise users, the script was re-written for AWS Route53. It's easy enough to delegate Route53 as authoritative for GoDaddy-managed domains, and AWS readily accepts requests via the boto library.

```
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
```

## To install
Place script on an internal Linux server and adjust values as follows:

```
-clone the repo locally
-copy the config-sample.ini file to a file named config.ini
-fill in the config.ini file with your info incl. AWS credentials
    -NOTE: "config.ini" is in the .gitignore so it won't be pushed with any repo changes,
        but "config-sample.ini" will
    -NOTE: for the GoDaddy version, update the values directly in the script
-you also have the option to create these as environment variables and skip using config.ini (Route53 version only)
```

## To run
Keep this script on a cron job running every few hours or so. For my use case an immediate change was not necessary-- it's just so I don't get locked out of my home network for not knowing the IP address.

\* */3 * * * /\<path to project\>/dynDNS-Scripts/dynDNS-Route53.py > /dev/null 2>&1

TODO: Create better support and error handling for environment variables