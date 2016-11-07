#!/usr/bin/env python

"""
Simple script to manage eDir users via LDAP. 
It relies on external OES server scripts 
for user home, shared directory and quota
provisioning.

Usage: 
    python edir.py -f input.json -o output.csv

Options:
    -h --help
    -f --file	Input file (required)
    -o --out	Output file (required)

Environment specific script constants are stored in this 
config file: settings.py
    
Input:

Input file is expected to be in JSON format (e.g. input.json).
with these 16 required data fields:
{
    "useractions": [
        {
            "action": "create",
            "username": "testuserj",
            "newusername": "testuserj",
            "loginDisabled": "False",
            "uidNumber": 15549,
            "gidNumber": 15549,
            "givenName": "John",
            "fullName": "John The Testuser",
            "sn": "Testuser",
            "employeeType": "ADM",
            "DNumber": "D01234567",
            "x500UniqueIdentifier": "44EFB5C72-1EB5-1036-96C4-C572BEDBFG4G",
            "primO": "Biology",
            "businessCategory": "Aruba-User-Role = \"staff\"",
            "userPassword": "initial password",
            "description": "Create on this date or any note"
        }
    ] 
}
where action can be create/update/archive/delete and newusername is same old 
one or a new value if renaming the user.

Output:

Output file (e.g. output.csv) will have these fields:

action, username, result (ERROR/SUCCESS: reason)

Logging:

Script creates a detailed edir.log

All errors are also printed to stdout.

Author: A. Ablovatski
Email: ablovatskia@denison.edu
Date: 10/31/2016
"""

from __future__ import print_function
import time
import sys
import json
import csv
import argparse
import logging
import ldap
import ldap.modlist as modlist
import urllib
import textwrap
import smtplib
import base64

def main(argv):
    """This is the main body of the script"""
    
    # Setup the log file
    logging.basicConfig(
        filename='edir.log',level=logging.DEBUG, 
        format='%(asctime)s, %(levelname)s: %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S')

    # Get LDAP creds and other constants from this settings file
    config_file = 'settings.py'
    
    if not readConfig(config_file):
        logging.error("unable to parse the settings file")
        sys.exit()
    
    # Parse script arguments
    parser = argparse.ArgumentParser()                                               

    parser.add_argument("--file", "-f", type=str, required=True, 
                        help="Input JSON file with user actions and params")
    parser.add_argument("--out", "-o", type=str, required=True, 
                        help="Output file with results of eDir user actions")

    try:
        args = parser.parse_args()
        
    except SystemExit:
        logging.error("required arguments missing - " \
                        "provide input and output file names")
        sys.exit()

    # Read input from json file
    in_file = args.file
    # Write output to csv file
    out_file = args.out
    
    try:
        f_in = open(in_file, 'rb')
        logging.info("opened file: {0}".format(in_file))
        f_out = open(out_file, 'wb')
        logging.info("opened file: {0}".format(out_file))
        reader = json.load(f_in)
        writer = csv.writer(f_out)
        writer.writerow( ['action','username','result'] )
        
        for row in reader["useractions"]:
            result = ''
            # Select what needs to be done
            if row["action"] == 'create':
                result = create(str(row["username"]), str(row["loginDisabled"]), 
                                str(row["uidNumber"]), str(row["gidNumber"]), 
                                str(row["givenName"]), str(row["fullName"]), 
                                str(row["sn"]), str(row["employeeType"]), 
                                str(row["DNumber"]), 
                                str(row["x500UniqueIdentifier"]), 
                                str(row["primO"]), str(row["businessCategory"]), 
                                str(row["userPassword"]), str(row["description"]))
            elif row["action"] == 'update':
                result = update(str(row["username"]), str(row["newusername"]), 
                                str(row["loginDisabled"]), str(row["uidNumber"]), 
                                str(row["gidNumber"]), str(row["givenName"]), 
                                str(row["fullName"]), str(row["sn"]), 
                                str(row["employeeType"]), str(row["DNumber"]), 
                                str(row["x500UniqueIdentifier"]), 
                                str(row["primO"]), str(row["businessCategory"]), 
                                str(row["description"]))
            elif row["action"] == 'delete':
                 result = delete(str(row["username"]))
            elif row["action"] == 'archive':
                 result = archive(str(row["username"]))
            else:
                print("ERROR: unrecognized action")                
                logging.error("unrecognized action")
                result = "ERROR: Unrecognized action"
            
            # Write the result to the output csv file
            writer.writerow( [row["action"], row["username"], result] )
            
    except IOError:
        print("ERROR: Unable to open input/output file!")
        logging.critical("file not found: {0} or {1}".format(in_file, out_file))
        
    except Exception as e:
        print("ERROR: unknown error while attempting to read/write to file: " \
                "{0}".format(e))
        logging.critical("unknown error while attempting to read/write to " \
                "file".format(e))
        
    finally:
        f_in.close()
        logging.info("closed file: {0}".format(in_file))
        f_out.close()
        logging.info("closed file: {0}".format(out_file))
        
    return

def create(username, loginDisabled, uidNumber, gidNumber, givenName, fullName, 
            sn, employeeType, dNumber, x500UniqueIdentifier, ou, 
            businessCategory, userPassword, description):
    """This funtions adds users to eDir"""
    
    # Check if any of the parameters are missing
    params = locals()
    
    for _item in params:
        if str(params[_item]) == "":
            print("ERROR: unable to create user {0} because {1} is missing " \
                    "a value".format(username, _item))
            logging.error("unable to create user {0} because {1} is missing " \
                            "a value".format(username, _item))
            result = "ERROR: Missing an expected input value for " + _item \
                        + " in input file"
            return result

    # We have all we need, connect to LDAP
    l = ldapConnect()
    
    # Catch LDAP connection failure
    if not l:
        result = "ERROR: unable to connect to LDAP server"
        return result
        
    # Do a quick check if the user already exists
    if findUser(l, username):
        print("ERROR: cannot create user - user already exists: {0}" \
                .format(username))
        logging.error("cannot create user - user already exists: {0}" \
                .format(username))
        result = "ERROR: username already taken!"
        return result
        
    # Create new user if it does not exist
    try:
        # Get the dn of our new user
        dn = buildDN(username)
        
        # Set server and groups variables
        userType = getUserType(username)
        groups = []
        if userType == "STU":
            server = STUSERVER
            gdn = "cn=" + StuGeneralMacUsers + GeneralMacUsersOU
            groups = [gdn]
        elif userType == "GST":
            gdn = "cn=" + GuestGeneralMacUsers + GeneralMacUsersOU
            groups = [gdn]
        else:
            server = EMPSERVER
            gdn = "cn=" + EmpGeneralMacUsers + GeneralMacUsersOU
            groups = [gdn]
            gdn1 = "cn=" + EmpGeneralWSUsers + GeneralMacUsersOU
            groups = groups + [gdn1]
            # Find user's department group and add it here
            deptGroup = lookupGroup(ou)
            if deptGroup:
                groups = groups + [deptGroup]
            else:
                logging.warning("unable to find departmental group for " /
                                    "the user {0}".format(username))
                        
        # Note: we are not setting Login Shell attrib 
        # to /bin/bash as described in Linux Profile doc
        
        # Build a dict for the "body" of the user object
        attrs = {}
        attrs['objectclass'] = ['top','person','organizationalPerson',
                                'inetOrgPerson','ndsLoginProperties',
                                'posixAccount']
        attrs['cn'] = username
        attrs['userPassword'] = userPassword
        attrs['description'] = description
        attrs['loginDisabled'] = loginDisabled
        attrs['givenName'] = givenName
        attrs['fullName'] = fullName
        attrs['sn'] = sn
        attrs['uid'] = username
        attrs['mail'] = username + MAILDOMAIN
        attrs['uidNumber'] = uidNumber
        attrs['gidNumber'] = gidNumber
        attrs['homeDirectory'] = "/Users/" + username
        attrs['employeeType'] = employeeType
        attrs['employeeNumber'] = dNumber[1:]
        attrs['telexNumber'] = dNumber
        attrs['ou'] = ou
        attrs['x500UniqueIdentifier'] = x500UniqueIdentifier
        attrs['businessCategory'] = businessCategory
        if server:
            attrs['ndsHomeDirectory'] = "cn=" + server + SHAREOU + "#0#" \
                                        + username
        attrs['Language'] = "ENGLISH"
        attrs['passwordUniqueRequired'] = "TRUE"
        attrs['passwordRequired'] = "TRUE"
        attrs['passwordMinimumLength'] = "5"
        attrs['passwordAllowChange'] = "TRUE"
        attrs['loginGraceRemaining'] = "3"
        attrs['loginGraceLimit'] = "3"

        # Convert our dict to proper syntax using modlist module
        ldif = modlist.addModlist(attrs)

        # Do the actual synchronous add to the ldapserver
        l.add_s(dn,ldif)
        
        # Log user creation
        logging.info("user added to eDir: {0} - now updating groups" \
                        .format(username))
        print("SUCCESS: User {0} added to eDir, now updating groups." \
                        .format(username))
        
        # Wait 20s untill all replicas are fully sync'd if needed
        # time.sleep(20)
        
        # Could use findUser(l, username) here
        # to verify that the user exists
        
        # Add user to GeneralMacUsers groups (and DeptGroup if exists)
        for group in groups:
            # First update the user
            mod_attrs = [( ldap.MOD_ADD, 'securityEquals', group ), 
                        ( ldap.MOD_ADD, 'groupMembership', group )]
            l.modify_s(dn, mod_attrs)
            # and and modify the group
            addMember(l, group, dn)
        
        logging.info("user {0} added to the eDir groups - now adding " \
                        "memberUid hack".format(username))
        
        # Add the username to memberUid attrib of GeneralMacUsers group
        # to support the dirty hack for Mac logins!!!
        mod_attrs = [( ldap.MOD_ADD, 'memberUid', username )]
        l.modify_s(gdn, mod_attrs)
        logging.info("user {0} added to memberUid attrib of eDir group {1} " \
                        "- remove later".format(username, gdn))
        
        # Its nice to the server to disconnect
        l.unbind_s()
        
    except ldap.LDAPError, e:
        print("ERROR: Could not add user to eDir or update groups for: " \
                    "{0}".format(e))
        logging.error("eDir add or group update failed for user: " \
                    "{0}".format(username))
        result = "ERROR: Could not create eDir user or update groups"
        return result
    
    try:
        # Make HTTP requests to create homes/LAN/quotas
        # Exclude quest accounts from space creation
        if userType == "STU":
            response = urllib.urlopen(
            "http://studentserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username)
            code = response.getcode()
            logging.info("request status for studentserver: {0}".format(code))
            
            response = urllib.urlopen(
            "http://fileserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username)
            code = response.getcode()
            logging.info("request status for fileserver: {0}".format(code))
            
            response = urllib.urlopen(
            "http://mediaserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username)
            code = response.getcode()
            logging.info("request status for mediaserver: {0}".format(code))
            
        elif userType == "GST":
            logging.info("not requesting any space for the guest user: {0}" \
                            .format(username))
        else:
            response = urllib.urlopen(
            "http://empserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username)
            code = response.getcode()
            logging.info("request status for empserver: {0}".format(code))
            
            response = urllib.urlopen(
            "http://fileserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username + ":" + ou)
            code = response.getcode()
            logging.info("request status for fileserver: {0}".format(code))
            
            response = urllib.urlopen(
            "http://mediaserver.domain.edu/cgi-bin/getspace.pl?username=" 
            + username)
            code = response.getcode()
            logging.info("request status for mediaserver: {0}".format(code))
    
    except Exception as e:
            print("ERROR: unknown error while requesting user storage: {0}" \
                    .format(e))
            logging.error("unknown error while requesting user storage")
            result = "ERROR: Could not provision storage for the user"
    
    print("SUCCESS: user added to eDir and groups plus space requested" \
            .format(dn))
    logging.info("user {0} was added to eDir and groups plus space requested" \
            .format(dn))
    result = "SUCCESS: User added to eDir"
    
    return result
    
def update(username, newusername, loginDisabled, uidNumber, gidNumber, 
            givenName, fullName, sn, employeeType, dNumber, 
            x500UniqueIdentifier, ou, businessCategory, description):
    """This function updates user attributes 
    and renames users if needed"""
    
    # Note: on ou update, eDir departmental groups are not updated!
    
    # Check if any of the arguments are missing
    params = locals()
    
    for _item in params:
        if str(params[_item]) == "":
            print("ERROR: unable to update user {0} because {1} is missing " \
                    "a value".format(username, _item))
            logging.error("unable to update user {0} because {1} is missing " \
                            "a value".format(username, _item))
            result = "ERROR: Missing an expected input value for " \
                        + _item + " in input file"
            return result

    # We have all we need, connect to LDAP
    l = ldapConnect()
    
    # Catch the condition when LDAP connection failed
    if not l:
        result = "ERROR: unable to connect to LDAP server"
        return result
    
    # Do a quick check if the user exists
    if not findUser(l, username):
        print("ERROR: user does not exist: {0}".format(username))
        logging.error("user does not exist: {0}".format(username))
        result = "ERROR: user could not be found!"
        return result
    
    # rename if new username is diferent
    if username != newusername:
        # First check if both usernames are in the same OU
        userType = getUserType(username)
        
        if userType != getUserType(newusername):
            print("ERROR: unable to rename user {0} to {1} because " \
                    "they are of different type".format(username, newusername))
            logging.error("unable to rename user {0} to {1} because " \
                    "they are of different type".format(username, newusername))
            result = "ERROR: can't rename users across different OUs"
            return result

        # Rename the user
        try:
            # Get the dn of our old user
            dn = buildDN(username)
            
            # Check if the new user name already exists
            if findUser(l, newusername):
                print("ERROR: cannot rename user - user already exists: {0}" \
                        .format(newusername))
                logging.error("cannot rename user - user already exists: {0}" \
                                .format(newusername))
                result = "ERROR: username already taken!"
                return result
            
            # you can safely ignore the results returned as an exception 
            # will be raised if the rename doesn't work.
            l.rename_s(dn, 'cn=' + newusername)
            
            logging.info("user {0} renamed to {1} in eDir" \
                            .format(username, newusername))
            
            # Update old memeberUID attribute in *GeneralMac_Users Group          
            if userType == "STU":
                gn = StuGeneralMacUsers
            elif userType == "GST":
                gn = GuestGeneralMacUsers
            else:
                gn = EmpGeneralMacUsers
            
            gdn = "cn=" + gn + GeneralMacUsersOU
            
            # Add new username to memberUid attrib of GeneralMacUsers group
            mod_attrs = [( ldap.MOD_ADD, 'memberUid', newusername )]
            l.modify_s(gdn, mod_attrs)
            logging.info("user {0} added to memberUid attrib of eDir group " \
                            "{1} - remove later!!!".format(newusername, gdn))
            
            # Find and delete the old memberUid attribute value
            delMemberUid(l, gn, gdn, username)
   
        except ldap.LDAPError, e:
            print("ERROR: Could not rename user or update GeneralMac_Users " \
                    "group in eDir: {0}".format(e))
            logging.error("eDir rename failed from: {0} to {1} or update of " \
                   "GeneralMac_Users group failed".format(username, newusername))
            result = "ERROR: Could not rename eDir user"
            return result
            
        except Exception as e:
            print("ERROR: unknown error while renaming user: {0}".format(e))
            logging.error("unknown error while attempting to rename user")
            result = "ERROR: Could not rename eDir user"
            
        print("INFO: user {0} renamed to {1} in eDir" \
                .format(username, newusername))
        logging.info("user {0} fully renamed to {1} in eDir" \
                        .format(username, newusername))
        
        # Send an email to the operator re: outstanding
        # renames of home, shared folders and eDir homeDir attribute
        frm = FROM
        to = TO
        subject = "eDir user renamed: " + dn + " to " + newusername
        text = "Need to rename home and other shared folders, " \
                "as well as ndsHomeDirectory attribute!"
                
        sendMail(frm, to, subject, text)
        logging.info("emailed {0} about user folder re-naming".format(to))
                
    # Rename or not, update attributes or disable
    try:
        # The dn of our user to update
        dn = buildDN(newusername) 
        
        # Can't just replace multiple businessCategory attribute values
        # with ( ldap.MOD_REPLACE, 'businessCategory', businessCategory )
        # bc all the businessCategory values will be deleted and replaced
        # with this one. First delete the exisitng
        # Aruba-User-Role value(s), and replace with the new one.
        searchScope = ldap.SCOPE_SUBTREE
        searchFilter = "cn=" + newusername
        ldap_result = l.search_s(baseDN, searchScope, searchFilter, 
                                    ['businessCategory'])
        
        for value in ldap_result[0][1]['businessCategory']:
            if ARUBAPATTERN in value:
                mod_attrs = [ ( ldap.MOD_DELETE, 'businessCategory', value ) ]
                l.modify_s(dn, mod_attrs)
 
        # Build the list of modifications
        # We do not reset passwords here!
        mod_attrs = [
            ( ldap.MOD_REPLACE, 'description', description ),
            ( ldap.MOD_REPLACE, 'loginDisabled', loginDisabled ),
            ( ldap.MOD_REPLACE, 'givenName', givenName ),
            ( ldap.MOD_REPLACE, 'fullName', fullName ),
            ( ldap.MOD_REPLACE, 'sn', sn ),
            ( ldap.MOD_REPLACE, 'uid', newusername ),
            ( ldap.MOD_REPLACE, 'mail', newusername + MAILDOMAIN ),
            ( ldap.MOD_REPLACE, 'uidNumber', uidNumber ),
            ( ldap.MOD_REPLACE, 'gidNumber', gidNumber ),
            ( ldap.MOD_REPLACE, 'homeDirectory', "/Users/" + newusername ),
            ( ldap.MOD_REPLACE, 'employeeType', employeeType ),
            ( ldap.MOD_REPLACE, 'employeeNumber', dNumber[1:] ),
            ( ldap.MOD_REPLACE, 'telexNumber', dNumber ),
            ( ldap.MOD_REPLACE, 'ou', ou ),
            ( ldap.MOD_REPLACE, 'x500UniqueIdentifier', x500UniqueIdentifier ),
            ( ldap.MOD_ADD, 'businessCategory', businessCategory )
        ]
        
        # Do the actual modifications
        l.modify_s(dn, mod_attrs)

        # Its nice to the server to disconnect when done
        l.unbind_s()
        
    except ldap.LDAPError, e:
        print("ERROR: Could not update user in eDir: {0}".format(e))
        logging.error("eDir update failed for: {0}".format(username))
        result = "ERROR: Could not update eDir user"
        return result
    
    except Exception as e:
        print("ERROR: unknown error while updating user: {0}".format(e))
        logging.error("unknown error while updating user")
        result = "ERROR: Could not update eDir user"
            
    print("SUCCESS: user {0} updated in eDir".format(newusername))
    logging.info("User {0} updated eDir".format(dn))
    result = "SUCCESS: User updated in eDir"
    
    return result
    
def archive(username):
    """This functions moves a
    DISABLED user to _Archive OU"""
    
    # Check if the argument is missing
    if str(username) == "":
        print("ERROR: unable to archive user because username argument " \
                "is missing a value")
        logging.error("unable to archive user because username argument " \
                        "is missing a value")
        result = "ERROR: Missing an expected input value for username " \
                    "in input file"
        return result
            
    # We have all we need, connect to LDAP
    l = ldapConnect()
    
    # Catch the condition when LDAP connection failed
    if not l:
        result = "ERROR: unable to connect to LDAP server"
        return result
    
    # Do a quick check if the user exists
    if not findUser(l, username):
        print("ERROR: user does not exist: {0}".format(username))
        logging.error("user does not exist: {0}".format(username))
        result = "ERROR: user could not be found!"
        return result
    
    # Is the user disabled?
    if not userDisabled(l, username):
        print("ERROR: user is not disabled: {0}".format(username))
        logging.error("user is not disabled: {0}".format(username))
        result = "ERROR: user is not disabled!"
        return result
        
    # Archive the user if all is OK
    try:
        dn = buildDN(username)
        # Set the archival container for our user
        userType = getUserType(username)
        
        if userType == "STU":
            container_new = "ou=_Archive" + STUDENTOU
        elif userType == "GST":
            result = "ERROR: we do not archive guest accounts"
            return result
        else:
            container_new = "ou=_Archive" + EMPOU
            
        l.rename_s(dn, 'cn=' + username, container_new)
        
        # Its nice to the server to disconnect when done
        l.unbind_s()
        
    except ldap.LDAPError, e:
        print("ERROR: Could move user in eDir: {0}".format(e))
        logging.error("eDir move failed for user {0}".format(username))
        result = "ERROR: Could not move eDir user"
        return result
        
    print("SUCCESS: user {0} archived in eDir".format(username))
    logging.info("user {0} archived in eDir".format(dn))
    result = "SUCCESS: User archived in eDir"
    
    return result
    
def delete(username):
    """This function deletes 
    a DISABLED user from eDir"""
    
    # Note that script only deletes users from Employee/Studetn/Visitor OUs
    # It does not delete them from _Archive OUs
    
    # Check if the argument is missing
    if str(username) == "":
        print("ERROR: unable to delete user because username argument " \
                "is missing a value")
        logging.error("unable to delete user because username argument " \
                        "is missing a value")
        result = "ERROR: Missing an expected input value for username " \
                    "in input file"
        return result
            
    # We have all we need, connect to LDAP
    l = ldapConnect()
        
    # Catch the condition when LDAP connection failed
    if not l:
        result = "ERROR: unable to connect to LDAP server"
        return result
    
    # Do a quick check if the user exists
    if not findUser(l, username):
        print("ERROR: user does not exist: {0}".format(username))
        logging.error("user does not exist: {0}".format(username))
        result = "ERROR: user could not be found!"
        return result
    
    # Is the user disabled?
    if not userDisabled(l, username):
        print("ERROR: user is not disabled: {0}".format(username))
        logging.error("user is not disabled: {0}".format(username))
        result = "ERROR: user is not disabled!"
        return result
        
    # Delete the user if all is OK
    try:
        # Get the dn of our user
        dn = buildDN(username)
        
        l.delete_s(dn)
        logging.info("user {0} deleted from eDir".format(dn))
        
        # Delete old memeberUid attribute from correct GeneralMac_Users Group       
        userType = getUserType(username)
        
        if userType == "STU":
            gn = StuGeneralMacUsers
        elif userType == "GST":
            gn = GuestGeneralMacUsers
        else:
            gn = EmpGeneralMacUsers

        gdn = "cn=" + gn + GeneralMacUsersOU

        # Find and delete the old memberUid attribute value
        delMemberUid(l, gn, gdn, username)
        
        # Its nice to the server to disconnect when done
        l.unbind_s()
        
    except ldap.LDAPError, e:
        print("ERROR: Could not delete user in eDir: {0}".format(e))
        logging.error("eDir delete failed for {0}".format(dn))
        result = "ERROR: Could not delete eDir user"
        return result

    except Exception as e:
        print("ERROR: unknown error while deleting user: {0}".format(e))
        logging.error("unknown error while deleting user")
        result = "ERROR: Could not delete eDir user"
        
    print("SUCCESS: user {0} deleted from eDir".format(username))
    logging.info("user {0} fully deleted from eDir".format(dn))
    result = "SUCCESS: User deleted from eDir"
    
    # Send an email to the operator about 
    # needing to deprov home, LAN folders, S and M folders
    frm = FROM
    to = TO
    subject = "eDir user deleted: " + dn
    text = "Need to deprovision home and other shared folders!"
    
    sendMail(frm, to, subject, text)
    logging.info("sent an email to {0} about user files deprovisioning" \
                    .format(to))
    
    return result

def readConfig(config_file):
    """Function to import the config file"""
    
    if config_file[-3:] == ".py":
        config_file = config_file[:-3]
    settings = __import__(config_file, globals(), locals(), [])
    
    # Read settings and set globals
    try: 
        global LDAPSERVER
        global USER
        global PASSWORD
        global baseDN
        global MAILDOMAIN
        global STUPATTERN
        global GSTPATTERN
        global ARUBAPATTERN
        global STUSERVER
        global EMPSERVER
        global SHAREOU
        global STUDENTOU
        global GUESTOU
        global EMPOU
        global DEPGROUPOU
        global GeneralMacUsersOU
        global StuGeneralMacUsers
        global GuestGeneralMacUsers
        global EmpGeneralMacUsers
        global EmpGeneralWSUsers
        global FROM
        global TO
        global MAILSERVER
        
        LDAPSERVER = settings.LDAPSERVER
        USER = settings.USER
        PASSWORD = base64.b64decode(settings.PASSWORD)
        baseDN = settings.BASEDN
        MAILDOMAIN = settings.MAILDOMAIN
        STUPATTERN = settings.STUPATTERN
        GSTPATTERN = settings.GSTPATTERN
        ARUBAPATTERN = settings.ARUBAPATTERN
        STUSERVER = settings.STUSERVER
        EMPSERVER = settings.EMPSERVER
        SHAREOU = settings.SHAREOU
        STUDENTOU = settings.STUDENTOU
        GUESTOU = settings.GUESTOU
        EMPOU = settings.EMPOU
        DEPGROUPOU = settings.DEPGROUPOU
        GeneralMacUsersOU = settings.GeneralMacUsersOU
        StuGeneralMacUsers = settings.StuGeneralMacUsers
        GuestGeneralMacUsers = settings.GuestGeneralMacUsers
        EmpGeneralMacUsers = settings.EmpGeneralMacUsers
        EmpGeneralWSUsers = settings.EmpGeneralWSUsers
        FROM = settings.FROM
        TO = settings.TO
        MAILSERVER = settings.MAILSERVER

    except Exception as e:
        print("ERROR: unable to parse the settings file: {0}".format(e))
        return False
        
    return True

def getUserType(username):
    """ Function to determine the type of a user"""

    if STUPATTERN in username:
        userType = "STU"
    elif GSTPATTERN == username[0:-4]:
        userType = "GST"
    else:
        userType = "EMP"

    return userType
    
def lookupGroup(ou):
    """ This function looks up 
    group based on HR-provided ou"""
    
    # Create primOU->department group translation dictionary
    deptGroups = {}
    deptGroups['Art'] = 'Art'
    deptGroups['History'] = 'History'
    deptGroups['Art History'] = 'ArtHistory'
    deptGroups['Chemistry'] = 'Chemistry'
    deptGroups['Cinema'] = 'Cinema'
    deptGroups['Classical Studies'] = 'Classics'
    deptGroups['Human Resources'] = 'HumanResources'
    deptGroups['Information Technology Services'] = 'ITS'
    deptGroups['Theatre'] = 'Theatre'

    # Lookup the dept group by ou
    depGroup = deptGroups.get(ou, None)
    
    if depGroup:
        depGroup = 'cn=' + depGroup + DEPGROUPOU

    return depGroup

def ldapConnect():
    """Function to bind to LDAP server"""

    ldap_user = USER
    ldap_secret = PASSWORD
    ldap_server = LDAPSERVER
    
    try:
        # Open a connection to the LDAP server
        l = ldap.initialize(ldap_server)
        l.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        
        # Bind with a user that has rights to add/update objects
        l.simple_bind_s(ldap_user, ldap_secret)
    
    except ldap.LDAPError, e:
        print("ERROR: Could not establish LDAP connection: {0}".format(e))
        logging.error("problem binding to eDir LDAP server")
        return False
        
    return l

def findUser(l, username):
    """Do a quick check if the user already exists"""
    
    # Set the basic search parameters
    searchScope = ldap.SCOPE_SUBTREE
    retrieveAttributes = None 
    searchFilter = "cn=" + username
        
    try:
        ldap_result = l.search_s(baseDN, searchScope, searchFilter, ['dn'])		
    
    except ldap.LDAPError, e:
        print("ERROR: problems with LDAP search: {0}".format(e))
        logging.error("problem with LDAP search for: {0}".format(username))
    
    # Check the search results
    if len(ldap_result) == 0:
        logging.info("user {0} does not exist in eDir".format(username))
        return False
        
    return True
    
def userDisabled(l, username):
    """Do a quick check if the user is disabled"""
    
    # Set the search arguments
    searchScope = ldap.SCOPE_SUBTREE
    searchFilter = "cn=" + username
    
    try:
        ldap_result = l.search_s(baseDN, searchScope, searchFilter, 
                                    ['loginDisabled'])
        
    except ldap.LDAPError, e:
        print("ERROR: unable to retrieve loginDisabled status for username: " \
                "{0}".format(e))
        logging.error("problem retrieving loginDisabled status for: {0}" \
                        .format(username))
    
    # Is the user disabled?
    if ldap_result[0][1]['loginDisabled'][0] == 'TRUE':
        return True

    return False

def buildDN(username):
    """Function to construct FQN for a username"""

    # First check if emp or student or guest
    userType = getUserType(username)
    
    if userType == "STU":
        dn = "cn=" + username + STUDENTOU
        logging.info("looks like we have a student here: {0}".format(username))
    elif userType == "GST":
        dn = "cn=" + username + GUESTOU
        logging.info("looks like we have a guest here: {0}".format(username))
    else:
        dn="cn=" + username + EMPOU
        logging.info("looks like we have an employee here: {0}".format(username))

    return dn
 
def addMember(l, gdn, dn):
    """Function to add members to a group"""

    try:
        mod_attrs = [( ldap.MOD_ADD, 'member', dn ), 
                    ( ldap.MOD_ADD, 'equivalentToMe', dn )]
        l.modify_s(gdn, mod_attrs)
        
    except ldap.LDAPError, e:
        print("ERROR: cannot add memeber to group {0}, error: {1}" \
                .format(gdn, e))
        logging.error("problem adding user {0} to group {1}".format(dn, gdn))
        
    logging.info("user {0} added to eDir group {1}".format(dn, gdn))
    
    return

def delMemberUid(l, gn, gdn, username):
    """Function to delete memberUid atribute"""
    
    try:
        searchScope = ldap.SCOPE_SUBTREE
        searchFilter = "cn=" + gn
        ldap_result = l.search_s(baseDN, searchScope, searchFilter, 
                                    ['memberUid'])

        for member in ldap_result[0][1]['memberUid']:
            if username == member:
                mod_attrs = [ ( ldap.MOD_DELETE, 'memberUid', member ) ]
                l.modify_s(gdn, mod_attrs)
                logging.info("deleted old memberUid value {0} from group " \
                                "{1}".format(member, gdn))
    except ldap.LDAPError, e:
        print("ERROR: cannot delete memeberUid from group {0}, error: {1}" \
                .format(gn, e))
        logging.error("problem removing old memberUid {0} from group {1}" \
                        .format(username, gdn))
    
    return

def sendMail(frm, to, subject, text):
    """Function to send a notification email"""
    
    # Build the message body
    message = textwrap.dedent("""\
        From: {0}
        To: {1}
        Subject: {2}
        {3}
        """.format(frm, to, subject, text))
    
    try:
        # Send the mail
        mailserver = MAILSERVER
        server = smtplib.SMTP(mailserver)
        server.sendmail(frm, to, message)
        server.quit()
        
    except Exception as e:
        print("ERROR: unable to send email: {0}".format(e))
        logging.error("unknown error while sending email")
    
    return

if __name__ == "__main__":
    main(sys.argv)
